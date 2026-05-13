"""
Docker Compose Manager
DEBUG mode: Simulated docker operations
PRODUCTION mode: Real docker-compose commands
"""
import subprocess
import os
from core.settings import settings


class DockerManager:
    """Docker Compose yöneticisi"""
    
    def __init__(self):
        self.is_running = False
        # Environment hazırla (subprocess için)
        self.env = os.environ.copy()
        
    async def start_containers(self) -> dict:
        """Docker Compose up"""
        if settings.DEBUG:
            self.is_running = True
            print("[DOCKER] Simulated: docker-compose up")
            return {
                "success": True,
                "message": "Containers started (simulated)",
                "mode": "debug"
            }
        
        try:
            result = subprocess.run(
                ['docker-compose', 'up', '-d'],
                cwd=settings.DOCKER_COMPOSE_PATH,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.is_running = True
                print("[DOCKER] Containers started")
                return {
                    "success": True,
                    "message": "Containers started",
                    "mode": "production"
                }
            else:
                print(f"[DOCKER] ERROR: {result.stderr}")
                return {
                    "success": False,
                    "message": result.stderr,
                    "mode": "production"
                }
                
        except FileNotFoundError:
            return {
                "success": False,
                "message": "docker-compose not found",
                "mode": "production"
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "docker-compose timeout",
                "mode": "production"
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "mode": "production"
            }
    
    async def stop_containers(self) -> dict:
        """Docker Compose down"""
        if settings.DEBUG:
            self.is_running = False
            print("[DOCKER] Simulated: docker-compose down")
            return {
                "success": True,
                "message": "Containers stopped (simulated)",
                "mode": "debug"
            }
        
        try:
            result = subprocess.run(
                ['docker-compose', 'down'],
                cwd=settings.DOCKER_COMPOSE_PATH,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.is_running = False
                print("[DOCKER] Containers stopped")
                return {
                    "success": True,
                    "message": "Containers stopped",
                    "mode": "production"
                }
            else:
                print(f"[DOCKER] ERROR: {result.stderr}")
                return {
                    "success": False,
                    "message": result.stderr,
                    "mode": "production"
                }
                
        except FileNotFoundError:
            return {
                "success": False,
                "message": "docker-compose not found",
                "mode": "production"
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "docker-compose timeout",
                "mode": "production"
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "mode": "production"
            }
    
    async def restart_containers(self) -> dict:
        """Docker Compose restart (down + up + chromium restart)"""
        from core.utils.systemd import systemd_manager  # Lazy import to avoid circular dependency
        
        print("[DOCKER] Restarting containers...")
        
        # 1. Docker down
        down_result = await self.stop_containers()
        if not down_result['success']:
            return {
                "success": False,
                "message": f"Docker down failed: {down_result['message']}",
                "mode": down_result['mode']
            }
        
        # 2. Docker up
        up_result = await self.start_containers()
        if not up_result['success']:
            return {
                "success": False,
                "message": f"Docker up failed: {up_result['message']}",
                "mode": up_result['mode']
            }
        
        # 3. Chromium restart (browser refresh için)
        chromium_result = await systemd_manager.restart_chromium()
        if not chromium_result['success']:
            print(f"[DOCKER] Chromium restart failed: {chromium_result['message']}")
            # Chromium fail olsa bile docker başarılı sayılır
        
        return {
            "success": True,
            "message": "Containers restarted successfully",
            "chromium_restarted": chromium_result['success'],
            "mode": up_result['mode']
        }
    
    def get_status(self) -> dict:
        """Docker durumunu döndür"""
        return {
            "is_running": self.is_running,
            "compose_path": settings.DOCKER_COMPOSE_PATH,
            "mode": "debug" if settings.DEBUG else "production"
        }


# Global instance
docker_manager = DockerManager()