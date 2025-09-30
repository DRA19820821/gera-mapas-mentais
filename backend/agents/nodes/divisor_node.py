# backend/agents/nodes/divisor_node.py
"""
Node do LLM01 - Divisor de Conteúdo.

Responsável por analisar o conteúdo da fundamentação teórica
e decidir como dividi-lo em partes lógicas para geração de
mapas mentais.
"""

from ..state import MindmapState
from ...services.llm_factory import get_llm
from ...agents.prompts.divisor_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from ...utils.logger import logger
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List


# ============================================
# MODELS PARA STRUCTURED OUTPUT
# ============================================

class ParteDivisao(BaseModel):
    """Representa uma parte da divisão."""
    numero: int = Field(description="Número da parte (1, 2, 3...)")
    titulo: str = Field(description="Título descritivo da parte")
    conteudo_inicio: str = Field(description="Primeiras palavras do trecho")
    conteudo_fim: str = Field(description="Últimas palavras do trecho")
    estimativa_mapas: int = Field(description="Quantos mapas mentais para esta parte")


class DivisaoConteudo(BaseModel):
    """Resposta estruturada do LLM01."""
    num_partes: int = Field(ge=1, le=10, description="Número de partes (1-10)")
    justificativa: str = Field(description="Razão da divisão escolhida")
    partes: List[ParteDivisao] = Field(description="Lista das partes")


# ============================================
# NODE FUNCTION
# ============================================

async def dividir_conteudo_node(state: MindmapState) -> MindmapState:
    """
    LLM01: Analisa o conteúdo e decide como dividir.
    
    Este node usa o LLM configurado para:
    1. Analisar a fundamentação teórica
    2. Identificar subtemas ou seções lógicas
    3. Propor uma divisão em partes
    4. Estimar quantos mapas mentais por parte
    
    Args:
        state: Estado atual do grafo
    
    Returns:
        MindmapState: Estado atualizado com divisões propostas
    """
    
    logger.info("🤖 LLM01: Iniciando análise para divisão de conteúdo...")
    logger.info(f"📊 Usando provider: {state['llm01_provider']}")
    
    try:
        # ============================================
        # OBTÉM LLM CONFIGURADO
        # ============================================
        
        llm = get_llm(
            provider=state["llm01_provider"],
            temperature=0.3,  # Mais determinístico para análise
            max_tokens=2000
        )
        
        logger.debug(f"LLM configurado: {state['llm01_provider']}")
        
        # ============================================
        # PREPARA CONTEÚDO
        # ============================================
        
        # Limita tamanho do conteúdo para evitar exceder contexto
        fundamentacao = state["fundamentacao"]
        max_chars = 8000  # Aproximadamente 2000 tokens
        
        if len(fundamentacao) > max_chars:
            logger.warning(
                f"⚠️ Fundamentação muito longa ({len(fundamentacao)} chars). "
                f"Truncando para {max_chars} chars."
            )
            fundamentacao_truncada = fundamentacao[:max_chars] + "\n\n[...conteúdo truncado...]"
        else:
            fundamentacao_truncada = fundamentacao
        
        # ============================================
        # PREPARA PROMPT
        # ============================================
        
        user_prompt = USER_PROMPT_TEMPLATE.format(
            ramo_direito=state["ramo_direito"],
            topico=state["topico"],
            fundamentacao=fundamentacao_truncada
        )
        
        logger.debug(f"Prompt preparado ({len(user_prompt)} chars)")
        
        # ============================================
        # CHAMA LLM COM STRUCTURED OUTPUT
        # ============================================
        
        logger.info("📞 Chamando LLM01...")
        
        # LangChain 0.3.x com structured output
        structured_llm = llm.with_structured_output(DivisaoConteudo)
        
        response = await structured_llm.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ])
        
        logger.success(f"✅ LLM01 respondeu: {response.num_partes} partes")
        
        # ============================================
        # VALIDA RESPOSTA
        # ============================================
        
        if not response.partes:
            raise ValueError("LLM01 não retornou nenhuma parte na divisão")
        
        if len(response.partes) != response.num_partes:
            logger.warning(
                f"⚠️ Inconsistência: num_partes={response.num_partes} "
                f"mas len(partes)={len(response.partes)}"
            )
        
        # ============================================
        # PROCESSA DIVISÕES
        # ============================================
        
        divisoes_processadas = []
        
        for parte in response.partes:
            # Tenta localizar o conteúdo da parte na fundamentação
            conteudo_parte = _extrair_conteudo_parte(
                fundamentacao_completa=state["fundamentacao"],
                inicio=parte.conteudo_inicio,
                fim=parte.conteudo_fim
            )
            
            divisoes_processadas.append({
                "numero": parte.numero,
                "titulo": parte.titulo,
                "conteudo": conteudo_parte,
                "estimativa_mapas": parte.estimativa_mapas,
                "conteudo_inicio": parte.conteudo_inicio,
                "conteudo_fim": parte.conteudo_fim
            })
            
            logger.info(
                f"  📝 Parte {parte.numero}: {parte.titulo} "
                f"({len(conteudo_parte)} chars, ~{parte.estimativa_mapas} mapas)"
            )
        
        # ============================================
        # ATUALIZA ESTADO
        # ============================================
        
        state["divisoes"] = divisoes_processadas
        state["status"] = "gerando"
        state["partes_processadas"] = []  # Inicializa lista vazia
        
        # Log estruturado
        state["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "node": "dividir_conteudo",
            "level": "success",
            "message": f"Conteúdo dividido em {response.num_partes} partes",
            "data": {
                "llm": state["llm01_provider"],
                "num_partes": response.num_partes,
                "justificativa": response.justificativa,
                "total_mapas_estimados": sum(p.estimativa_mapas for p in response.partes)
            }
        })
        
        logger.success(
            f"✅ Divisão concluída: {response.num_partes} partes, "
            f"~{sum(p.estimativa_mapas for p in response.partes)} mapas estimados"
        )
        logger.info(f"📋 Justificativa: {response.justificativa}")
        
        return state
    
    except Exception as e:
        logger.error(f"❌ Erro no LLM01: {str(e)}")
        logger.exception(e)
        
        state["status"] = "erro"
        state["erro_msg"] = f"Erro na divisão de conteúdo: {str(e)}"
        
        state["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "node": "dividir_conteudo",
            "level": "error",
            "message": f"Erro no LLM01: {str(e)}",
            "data": {
                "llm": state["llm01_provider"],
                "error_type": type(e).__name__
            }
        })
        
        return state


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def _extrair_conteudo_parte(
    fundamentacao_completa: str,
    inicio: str,
    fim: str
) -> str:
    """
    Tenta extrair o conteúdo de uma parte específica.
    
    Localiza o texto entre as strings de início e fim.
    Se não encontrar, retorna a fundamentação completa.
    
    Args:
        fundamentacao_completa: Texto completo da fundamentação
        inicio: Primeiras palavras da parte
        fim: Últimas palavras da parte
    
    Returns:
        str: Conteúdo extraído da parte
    """
    
    # Normaliza strings para busca
    inicio_limpo = inicio.strip()[:50]  # Primeiros 50 chars
    fim_limpo = fim.strip()[:50]
    
    try:
        # Tenta encontrar posições
        idx_inicio = fundamentacao_completa.lower().find(inicio_limpo.lower())
        idx_fim = fundamentacao_completa.lower().find(fim_limpo.lower())
        
        if idx_inicio != -1 and idx_fim != -1 and idx_fim > idx_inicio:
            # Extrai o trecho
            conteudo = fundamentacao_completa[idx_inicio:idx_fim + len(fim_limpo)]
            logger.debug(f"Conteúdo extraído: {len(conteudo)} chars")
            return conteudo
        else:
            # Não conseguiu localizar, retorna fundamentação completa
            logger.warning(
                "⚠️ Não foi possível localizar trecho específico. "
                "Usando fundamentação completa."
            )
            return fundamentacao_completa
    
    except Exception as e:
        logger.warning(f"⚠️ Erro ao extrair conteúdo da parte: {e}")
        return fundamentacao_completa