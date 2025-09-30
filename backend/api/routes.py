# backend/api/routes.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from typing import List
import asyncio
from pathlib import Path

from ..agents.graph import create_mindmap_graph
from ..agents.state import MindmapState
from ..services.file_manager import save_uploaded_html, get_output_files
from ..api.websocket import manager
from ..utils.logger import logger
from ..core.config import get_settings

router = APIRouter()
settings = get_settings()

@router.post("/process")
async def process_htmls(
    files: List[UploadFile] = File(...),
    llm01_provider: str = Form(...),
    llm02_provider: str = Form(...),
    llm03_provider: str = Form(...)
):
    """
    Processa arquivos HTML e gera mapas mentais.
    
    Args:
        files: Lista de arquivos HTML
        llm01_provider: Provider para divisão (openai|anthropic|gemini|deepseek)
        llm02_provider: Provider para geração (openai|anthropic|gemini|deepseek)
        llm03_provider: Provider para revisão (openai|anthropic|gemini|deepseek)
    
    Returns:
        dict: Resultado do processamento
    """
    
    try:
        logger.info(f"Recebidos {len(files)} arquivos para processamento")
        
        # Valida providers
        valid_providers = ["openai", "anthropic", "gemini", "deepseek"]
        for provider in [llm01_provider, llm02_provider, llm03_provider]:
            if provider not in valid_providers:
                raise HTTPException(400, f"Provider inválido: {provider}")
        
        # Salva arquivos enviados
        uploaded_files = []
        for file in files:
            if not file.filename.endswith('.html'):
                continue
            
            content = await file.read()
            filepath = save_uploaded_html(content, file.filename)
            uploaded_files.append(file.filename)
            logger.info(f"Arquivo salvo: {file.filename}")
        
        if not uploaded_files:
            raise HTTPException(400, "Nenhum arquivo HTML válido encontrado")
        
        # Processa cada arquivo
        results = []
        
        for filename in uploaded_files:
            try:
                logger.info(f"Processando: {filename}")
                
                # Cria o grafo LangGraph
                graph = create_mindmap_graph()
                
                # Estado inicial
                initial_state: MindmapState = {
                    "html_filename": filename,
                    "ramo_direito": "",
                    "topico": "",
                    "fundamentacao": "",
                    "divisoes": [],
                    "partes_processadas": [],
                    "tentativas_revisao": 0,
                    "max_tentativas": settings.max_tentativas_revisao,
                    "status": "parsing",
                    "erro_msg": None,
                    "llm01_provider": llm01_provider,
                    "llm02_provider": llm02_provider,
                    "llm03_provider": llm03_provider,
                    "logs": []
                }
                
                # Executa o grafo
                config = {"configurable": {"thread_id": filename}}
                
                # Stream de eventos para WebSocket
                async for event in graph.astream(initial_state, config):
                    # Envia progresso via WebSocket
                    if "__end__" not in event:
                        for node_name, node_data in event.items():
                            await manager.send_log({
                                "level": "info",
                                "message": f"Executando: {node_name}",
                                "node": node_name
                            })
                
                # Pega estado final
                final_state = await graph.aget_state(config)
                
                if final_state.values["status"] == "concluido":
                    results.append({
                        "file": filename,
                        "success": True,
                        "parts": len(final_state.values["partes_processadas"]),
                        "logs": final_state.values["logs"]
                    })
                    
                    await manager.send_completion({
                        "success": True,
                        "file": filename,
                        "files_generated": len(final_state.values["partes_processadas"])
                    })
                else:
                    results.append({
                        "file": filename,
                        "success": False,
                        "error": final_state.values.get("erro_msg", "Erro desconhecido")
                    })
                    
            except Exception as e:
                logger.error(f"Erro ao processar {filename}: {str(e)}")
                results.append({
                    "file": filename,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "status": "completed",
            "total_files": len(uploaded_files),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        raise HTTPException(500, str(e))

@router.get("/outputs")
async def list_outputs():
    """Lista arquivos .mmd gerados."""
    try:
        files = get_output_files()
        return {
            "files": [Path(f).name for f in files],
            "total": len(files)
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download de arquivo .mmd específico."""
    try:
        filepath = Path(settings.output_dir) / filename
        
        if not filepath.exists():
            raise HTTPException(404, "Arquivo não encontrado")
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="text/plain"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))