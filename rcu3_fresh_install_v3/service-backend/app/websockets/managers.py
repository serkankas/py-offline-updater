from .base import BaseWebsocketConsumer

from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[BaseWebsocketConsumer]] = {}
    
    def add_connection(self, group: str, consumer: BaseWebsocketConsumer):
        if group not in self.active_connections:
            self.active_connections[group] = []
        self.active_connections[group].append(consumer)
        print(f"Connection added to group '{group}'. Total: {len(self.active_connections[group])}")
    
    def remove_connection(self, group: str, consumer: BaseWebsocketConsumer):
        if group in self.active_connections:
            try:
                self.active_connections[group].remove(consumer)
                print(f"Connection removed from group '{group}'. Remaining: {len(self.active_connections[group])}")
                if not self.active_connections[group]:
                    del self.active_connections[group]
            except ValueError:
                pass
    
    async def close_all_group_connections(self, group:str):
        if group not in self.active_connections:
            print(f"No connections in group '{group}'")
            return
        
        for consumer in self.active_connections[group]:
            await consumer.disconnect()
        
        del(self.active_connections[group])
        print(f"All connections in group '{group}' closed")

    async def broadcast(self, group: str, message: dict):
        if group not in self.active_connections:
            print(f"No connections in group '{group}'")
            return
        
        for consumer in self.active_connections[group]:
            if consumer.is_connected:
                await consumer.websocket.send_json(message)
    
    def get_group_size(self, group: str) -> int:
        return len(self.active_connections.get(group, []))

websocket_manager = ConnectionManager()

