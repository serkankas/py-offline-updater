"""
RCU UDP Discovery Server - Port 65535 listener
Responds to <discover/> messages with device info
"""
import asyncio
from core.settings import settings


class RCUDiscoveryServer:
    """UDP Discovery Server Manager"""
    
    def __init__(self):
        self._transport = None
        self._running = False
        
    async def start(self):
        """UDP discovery server'ı başlat"""
        if self._running:
            return
            
        try:
            loop = asyncio.get_event_loop()
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: UDPDiscoveryProtocol(),
                local_addr=('0.0.0.0', settings.RCU_UDP_PORT)
            )
            self._running = True
            print(f"[RCU UDP] Listening on 0.0.0.0:{settings.RCU_UDP_PORT}")
            
        except Exception as e:
            print(f"[RCU UDP] ERROR: {e}")
            
    async def stop(self):
        """UDP discovery server'ı durdur"""
        if not self._running:
            return
            
        self._running = False
        if self._transport:
            self._transport.close()


class UDPDiscoveryProtocol(asyncio.DatagramProtocol):
    """UDP Discovery Protocol Handler"""

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        """UDP datagram alındığında çağrılır"""
        try:
            message = data.decode('utf-8', errors='ignore').strip('\x00').strip()
            
            if message == '<discover/>':
                if settings.DEBUG:
                    print(f"[RCU UDP] Discovery from {addr}")
                response = self._build_discovery_response()
                self.transport.sendto(response.encode('utf-8'), addr)
            elif settings.DEBUG:
                print(f"[RCU UDP] Unknown: {message[:50]}")
                
        except Exception as e:
            if settings.DEBUG:
                print(f"[RCU UDP] ERROR: {e}")
    
    def _build_discovery_response(self) -> str:
        """UDP discovery için XML response oluştur"""
        return f"""<info>
  <host>{settings.RCU_HOST}</host>
  <port>{settings.RCU_TCP_PORT}</port>
  <type>{settings.RCU_TYPE}</type>
  <serial>{settings.RCU_SERIAL}</serial>
  <sw_version>{settings.RCU_SW_VERSION}</sw_version>
  <version>{settings.RCU_VERSION}</version>
  <status>STARTED</status>
  <hw_version>{settings.RCU_HW_VERSION}</hw_version>
  <fw_version>{settings.RCU_FW_VERSION}</fw_version>
  <os_version>{settings.RCU_OS_VERSION}</os_version>
</info>"""


# Singleton instance
rcu_discovery_server = RCUDiscoveryServer()
