from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

router = APIRouter()

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()

@router.websocket("/ambulance/{case_id}")
async def websocket_ambulance(websocket: WebSocket, case_id: str):
    await manager.connect(websocket, f"amb_{case_id}")
    try:
        while True:
            data = await websocket.receive_json()
            # Broadcast the ambulance update to the hospital dashboard
            await manager.broadcast({"type": "AMBULANCE_UPDATE", "case_id": case_id, "data": data})
    except WebSocketDisconnect:
        manager.disconnect(f"amb_{case_id}")
        await manager.broadcast({"type": "AMBULANCE_DISCONNECT", "case_id": case_id})

@router.websocket("/hospital")
async def websocket_hospital(websocket: WebSocket):
    # The hospital command center connection
    client_id = "hospital_dashboard"
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle messages from hospital if needed
    except WebSocketDisconnect:
        manager.disconnect(client_id)
