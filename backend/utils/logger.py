# backend/utils/logger.py
from loguru import logger
from pathlib import Path
import sys
from datetime import datetime

def setup_logger(settings):
    """
    Configura o Loguru para logging estruturado.
    
    Cria logs em:
    - Console: formato colorido e legível
    - Arquivo: formato JSON para análise
    """
    
    # Remove handler padrão
    logger.remove()
    
    # === CONSOLE HANDLER ===
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True
    )
    
    # === FILE HANDLER (JSON) ===
    log_path = Path(settings.logs_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_path / "app_{time:YYYY-MM-DD}.json",
        format="{message}",
        level="INFO",
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        serialize=True,  # JSON format
        enqueue=True     # Thread-safe
    )
    
    # === FILE HANDLER (TEXT - LEGÍVEL) ===
    logger.add(
        log_path / "app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        enqueue=True
    )
    
    logger.info("=" * 60)
    logger.info("Sistema de logs inicializado")
    logger.info(f"Diretório de logs: {log_path}")
    logger.info("=" * 60)
    
    return logger

def log_execution_time(func):
    """Decorator para logar tempo de execução de funções."""
    import functools
    import time
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        logger.info(f"Iniciando: {func.__name__}")
        
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start
            logger.success(f"Concluído: {func.__name__} ({elapsed:.2f}s)")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"Erro em {func.__name__} após {elapsed:.2f}s: {str(e)}")
            raise
    
    return wrapper

# Helper para adicionar timestamp aos logs
def _get_timestamp():
    return datetime.now().isoformat()

logger._get_timestamp = _get_timestamp