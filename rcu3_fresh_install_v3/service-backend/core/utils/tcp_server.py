"""
VDR TCP Server - Port 7000 listener
DEBUG mode: Simulated VDR messages from .env
PRODUCTION mode: Real TCP connection
"""
import asyncio
import time
from enum import Enum
from core.settings import settings
from core.utils.docker import docker_manager


class VDRStatus(Enum):
    """VDR bağlantı durumları"""
    WAITING = "waiting"
    CONNECTED = "connected"
    STARTED = "started"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"


class VDRTCPServer:
    """VDR TCP Server Manager"""
    
    WAITING_TIMEOUT = 180  # 3 dakika (saniye)

    def __init__(self):
        if settings.DEBUG:
            import os
            mock_status = os.getenv("VDR_MOCK_STATUS", "waiting")
            try:
                self.status = VDRStatus(mock_status)
            except ValueError:
                self.status = VDRStatus.WAITING
        else:
            self.status = VDRStatus.WAITING

        self.vessel_info = {}
        self.client_address = None
        self.last_message_time = None
        self._server = None
        self._running = False
        self._clear_received = False  # <clear/> flag
        self._waiting_since = time.monotonic()  # WAITING state başlangıç zamanı
        
    async def start(self):
        """TCP server'ı başlat"""
        if settings.DEBUG:
            print(f"[VDR TCP] DEBUG mode - status: {self.status.value}")
            self._running = True
            return
            
        if self._running:
            return
            
        try:
            self._server = await asyncio.start_server(
                self._handle_client,
                settings.VDR_TCP_HOST,
                settings.VDR_TCP_PORT
            )
            self._running = True
            print(f"[VDR TCP] Listening on {settings.VDR_TCP_HOST}:{settings.VDR_TCP_PORT}")
            
        except Exception as e:
            print(f"[VDR TCP] ERROR: {e}")
            
    async def stop(self):
        """TCP server'ı durdur"""
        if settings.DEBUG:
            self._running = False
            return
            
        if not self._running:
            return
            
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            
    async def _handle_client(self, reader, writer):
        """VDR bağlantısını işle"""
        addr = writer.get_extra_info('peername')
        self.client_address = addr
        self.status = VDRStatus.CONNECTED
        self._clear_received = False
        self._waiting_since = None  # Bağlantı kuruldu, waiting timeout'u sıfırla
        print(f"[VDR TCP] Connected: {addr}")
        
        try:
            while self._running:
                data = await reader.read(1024)
                if not data:
                    break
                    
                message = data.decode('utf-8', errors='ignore').strip()
                await self._process_message(message, writer)
                
        except Exception as e:
            print(f"[VDR TCP] ERROR: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            
            # Eğer <clear/> aldıysak ve <start/> gelmeden disconnect olduysa = STOPPED
            if self._clear_received:
                self.status = VDRStatus.STOPPED
                print(f"[VDR TCP] Disconnected after <clear/>: STOPPED")
            else:
                self.status = VDRStatus.DISCONNECTED
                print(f"[VDR TCP] Disconnected: {addr}")

            self.client_address = None
            self._clear_received = False
            self._waiting_since = None
            
    async def _process_message(self, message: str, writer):
        """VDR mesajını işle"""
        self.last_message_time = time.time()
        
        if '<clear/>' in message:
            # <clear/> flag set et - eğer <start/> gelmezse STOPPED olacak
            self._clear_received = True
            print(f"[VDR TCP] <clear/> received")
            
        elif '<start/>' in message:
            self._clear_received = False  # <start/> geldi, flag temizle
            self.status = VDRStatus.STARTED
            print(f"[VDR TCP] <start/> - Status: STARTED")
            result = await docker_manager.restart_containers()
            if not result['success']:
                print(f"[VDR TCP] Docker restart failed: {result['message']}")
            else:
                print(f"[VDR TCP] Docker restarted, Chromium refreshed")
            
        elif '<main_ch>' in message:
            self._parse_config(message)
            
        elif '<vessel_name>' in message:
            self._parse_config(message)
            
        elif '<req>info</req>' in message:
            response = self._build_info_response()
            writer.write(response.encode('utf-8'))
            await writer.drain()
            
    def _parse_config(self, message: str):
        """XML config mesajlarını parse et"""
        if '<main_ch>' in message:
            value = message.split('<main_ch>')[1].split('</main_ch>')[0]
            self.vessel_info['main_ch'] = value
        elif '<vessel_name>' in message:
            value = message.split('<vessel_name>')[1].split('</vessel_name>')[0]
            self.vessel_info['vessel_name'] = value
            
    def _build_info_response(self) -> str:
        """<req>info</req> için XML response"""
        return f"""<info>
  <host>{settings.VDR_HOST}</host>
  <port>{settings.VDR_TCP_PORT}</port>
  <serial>{settings.VDR_SERIAL}</serial>
  <status>CONNECTED</status>
</info>\x00"""
    
    def get_status(self) -> dict:
        """
        VDR durumunu döndür.
        - WAITING state 3 dakikayı geçerse → DISCONNECTED
        - Gerçek disconnect kontrolü: son 90 saniyede mesaj var mı?
        - VDR heartbeat (~56s aralıklarla) + buffer için 90s kullanıyoruz.
        """
        actual_status = self.status.value

        # WAITING state timeout: 3 dakika içinde bağlantı yoksa → disconnected
        if self.status == VDRStatus.WAITING and self._waiting_since is not None:
            elapsed = time.monotonic() - self._waiting_since
            if elapsed >= self.WAITING_TIMEOUT:
                actual_status = VDRStatus.DISCONNECTED.value
                return {
                    "status": actual_status,
                    "vessel_info": self.vessel_info,
                    "client_address": self.client_address,
                    "last_message_time": self.last_message_time,
                    "tcp_running": self._running,
                }

        # last_message_time varsa, gerçek bağlantı durumunu kontrol et
        if self.last_message_time is not None:
            time_since_last_msg = time.time() - self.last_message_time

            if time_since_last_msg < 90:
                # Son 90 saniyede mesaj gelmiş - bağlantı aktif
                # VDR ~56s aralıklarla heartbeat gönderiyor, 90s buffer yeterli
                if self.status == VDRStatus.DISCONNECTED:
                    # TCP socket kapanmış ama mesajlar hala geliyor
                    # Demek ki VDR aktif (yeni connection açılmış olabilir)
                    actual_status = VDRStatus.CONNECTED.value
            else:
                # 90+ saniye mesaj yok - gerçek disconnect
                if self.status != VDRStatus.WAITING:
                    actual_status = VDRStatus.DISCONNECTED.value

        return {
            "status": actual_status,
            "vessel_info": self.vessel_info,
            "client_address": self.client_address,
            "last_message_time": self.last_message_time,
            "tcp_running": self._running,
        }


vdr_tcp_server = VDRTCPServer()