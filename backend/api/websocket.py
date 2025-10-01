# backend/api/websocket.py
"""
Gerenciador de conexões WebSocket com logs de debug.
"""

from fastapi import WebSocket
from typing import List
import json
from datetime import datetime
from ..utils.logger import logger


class ConnectionManager:
    """Gerencia conexões WebSocket para progresso em tempo real."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Aceita nova conexão WebSocket."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        logger.info(f"🔌 Nova conexão WebSocket. Total: {len(self.active_connections)}")
        
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
            logger.info(f"🔌 Conexão WebSocket removida. Total: {len(self.active_connections)}")
    
    async def send_message(self, websocket: WebSocket, message: dict):
        """Envia mensagem para um cliente específico."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"⚠️ Erro ao enviar mensagem: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Envia mensagem para todos os clientes conectados."""
        if not self.active_connections:
            logger.warning("⚠️ Nenhuma conexão WebSocket ativa para broadcast")
            return
        
        logger.debug(f"📡 Broadcasting para {len(self.active_connections)} cliente(s): {message.get('type', 'unknown')}")
        
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao broadcast: {e}")
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
        
        logger.debug(
            f"📊 Progresso: {progress.get('current_step', 0)}/{progress.get('total_steps', 0)} "
            f"({progress.get('percentage', 0)}%) - {progress.get('message', '')}"
        )
        
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
        
        # Log no console também
        level_map = {
            "info": logger.info,
            "success": logger.success,
            "warning": logger.warning,
            "error": logger.error
        }
        
        log_func = level_map.get(log_entry.get("level", "info"), logger.info)
        log_func(f"📨 WS Log: {log_entry.get('message', '')}")
        
        await self.broadcast(message)
    
    async def send_completion(self, result: dict):
        """
        Envia notificação de conclusão.
        
        Args:
            result: {
                "success": True/False,
                "files_generated": ["file1.mmd", "file2.mmd"],
                "total_files": 2,
                "output_dir": "output",
                "error": "mensagem de erro" (se falha)
            }
        """
        message = {
            "type": "completion",
            "timestamp": datetime.now().isoformat(),
            **result
        }
        
        logger.success(
            f"✅ Processamento concluído: {result.get('total_files', 0)} arquivo(s) gerado(s)"
        )
        
        await self.broadcast(message)


# Instância global
manager = ConnectionManager()