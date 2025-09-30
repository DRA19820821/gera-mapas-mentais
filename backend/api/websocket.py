# backend/api/websocket.py
from fastapi import WebSocket
from typing import List
import json
from datetime import datetime

class ConnectionManager:
    """Gerencia conexões WebSocket para progresso em tempo real."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Aceita nova conexão WebSocket."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Envia mensagem de boas-vindas
        await self.send_message(websocket, {
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.now().isoformat()
        })
    
    def disconnect(self, websocket: WebSocket):
        """Remove conexão WebSocket."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_message(self, websocket: WebSocket, message: dict):
        """Envia mensagem para um cliente específico."""
        try:
            await websocket.send_json(message)
        except:
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Envia mensagem para todos os clientes conectados."""
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Remove conexões mortas
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_progress(self, progress: dict):
        """
        Envia atualização de progresso.
        
        Args:
            progress: {
                "stage": "parsing|dividindo|gerando|revisando|salvando",
                "current_step": 1,
                "total_steps": 5,
                "message": "Processando...",
                "percentage": 20,
                "html_file": "nome_arquivo.html"
            }
        """
        message = {
            "type": "progress",
            "timestamp": datetime.now().isoformat(),
            **progress
        }
        await self.broadcast(message)
    
    async def send_log(self, log_entry: dict):
        """
        Envia entrada de log.
        
        Args:
            log_entry: {
                "level": "info|success|warning|error",
                "message": "Mensagem...",
                "node": "nome_do_node",
                "data": {...}
            }
        """
        message = {
            "type": "log",
            "timestamp": datetime.now().isoformat(),
            **log_entry
        }
        await self.broadcast(message)
    
    async def send_completion(self, result: dict):
        """
        Envia notificação de conclusão.
        
        Args:
            result: {
                "success": True/False,
                "files_generated": ["file1.mmd", "file2.mmd"],
                "total_time": "45.2s",
                "error": "mensagem de erro" (se falha)
            }
        """
        message = {
            "type": "completion",
            "timestamp": datetime.now().isoformat(),
            **result
        }
        await self.broadcast(message)

# Instância global
manager = ConnectionManager()