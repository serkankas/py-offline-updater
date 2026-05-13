"""
Service Status Manager
Tracks overall service phase based on VDR connection and TCP server state
"""
from enum import Enum
from core.settings import settings


class ServicePhase(Enum):
    """Service operational phases"""
    INITIALIZING = "initializing"      # System Starting
    OPERATIONAL = "operational"         # Normal Operation
    PAUSED = "paused"                  # System Stopped
    DISCONNECTED = "disconnected"      # No Connection


class ServiceStatusManager:
    """Manages overall service status based on VDR and TCP server states"""
    
    def __init__(self):
        if settings.DEBUG:
            import os
            mock_phase = os.getenv("SERVICE_MOCK_PHASE", "initializing")
            try:
                self.phase = ServicePhase(mock_phase)
            except ValueError:
                self.phase = ServicePhase.INITIALIZING
        else:
            self.phase = ServicePhase.INITIALIZING
        
    def update_from_vdr(self, vdr_status: str, tcp_running: bool, last_message_time: float = None):
        """
        Update service phase based on VDR status
        
        Args:
            vdr_status: VDR status string (waiting, connected, started, stopped, disconnected)
            tcp_running: Whether TCP server is running
            last_message_time: Last message timestamp (None if no messages yet)
        """
        import time
        
        # DEBUG mode: keep the mocked phase
        if settings.DEBUG:
            return
        
        # TCP server not running -> DISCONNECTED
        if not tcp_running:
            self.phase = ServicePhase.DISCONNECTED
            return
        
        # Check 90s timeout if we have message history
        if last_message_time is not None:
            time_since_last = time.time() - last_message_time
            if time_since_last >= 90:
                self.phase = ServicePhase.DISCONNECTED
                return
        
        # Map VDR status to service phase
        if vdr_status == "started":
            self.phase = ServicePhase.OPERATIONAL
        elif vdr_status == "stopped":
            self.phase = ServicePhase.PAUSED
        elif vdr_status in ["disconnected", "error"]:
            self.phase = ServicePhase.DISCONNECTED
        elif vdr_status in ["waiting", "connected"]:
            # If still in INITIALIZING, stay there
            # Otherwise, if we were operational/paused, go to DISCONNECTED
            if self.phase not in [ServicePhase.INITIALIZING]:
                self.phase = ServicePhase.DISCONNECTED
    
    def get_phase(self) -> str:
        """Get current phase as string"""
        return self.phase.value
    
    def get_display_text(self) -> str:
        """Get user-facing display text"""
        display_map = {
            ServicePhase.INITIALIZING: "System Starting",
            ServicePhase.OPERATIONAL: "Normal Operation",
            ServicePhase.PAUSED: "System Stopped",
            ServicePhase.DISCONNECTED: "No Connection"
        }
        return display_map[self.phase]
    
    def get_status(self) -> dict:
        """Get full status information"""
        return {
            "phase": self.phase.value,
            "display": self.get_display_text()
        }


service_status_manager = ServiceStatusManager()
