"""
Systemd Service Manager
DEBUG mode: Simulated systemd operations
PRODUCTION mode: Real systemctl commands
"""
import subprocess
from core.settings import settings


class SystemdManager:
    """Systemd servis yöneticisi"""
    
    async def restart_service(self, service_name: str) -> dict:
        """Systemd servisini restart et"""
        if settings.DEBUG:
            print(f"[SYSTEMD] Simulated: systemctl restart {service_name}")
            return {
                "success": True,
                "message": f"{service_name} restarted (simulated)",
                "mode": "debug"
            }
        
        try:
            result = subprocess.run(
                ['systemctl', 'restart', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"[SYSTEMD] {service_name} restarted")
                return {
                    "success": True,
                    "message": f"{service_name} restarted",
                    "mode": "production"
                }
            else:
                print(f"[SYSTEMD] ERROR: {result.stderr}")
                return {
                    "success": False,
                    "message": result.stderr,
                    "mode": "production"
                }
                
        except FileNotFoundError:
            return {
                "success": False,
                "message": "systemctl not found",
                "mode": "production"
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "systemctl timeout",
                "mode": "production"
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "mode": "production"
            }
    
    async def restart_chromium(self) -> dict:
        """Chromium kiosk servisini restart et"""
        return await self.restart_service("chromium-kiosk.service")


# Global instance
systemd_manager = SystemdManager()

