# backend/api/routes.py
"""
Rotas da API com progresso funcional via WebSocket.
"""

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
    VERSÃO CORRIGIDA: Envia progresso real via WebSocket
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
        
        # Envia progresso inicial
        await manager.send_progress({
            "stage": "parsing",
            "current_step": 0,
            "total_steps": len(uploaded_files) * 5,  # 5 etapas por arquivo
            "message": f"Preparando processamento de {len(uploaded_files)} arquivo(s)...",
            "percentage": 0,
            "html_file": uploaded_files[0] if uploaded_files else ""
        })
        
        # Processa cada arquivo
        results = []
        step_counter = 0
        total_steps = len(uploaded_files) * 5
        
        for file_index, filename in enumerate(uploaded_files, 1):
            try:
                logger.info(f"Processando: {filename} ({file_index}/{len(uploaded_files)})")
                
                # === PARSING ===
                step_counter += 1
                await manager.send_progress({
                    "stage": "parsing",
                    "current_step": step_counter,
                    "total_steps": total_steps,
                    "message": f"Analisando HTML: {filename}",
                    "percentage": int((step_counter / total_steps) * 100),
                    "html_file": filename
                })
                
                await manager.send_log({
                    "level": "info",
                    "message": f"📄 Parsing HTML: {filename}",
                    "node": "parse_html"
                })
                
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
                
                config = {"configurable": {"thread_id": filename}}
                
                # === DIVISÃO ===
                step_counter += 1
                await manager.send_progress({
                    "stage": "dividindo",
                    "current_step": step_counter,
                    "total_steps": total_steps,
                    "message": f"Dividindo conteúdo com LLM01 ({llm01_provider})...",
                    "percentage": int((step_counter / total_steps) * 100),
                    "html_file": filename
                })
                
                await manager.send_log({
                    "level": "info",
                    "message": f"🤖 LLM01 ({llm01_provider}): Analisando conteúdo...",
                    "node": "dividir_conteudo"
                })
                
                # Executa o grafo com streaming
                current_node = ""
                num_partes = 0
                partes_concluidas = 0
                
                async for event in graph.astream(initial_state, config):
                    # Detecta qual node está executando
                    if "__end__" not in event:
                        for node_name, node_data in event.items():
                            current_node = node_name
                            
                            # === GERAÇÃO ===
                            if node_name == "gerar_mindmap":
                                if num_partes == 0 and "divisoes" in node_data:
                                    num_partes = len(node_data.get("divisoes", []))
                                
                                partes_concluidas = len([p for p in node_data.get("partes_processadas", []) if p.get("aprovado")])
                                
                                step_counter += 0.5
                                await manager.send_progress({
                                    "stage": "gerando",
                                    "current_step": int(step_counter),
                                    "total_steps": total_steps,
                                    "message": f"Gerando mapa mental {partes_concluidas + 1}/{num_partes} com LLM02 ({llm02_provider})...",
                                    "percentage": int((step_counter / total_steps) * 100),
                                    "html_file": filename
                                })
                                
                                await manager.send_log({
                                    "level": "info",
                                    "message": f"🎨 LLM02 ({llm02_provider}): Gerando mapa {partes_concluidas + 1}/{num_partes}",
                                    "node": "gerar_mindmap"
                                })
                            
                            # === REVISÃO ===
                            elif node_name == "revisar_mindmap":
                                step_counter += 0.3
                                await manager.send_progress({
                                    "stage": "revisando",
                                    "current_step": int(step_counter),
                                    "total_steps": total_steps,
                                    "message": f"Revisando mapa {partes_concluidas + 1}/{num_partes} com LLM03 ({llm03_provider})...",
                                    "percentage": int((step_counter / total_steps) * 100),
                                    "html_file": filename
                                })
                                
                                await manager.send_log({
                                    "level": "info",
                                    "message": f"🔍 LLM03 ({llm03_provider}): Revisando mapa {partes_concluidas + 1}/{num_partes}",
                                    "node": "revisar_mindmap"
                                })
                            
                            # === SALVAMENTO ===
                            elif node_name == "salvar_mindmap":
                                step_counter = file_index * 5  # Completa os steps deste arquivo
                                await manager.send_progress({
                                    "stage": "salvando",
                                    "current_step": step_counter,
                                    "total_steps": total_steps,
                                    "message": f"Salvando arquivos .mmd...",
                                    "percentage": int((step_counter / total_steps) * 100),
                                    "html_file": filename
                                })
                                
                                await manager.send_log({
                                    "level": "success",
                                    "message": f"💾 Salvando mapas mentais...",
                                    "node": "salvar_mindmap"
                                })
                
                # Pega estado final
                final_state = await graph.aget_state(config)
                
                if final_state.values["status"] == "concluido":
                    arquivos_gerados = []
                    html_base = filename.replace('.html', '')
                    
                    for parte in final_state.values["partes_processadas"]:
                        mmd_filename = f"{html_base}_parte{parte['parte_numero']:02d}.mmd"
                        arquivos_gerados.append(mmd_filename)
                    
                    results.append({
                        "file": filename,
                        "success": True,
                        "parts": len(final_state.values["partes_processadas"]),
                        "files_generated": arquivos_gerados,
                        "logs": final_state.values["logs"]
                    })
                    
                    await manager.send_log({
                        "level": "success",
                        "message": f"✅ {filename}: {len(arquivos_gerados)} arquivo(s) gerado(s)",
                        "node": "completion"
                    })
                    
                else:
                    results.append({
                        "file": filename,
                        "success": False,
                        "error": final_state.values.get("erro_msg", "Erro desconhecido"),
                        "files_generated": []
                    })
                    
                    await manager.send_log({
                        "level": "error",
                        "message": f"❌ {filename}: {final_state.values.get('erro_msg', 'Erro')}",
                        "node": "error"
                    })
                    
            except Exception as e:
                logger.error(f"Erro ao processar {filename}: {str(e)}")
                results.append({
                    "file": filename,
                    "success": False,
                    "error": str(e),
                    "files_generated": []
                })
                
                await manager.send_log({
                    "level": "error",
                    "message": f"❌ Erro em {filename}: {str(e)}",
                    "node": "error"
                })
        
        # Progresso final
        await manager.send_progress({
            "stage": "salvando",
            "current_step": total_steps,
            "total_steps": total_steps,
            "message": "Processamento concluído!",
            "percentage": 100,
            "html_file": ""
        })
        
        # Coleta todos os arquivos gerados
        all_files_generated = []
        for result in results:
            if result["success"]:
                all_files_generated.extend(result.get("files_generated", []))
        
        # Notificação de conclusão
        await manager.send_completion({
            "success": True,
            "files_generated": all_files_generated,
            "total_files": len(all_files_generated),
            "output_dir": settings.output_dir
        })
        
        return {
            "status": "completed",
            "total_files": len(uploaded_files),
            "results": results,
            "files_generated": all_files_generated,
            "output_directory": settings.output_dir
        }
        
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        
        await manager.send_log({
            "level": "error",
            "message": f"❌ Erro crítico: {str(e)}",
            "node": "error"
        })
        
        raise HTTPException(500, str(e))


@router.get("/outputs")
async def list_outputs():
    """Lista arquivos .mmd gerados."""
    try:
        files = get_output_files()
        return {
            "files": [Path(f).name for f in files],
            "total": len(files),
            "directory": settings.output_dir
        }
    except Exception as e:
        raise HTTPException(500, str(e))