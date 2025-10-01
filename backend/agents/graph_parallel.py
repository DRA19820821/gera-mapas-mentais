# backend/agents/graph_parallel.py
"""
Versão PARALELIZADA do grafo LangGraph.
Processa múltiplas partes simultaneamente para ganho de performance.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Literal
import asyncio
from datetime import datetime

from .state import MindmapState
from .nodes.parser_node import parse_html_node
from .nodes.divisor_node import dividir_conteudo_node
from .nodes.salvar_node import salvar_mindmap_node
from ..services.llm_factory import get_llm
from ..agents.prompts.gerador_prompts import SYSTEM_PROMPT as GERADOR_SYSTEM
from ..agents.prompts.gerador_prompts import USER_PROMPT_TEMPLATE as GERADOR_TEMPLATE
from ..agents.prompts.revisor_prompts import SYSTEM_PROMPT as REVISOR_SYSTEM
from ..agents.prompts.revisor_prompts import USER_PROMPT_TEMPLATE as REVISOR_TEMPLATE
from ..utils.logger import logger
from pydantic import BaseModel, Field
from typing import List
import re


# ============================================
# MODELS PARA STRUCTURED OUTPUT (Revisor)
# ============================================

class Problema(BaseModel):
    categoria: str
    gravidade: str
    descricao: str
    localizacao: str

class AvaliacaoMapa(BaseModel):
    aprovado: bool
    nota_geral: float = Field(ge=0, le=10)
    problemas: List[Problema]
    sugestoes_melhoria: List[str]
    justificativa: str


# ============================================
# FUNÇÕES AUXILIARES PARA PROCESSAMENTO PARALELO
# ============================================

async def processar_parte_completa(
    parte_info: dict,
    state: MindmapState,
    parte_index: int,
    max_tentativas: int = 3
) -> dict:
    """
    Processa uma parte completa: geração + revisão com retry.
    
    Esta função é chamada em paralelo para múltiplas partes.
    """
    parte_numero = parte_index + 1
    
    logger.info(f"🎯 [Parte {parte_numero}] Iniciando processamento: {parte_info['titulo']}")
    
    # LLMs
    llm_gerador = get_llm(
        provider=state["llm02_provider"],
        temperature=0.4,
        max_tokens=12000
    )
    
    llm_revisor = get_llm(
        provider=state["llm03_provider"],
        temperature=0.2,
        max_tokens=12000
    )
    
    structured_revisor = llm_revisor.with_structured_output(AvaliacaoMapa)
    
    # Loop de tentativas
    for tentativa in range(1, max_tentativas + 1):
        try:
            logger.info(f"📝 [Parte {parte_numero}] Tentativa {tentativa}/{max_tentativas}")
            
            # ============================================
            # GERAÇÃO (LLM02)
            # ============================================
            
            logger.info(f"🎨 [Parte {parte_numero}] Gerando mapa mental...")
            
            prompt_gerador = GERADOR_TEMPLATE.format(
                ramo_direito=state["ramo_direito"],
                topico=state["topico"],
                parte_titulo=parte_info["titulo"],
                conteudo_parte=parte_info.get("conteudo", "")
            )
            
            response_gerador = await llm_gerador.ainvoke([
                {"role": "system", "content": GERADOR_SYSTEM},
                {"role": "user", "content": prompt_gerador}
            ])
            
            mapa_gerado = response_gerador.content
            
            # Limpa código Mermaid
            mapa_gerado = re.sub(r'^```mermaid\s*', '', mapa_gerado, flags=re.MULTILINE)
            mapa_gerado = re.sub(r'\s*```$', '', mapa_gerado, flags=re.MULTILINE)
            mapa_gerado = mapa_gerado.strip()
            
            logger.success(f"✅ [Parte {parte_numero}] Mapa gerado ({len(mapa_gerado)} chars)")
            
            # ============================================
            # REVISÃO (LLM03)
            # ============================================
            
            logger.info(f"🔍 [Parte {parte_numero}] Revisando mapa...")
            
            prompt_revisor = REVISOR_TEMPLATE.format(
                ramo_direito=state["ramo_direito"],
                topico=state["topico"],
                parte_titulo=parte_info["titulo"],
                conteudo_original=parte_info.get("conteudo", ""),
                mapa_gerado=mapa_gerado,
                tentativa=tentativa,
                max_tentativas=max_tentativas
            )
            
            avaliacao = await structured_revisor.ainvoke([
                {"role": "system", "content": REVISOR_SYSTEM},
                {"role": "user", "content": prompt_revisor}
            ])
            
            logger.success(
                f"{'✅' if avaliacao.aprovado else '⚠️'} [Parte {parte_numero}] "
                f"{'APROVADO' if avaliacao.aprovado else 'REJEITADO'} "
                f"(nota: {avaliacao.nota_geral:.1f}/10)"
            )
            
            # ============================================
            # DECISÃO: APROVAR OU RETRY
            # ============================================
            
            if avaliacao.aprovado:
                # SUCESSO!
                return {
                    "parte_numero": parte_numero,
                    "parte_titulo": parte_info["titulo"],
                    "mapa_gerado": mapa_gerado,
                    "aprovado": True,
                    "nota_geral": avaliacao.nota_geral,
                    "tentativas": tentativa,
                    "problemas": [p.model_dump() for p in avaliacao.problemas],
                    "sugestoes_melhoria": avaliacao.sugestoes_melhoria,
                    "justificativa_revisao": avaliacao.justificativa
                }
            
            else:
                # Rejeitado - mostra problemas
                logger.warning(
                    f"⚠️ [Parte {parte_numero}] Rejeitado: "
                    f"{len(avaliacao.problemas)} problema(s)"
                )
                
                for problema in avaliacao.problemas[:3]:
                    logger.warning(
                        f"   • [{problema.gravidade.upper()}] "
                        f"{problema.categoria}: {problema.descricao}"
                    )
                
                # Se não é a última tentativa, continua o loop
                if tentativa < max_tentativas:
                    logger.info(f"🔄 [Parte {parte_numero}] Tentando novamente...")
                    await asyncio.sleep(1)  # Pequeno delay entre tentativas
                    continue
                
                # Última tentativa - auto-aprova
                logger.error(
                    f"❌ [Parte {parte_numero}] Esgotadas {max_tentativas} tentativas. "
                    "Auto-aprovando..."
                )
                
                return {
                    "parte_numero": parte_numero,
                    "parte_titulo": parte_info["titulo"],
                    "mapa_gerado": mapa_gerado,
                    "aprovado": True,  # Auto-aprovado
                    "nota_geral": 5.0,
                    "tentativas": tentativa,
                    "problemas": [p.model_dump() for p in avaliacao.problemas],
                    "sugestoes_melhoria": avaliacao.sugestoes_melhoria,
                    "justificativa_revisao": (
                        f"Auto-aprovado após {max_tentativas} tentativas. "
                        f"Nota original: {avaliacao.nota_geral:.1f}"
                    )
                }
        
        except Exception as e:
            logger.error(f"❌ [Parte {parte_numero}] Erro na tentativa {tentativa}: {e}")
            
            if tentativa == max_tentativas:
                # Última tentativa - retorna erro
                return {
                    "parte_numero": parte_numero,
                    "parte_titulo": parte_info["titulo"],
                    "mapa_gerado": "",
                    "aprovado": False,
                    "nota_geral": 0.0,
                    "tentativas": tentativa,
                    "problemas": [],
                    "sugestoes_melhoria": [],
                    "justificativa_revisao": f"Erro após {tentativa} tentativas: {str(e)}"
                }
            
            await asyncio.sleep(2)  # Delay maior em caso de erro
            continue


async def processar_partes_paralelo(
    state: MindmapState,
    max_workers: int = 3
) -> MindmapState:
    """
    Processa múltiplas partes em paralelo.
    
    Args:
        state: Estado atual
        max_workers: Máximo de partes processadas simultaneamente
                     (para não sobrecarregar APIs)
    """
    
    divisoes = state["divisoes"]
    total_partes = len(divisoes)
    
    logger.info(
        f"🚀 Iniciando processamento PARALELO de {total_partes} parte(s) "
        f"(máx {max_workers} simultâneas)..."
    )
    
    # Cria tasks para cada parte
    tasks = []
    for i, parte_info in enumerate(divisoes):
        task = processar_parte_completa(
            parte_info=parte_info,
            state=state,
            parte_index=i,
            max_tentativas=state["max_tentativas"]
        )
        tasks.append(task)
    
    # Processa em lotes (semaphore para limitar concorrência)
    semaphore = asyncio.Semaphore(max_workers)
    
    async def task_with_semaphore(task):
        async with semaphore:
            return await task
    
    # Executa todas as tasks
    logger.info(f"⏳ Aguardando conclusão de {total_partes} parte(s)...")
    
    resultados = await asyncio.gather(
        *[task_with_semaphore(task) for task in tasks],
        return_exceptions=True  # Não para se uma falhar
    )
    
    # Processa resultados
    partes_processadas = []
    partes_com_erro = []
    
    for i, resultado in enumerate(resultados):
        if isinstance(resultado, Exception):
            logger.error(f"❌ Parte {i+1} falhou com exceção: {resultado}")
            partes_com_erro.append(i+1)
        else:
            partes_processadas.append(resultado)
            
            if resultado["aprovado"]:
                logger.success(
                    f"✅ Parte {resultado['parte_numero']}: "
                    f"{resultado['parte_titulo']} "
                    f"(nota: {resultado['nota_geral']:.1f}, "
                    f"{resultado['tentativas']} tentativa(s))"
                )
    
    # Atualiza estado
    state["partes_processadas"] = sorted(partes_processadas, key=lambda x: x["parte_numero"])
    state["status"] = "concluido" if not partes_com_erro else "parcial"
    
    if partes_com_erro:
        state["erro_msg"] = f"Partes com erro: {partes_com_erro}"
    
    # Log final
    logger.success(
        f"🎉 Processamento paralelo concluído!\n"
        f"   ✅ Sucesso: {len(partes_processadas)}/{total_partes}\n"
        f"   ❌ Erros: {len(partes_com_erro)}/{total_partes}"
    )
    
    return state


# ============================================
# GRAFO SIMPLIFICADO (SEM LANGGRAPH PARA PARTES)
# ============================================

async def execute_graph_parallel(
    html_filename: str,
    llm01_provider: str,
    llm02_provider: str,
    llm03_provider: str,
    max_tentativas: int = 3,
    max_workers: int = 3
) -> dict:
    """
    Executa processamento PARALELO.
    
    Fluxo:
    1. Parse HTML (sequencial)
    2. Divide conteúdo (sequencial - LLM01)
    3. Processa partes (PARALELO - LLM02 + LLM03)
    4. Salva (sequencial)
    
    Args:
        max_workers: Máximo de partes processadas simultaneamente
    """
    
    logger.info(f"🚀 Iniciando processamento PARALELO: {html_filename}")
    logger.info(f"⚙️ Max workers: {max_workers}")
    
    # Estado inicial
    state: MindmapState = {
        "html_filename": html_filename,
        "ramo_direito": "",
        "topico": "",
        "fundamentacao": "",
        "divisoes": [],
        "partes_processadas": [],
        "tentativas_revisao": 0,
        "max_tentativas": max_tentativas,
        "status": "parsing",
        "erro_msg": None,
        "llm01_provider": llm01_provider,
        "llm02_provider": llm02_provider,
        "llm03_provider": llm03_provider,
        "logs": []
    }
    
    try:
        # ============================================
        # 1. PARSE (Sequencial)
        # ============================================
        
        logger.info("📄 1/4: Parsing HTML...")
        state = await parse_html_node(state)
        
        if state["status"] == "erro":
            raise Exception(state["erro_msg"])
        
        # ============================================
        # 2. DIVISÃO (Sequencial - LLM01)
        # ============================================
        
        logger.info("✂️ 2/4: Dividindo conteúdo...")
        state = await dividir_conteudo_node(state)
        
        if state["status"] == "erro":
            raise Exception(state["erro_msg"])
        
        num_partes = len(state["divisoes"])
        logger.info(f"📊 Conteúdo dividido em {num_partes} parte(s)")
        
        # ============================================
        # 3. PROCESSAMENTO PARALELO (LLM02 + LLM03)
        # ============================================
        
        logger.info("🚀 3/4: Processando partes EM PARALELO...")
        state = await processar_partes_paralelo(state, max_workers=max_workers)
        
        if state["status"] == "erro":
            raise Exception(state["erro_msg"])
        
        # ============================================
        # 4. SALVAMENTO (Sequencial)
        # ============================================
        
        logger.info("💾 4/4: Salvando arquivos...")
        state = await salvar_mindmap_node(state)
        
        logger.success(f"✅ Processamento concluído: {html_filename}")
        
        return state
    
    except Exception as e:
        logger.error(f"❌ Erro no processamento: {str(e)}")
        state["status"] = "erro"
        state["erro_msg"] = str(e)
        return state


# ============================================
# PROCESSAMENTO DE MÚLTIPLOS ARQUIVOS EM PARALELO
# ============================================

async def processar_multiplos_htmls_paralelo(
    html_files: List[str],
    llm01_provider: str,
    llm02_provider: str,
    llm03_provider: str,
    max_tentativas: int = 3,
    max_workers_por_arquivo: int = 3,
    max_arquivos_simultaneos: int = 2
) -> List[dict]:
    """
    Processa múltiplos HTMLs em paralelo.
    
    Args:
        max_workers_por_arquivo: Quantas partes processar em paralelo por arquivo
        max_arquivos_simultaneos: Quantos arquivos processar simultaneamente
    """
    
    logger.info(
        f"🚀 Processando {len(html_files)} arquivo(s) em paralelo\n"
        f"   📁 Max arquivos simultâneos: {max_arquivos_simultaneos}\n"
        f"   📝 Max partes simultâneas por arquivo: {max_workers_por_arquivo}"
    )
    
    semaphore = asyncio.Semaphore(max_arquivos_simultaneos)
    
    async def process_with_semaphore(filename):
        async with semaphore:
            return await execute_graph_parallel(
                html_filename=filename,
                llm01_provider=llm01_provider,
                llm02_provider=llm02_provider,
                llm03_provider=llm03_provider,
                max_tentativas=max_tentativas,
                max_workers=max_workers_por_arquivo
            )
    
    resultados = await asyncio.gather(
        *[process_with_semaphore(f) for f in html_files],
        return_exceptions=True
    )
    
    return resultados