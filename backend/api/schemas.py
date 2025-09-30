# backend/api/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class ProcessRequest(BaseModel):
    """Schema para requisição de processamento."""
    llm01_provider: Literal["openai", "anthropic", "gemini", "deepseek"]
    llm02_provider: Literal["openai", "anthropic", "gemini", "deepseek"]
    llm03_provider: Literal["openai", "anthropic", "gemini", "deepseek"]

class FileResult(BaseModel):
    """Resultado do processamento de um arquivo."""
    file: str
    success: bool
    parts: Optional[int] = None
    error: Optional[str] = None
    logs: Optional[List[dict]] = None

class ProcessResponse(BaseModel):
    """Resposta do processamento."""
    status: str
    total_files: int
    results: List[FileResult]
    
class OutputFile(BaseModel):
    """Informações de um arquivo de output."""
    filename: str
    created_at: Optional[datetime] = None
    size: Optional[int] = None

class OutputListResponse(BaseModel):
    """Lista de arquivos de output."""
    files: List[str]
    total: int

class WebSocketMessage(BaseModel):
    """Mensagem WebSocket."""
    type: Literal["connection", "progress", "log", "completion"]
    timestamp: str
    data: Optional[dict] = None

class ProgressUpdate(BaseModel):
    """Atualização de progresso."""
    stage: Literal["parsing", "dividindo", "gerando", "revisando", "salvando"]
    current_step: int
    total_steps: int
    message: str
    percentage: float
    html_file: str

class LogEntry(BaseModel):
    """Entrada de log."""
    level: Literal["info", "success", "warning", "error"]
    message: str
    node: Optional[str] = None
    data: Optional[dict] = None

class CompletionNotification(BaseModel):
    """Notificação de conclusão."""
    success: bool
    files_generated: Optional[List[str]] = None
    total_time: Optional[str] = None
    error: Optional[str] = None

class HealthCheck(BaseModel):
    """Status de saúde da aplicação."""
    status: str
    version: str
    uptime: float
    providers_configured: List[str]