# backend/services/file_manager.py
import os
from pathlib import Path
from datetime import datetime
import json
from ..core.config import get_settings

settings = get_settings()

def ensure_directories():
    """Garante que os diretórios necessários existem."""
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.logs_dir).mkdir(parents=True, exist_ok=True)

def save_uploaded_html(file_content: bytes, filename: str) -> str:
    """
    Salva HTML enviado pelo usuário.
    
    Returns:
        str: Caminho completo do arquivo salvo
    """
    ensure_directories()
    
    # Sanitiza nome do arquivo
    safe_filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))
    
    filepath = Path(settings.upload_dir) / safe_filename
    
    with open(filepath, 'wb') as f:
        f.write(file_content)
    
    return str(filepath)

def save_mmd_file(filename: str, content: str, metadata: dict = None) -> str:
    """
    Salva arquivo .mmd no diretório de output.
    
    Args:
        filename: Nome do arquivo (ex: direito_penal_parte01.mmd)
        content: Conteúdo do mapa mental em Mermaid
        metadata: Metadados opcionais (dict)
    
    Returns:
        str: Caminho completo do arquivo salvo
    """
    ensure_directories()
    
    filepath = Path(settings.output_dir) / filename
    
    # Salva o arquivo .mmd
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Salva metadados se fornecidos
    if metadata:
        meta_filename = filename.replace('.mmd', '.meta.json')
        meta_filepath = Path(settings.output_dir) / meta_filename
        
        with open(meta_filepath, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    return str(filepath)

def get_output_files(pattern: str = "*.mmd") -> list[str]:
    """
    Lista arquivos .mmd no diretório de output.
    
    Args:
        pattern: Padrão glob (default: "*.mmd")
    
    Returns:
        list: Lista de caminhos de arquivos
    """
    ensure_directories()
    output_path = Path(settings.output_dir)
    return [str(f) for f in output_path.glob(pattern)]

def cleanup_old_files(max_age_days: int = 7):
    """
    Remove arquivos antigos dos diretórios de upload e output.
    
    Args:
        max_age_days: Idade máxima em dias (default: 7)
    """
    from datetime import timedelta
    
    cutoff = datetime.now() - timedelta(days=max_age_days)
    
    for directory in [settings.upload_dir, settings.output_dir]:
        path = Path(directory)
        if not path.exists():
            continue
        
        for file in path.iterdir():
            if file.is_file():
                file_time = datetime.fromtimestamp(file.stat().st_mtime)
                if file_time < cutoff:
                    file.unlink()
                    print(f"Removido arquivo antigo: {file}")