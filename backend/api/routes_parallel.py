# backend/api/routes_parallel.py
"""
Rotas da API com processamento PARALELO.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
import asyncio
from pathlib import Path

from ..agents.graph_parallel import (
    execute_graph_parallel,
    processar_multiplos_htmls_paralelo
)
from ..services.file_manager import save_uploaded_html
from ..api.websocket import manager
from ..utils.logger import logger
from ..core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/process-parallel")
async def process_htmls_parallel(
    files: List[UploadFile] = File(...),
    llm01_provider: str = Form(...),
    llm02_provider: str = Form(...),
    llm03_provider: str = Form(...),
    max_workers_per_file: int = Form(3),  # Partes por arquivo
    max_concurrent_files: int = Form(2)    # Arquivos simultâneos
):
    """
    Processa arquivos HTML com PARALELIZAÇÃO.
    
    Configurações de performance:
    - max_workers_per_file: Quantas partes processar simultaneamente por arquivo (1-5)
    - max_concurrent_files: Quantos arquivos processar simultaneamente (1-3)
    
    Exemplo:
    - 1 arquivo com 6 partes, max_workers=3: processa 3 partes por vez
    - 3 arquivos, max_concurrent_files=2: processa 2 arquivos por vez
    """
    
    try:
        logger.info(f"📥 Recebidos {len(files)} arquivo(s) para processamento PARALELO")
        
        # Valida providers
        valid_providers = ["openai", "anthropic", "gemini", "deepseek"]
        for provider in [llm01_provider, llm02_provider, llm03_provider]:
            if provider not in valid_providers:
                raise HTTPException(400, f"Provider inválido: {provider}")
        
        # Valida configurações de paralelização
        if not (1 <= max_workers_per_file <= 5):
            raise HTTPException(400, "max_workers_per_file deve estar entre 1 e 5")
        
        if not (1 <= max_concurrent_files <= 3):
            raise HTTPException(400, "max_concurrent_files deve estar entre 1 e 3")
        
        # Salva arquivos
        uploaded_files = []
        for file in files:
            if not file.filename.endswith('.html'):
                continue
            
            content = await file.read()
            save_uploaded_html(content, file.filename)
            uploaded_files.append(file.filename)
            logger.info(f"💾 Arquivo salvo: {file.filename}")
        
        if not uploaded_files:
            raise HTTPException(400, "Nenhum arquivo HTML válido encontrado")
        
        # Progresso inicial
        await manager.send_progress({
            "stage": "parsing",
            "current_step": 0,
            "total_steps": len(uploaded_files) * 4,  # 4 etapas: parse, divide, gera+revisa, salva
            "message": f"Iniciando processamento PARALELO de {len(uploaded_files)} arquivo(s)...",
            "percentage": 0,
            "html_file": ""
        })
        
        await manager.send_log({
            "level": "info",
            "message": (
                f"🚀 Modo PARALELO ativado:\n"
                f"   📁 {max_concurrent_files} arquivo(s) simultâneo(s)\n"
                f"   📝 {max_workers_per_file} parte(s) simultânea(s) por arquivo"
            ),
            "node": "parallel_config"
        })
        
        # ============================================
        # PROCESSAMENTO PARALELO
        # ============================================
        
        resultados = await processar_multiplos_htmls_paralelo(
            html_files=uploaded_files,
            llm01_provider=llm01_provider,
            llm02_provider=llm02_provider,
            llm03_provider=llm03_provider,
            max_tentativas=settings.max_tentativas_revisao,
            max_workers_por_arquivo=max_workers_per_file,
            max_arquivos_simultaneos=max_concurrent_files
        )
        
        # ============================================
        # PROCESSA RESULTADOS
        # ============================================
        
        results = []
        all_files_generated = []
        
        for i, (filename, state) in enumerate(zip(uploaded_files, resultados)):
            
            # Progresso
            current_step = (i + 1) * 4
            await manager.send_progress({
                "stage": "salvando",
                "current_step": current_step,
                "total_steps": len(uploaded_files) * 4,
                "message": f"Finalizado: {filename}",
                "percentage": int((current_step / (len(uploaded_files) * 4)) * 100),
                "html_file": filename
            })
            
            # Verifica se houve erro
            if isinstance(state, Exception):
                logger.error(f"❌ {filename}: {state}")
                results.append({
                    "file": filename,
                    "success": False,
                    "error": str(state),
                    "files_generated": []
                })
                
                await manager.send_log({
                    "level": "error",
                    "message": f"❌ {filename}: {str(state)}",
                    "node": "error"
                })
                continue
            
            # Sucesso
            if state["status"] in ["concluido", "parcial"]:
                arquivos_gerados = []
                html_base = filename.replace('.html', '')
                
                for parte in state["partes_processadas"]:
                    if parte.get("aprovado"):
                        mmd_filename = f"{html_base}_parte{parte['parte_numero']:02d}.mmd"
                        arquivos_gerados.append(mmd_filename)
                
                all_files_generated.extend(arquivos_gerados)
                
                results.append({
                    "file": filename,
                    "success": True,
                    "parts": len(state["partes_processadas"]),
                    "files_generated": arquivos_gerados,
                    "logs": state.get("logs", [])
                })
                
                await manager.send_log({
                    "level": "success",
                    "message": (
                        f"✅ {filename}: {len(arquivos_gerados)} arquivo(s) gerado(s) "
                        f"em {len(state['partes_processadas'])} parte(s)"
                    ),
                    "node": "completion"
                })
            else:
                # Erro
                results.append({
                    "file": filename,
                    "success": False,
                    "error": state.get("erro_msg", "Erro desconhecido"),
                    "files_generated": []
                })
                
                await manager.send_log({
                    "level": "error",
                    "message": f"❌ {filename}: {state.get('erro_msg', 'Erro')}",
                    "node": "error"
                })
        
        # ============================================
        # CONCLUSÃO
        # ============================================
        
        await manager.send_progress({
            "stage": "salvando",
            "current_step": len(uploaded_files) * 4,
            "total_steps": len(uploaded_files) * 4,
            "message": "Processamento paralelo concluído!",
            "percentage": 100,
            "html_file": ""
        })
        
        await manager.send_completion({
            "success": True,
            "files_generated": all_files_generated,
            "total_files": len(all_files_generated),
            "output_dir": settings.output_dir
        })
        
        return {
            "status": "completed",
            "mode": "parallel",
            "total_files": len(uploaded_files),
            "results": results,
            "files_generated": all_files_generated,
            "output_directory": settings.output_dir,
            "performance": {
                "max_workers_per_file": max_workers_per_file,
                "max_concurrent_files": max_concurrent_files
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento paralelo: {str(e)}")
        
        await manager.send_log({
            "level": "error",
            "message": f"❌ Erro crítico: {str(e)}",
            "node": "error"
        })
        
        raise HTTPException(500, str(e))


@router.post("/process-benchmark")
async def benchmark_processing(
    files: List[UploadFile] = File(...),
    llm01_provider: str = Form(...),
    llm02_provider: str = Form(...),
    llm03_provider: str = Form(...)
):
    """
    Compara desempenho: Sequencial vs Paralelo.
    
    Útil para testes de performance.
    """
    import time
    
    try:
        # Salva arquivos
        uploaded_files = []
        for file in files:
            if file.filename.endswith('.html'):
                content = await file.read()
                save_uploaded_html(content, file.filename)
                uploaded_files.append(file.filename)
        
        # ============================================
        # TESTE SEQUENCIAL
        # ============================================
        
        logger.info("⏱️ Iniciando teste SEQUENCIAL...")
        start_seq = time.time()
        
        from ..agents.graph import execute_graph
        
        results_seq = []
        for filename in uploaded_files:
            result = await execute_graph(
                html_filename=filename,
                llm01_provider=llm01_provider,
                llm02_provider=llm02_provider,
                llm03_provider=llm03_provider
            )
            results_seq.append(result)
        
        time_seq = time.time() - start_seq
        logger.info(f"⏱️ Sequencial: {time_seq:.2f}s")
        
        # ============================================
        # TESTE PARALELO
        # ============================================
        
        logger.info("⏱️ Iniciando teste PARALELO...")
        start_par = time.time()
        
        results_par = await processar_multiplos_htmls_paralelo(
            html_files=uploaded_files,
            llm01_provider=llm01_provider,
            llm02_provider=llm02_provider,
            llm03_provider=llm03_provider,
            max_workers_por_arquivo=3,
            max_arquivos_simultaneos=2
        )
        
        time_par = time.time() - start_par
        logger.info(f"⏱️ Paralelo: {time_par:.2f}s")
        
        # ============================================
        # ANÁLISE
        # ============================================
        
        speedup = time_seq / time_par if time_par > 0 else 0
        economia = ((time_seq - time_par) / time_seq * 100) if time_seq > 0 else 0
        
        return {
            "benchmark": {
                "files": len(uploaded_files),
                "sequential_time": round(time_seq, 2),
                "parallel_time": round(time_par, 2),
                "speedup": round(speedup, 2),
                "time_saved": round(time_seq - time_par, 2),
                "efficiency_gain": f"{economia:.1f}%"
            },
            "results": {
                "sequential": [
                    {
                        "file": f,
                        "parts": len(r.get("partes_processadas", []))
                    } for f, r in zip(uploaded_files, results_seq)
                ],
                "parallel": [
                    {
                        "file": f,
                        "parts": len(r.get("partes_processadas", []))
                    } for f, r in zip(uploaded_files, results_par)
                ]
            }
        }
        
    except Exception as e:
        raise HTTPException(500, str(e))