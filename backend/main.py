# backend/main.py
"""
Aplicação principal FastAPI.

Ponto de entrada da aplicação, configura rotas, middleware,
WebSocket e lifecycle events.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from pathlib import Path

from .core.config import get_settings
from .utils.logger import setup_logger
from .api.routes import router
from .api.websocket import manager
from .services.file_manager import ensure_directories

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    
    Startup: Inicializa logger e cria diretórios necessários
    Shutdown: Limpeza se necessário
    """
    # === STARTUP ===
    setup_logger(settings)
    ensure_directories()
    
    print("\n" + "="*60)
    print(f"🚀 {settings.app_name} v{settings.app_version}")
    print("="*60)
    print(f"📍 Ambiente: {'DESENVOLVIMENTO' if settings.debug else 'PRODUÇÃO'}")
    print(f"🔑 Providers configurados: {', '.join(settings.list_configured_providers())}")
    print("="*60 + "\n")
    
    yield
    
    # === SHUTDOWN ===
    print("\n🛑 Encerrando aplicação...")


# ============================================
# CRIAR APLICAÇÃO FASTAPI
# ============================================

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Sistema de geração automática de mapas mentais em Mermaid para conteúdo jurídico",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)


# ============================================
# MIDDLEWARE CORS
# ============================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# ROTAS DA API
# ============================================

app.include_router(router, prefix="/api", tags=["api"])


# ============================================
# ROTA RAIZ - SERVE A INTERFACE
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Serve a interface HTML principal.
    """
    html_path = Path("frontend/index.html")
    
    if not html_path.exists():
        return HTMLResponse(
            content="<h1>Erro: Interface não encontrada</h1><p>Arquivo frontend/index.html não existe.</p>",
            status_code=500
        )
    
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ============================================
# WEBSOCKET
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket para comunicação em tempo real.
    
    Envia atualizações de progresso, logs e notificações
    de conclusão durante o processamento.
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # Aguarda mensagens do cliente (se necessário)
            data = await websocket.receive_text()
            
            # Processa mensagens do cliente se necessário
            # Por enquanto, apenas mantém conexão aberta
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================
# ROTA DE HEALTH CHECK
# ============================================

@app.get("/health")
async def health_check():
    """
    Verifica status da aplicação.
    
    Retorna informações sobre a saúde do sistema,
    providers configurados e versão.
    """
    return JSONResponse({
        "status": "healthy",
        "version": settings.app_version,
        "providers": settings.list_configured_providers(),
        "debug": settings.debug
    })


# ============================================
# ARQUIVOS ESTÁTICOS (OPCIONAL)
# ============================================

# Se você quiser servir CSS/JS separados:
static_path = Path("frontend/static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# ============================================
# HANDLER DE ERROS GLOBAL
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Handler global para exceções não tratadas.
    """
    from .utils.logger import logger
    
    logger.error(f"Erro não tratado: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "Ocorreu um erro interno",
            "type": type(exc).__name__
        }
    )


# ============================================
# EXECUÇÃO DIRETA
# ============================================

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )