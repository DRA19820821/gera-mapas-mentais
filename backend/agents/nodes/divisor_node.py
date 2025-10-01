# backend/agents/nodes/divisor_node.py
"""
Node do LLM01 - Divisor de Conteúdo.
VERSÃO AJUSTADA - Retorna conteúdo completo de cada parte
"""

from ..state import MindmapState
from ...services.llm_factory import get_llm
from ...agents.prompts.divisor_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from ...utils.logger import logger
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List


# ============================================
# MODELS PARA STRUCTURED OUTPUT (AJUSTADO)
# ============================================

class ParteDivisao(BaseModel):
    """Representa uma parte da divisão - AGORA COM CONTEÚDO COMPLETO."""
    numero: int = Field(description="Número da parte (1, 2, 3...)")
    titulo: str = Field(description="Título descritivo e específico da parte")
    conteudo_completo: str = Field(description="Texto completo da parte (copiado da fundamentação)")
    estimativa_mapas: int = Field(ge=1, le=3, description="Quantos mapas mentais para esta parte (1-3)")


class DivisaoConteudo(BaseModel):
    """Resposta estruturada do LLM01."""
    num_partes: int = Field(ge=2, le=10, description="Número de partes (2-10)")
    justificativa: str = Field(description="Razão da divisão escolhida")
    partes: List[ParteDivisao] = Field(description="Lista das partes com conteúdo completo")


# ============================================
# NODE FUNCTION
# ============================================

async def dividir_conteudo_node(state: MindmapState) -> MindmapState:
    """
    LLM01: Analisa o conteúdo e divide em partes.
    
    NOVA VERSÃO: O LLM retorna o conteúdo completo de cada parte,
    não apenas marcadores de início/fim.
    
    Args:
        state: Estado atual do grafo
    
    Returns:
        MindmapState: Estado atualizado com divisões (cada uma com conteúdo completo)
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
            max_tokens=12000   # Aumentado para incluir conteúdo completo na resposta
        )
        
        logger.debug(f"LLM configurado: {state['llm01_provider']}")
        
        # ============================================
        # PREPARA CONTEÚDO
        # ============================================
        
        fundamentacao = state["fundamentacao"]
        
        # Ajusta limite se necessário (alguns LLMs têm limite menor)
        max_chars_input = 15000  # ~4000 tokens
        
        if len(fundamentacao) > max_chars_input:
            logger.warning(
                f"⚠️ Fundamentação muito longa ({len(fundamentacao)} chars). "
                f"Truncando para {max_chars_input} chars."
            )
            fundamentacao_para_analise = fundamentacao[:max_chars_input] + "\n\n[...conteúdo truncado...]"
        else:
            fundamentacao_para_analise = fundamentacao
        
        logger.info(f"📏 Tamanho da fundamentação: {len(fundamentacao_para_analise)} chars")
        
        # ============================================
        # PREPARA PROMPT
        # ============================================
        
        user_prompt = USER_PROMPT_TEMPLATE.format(
            ramo_direito=state["ramo_direito"],
            topico=state["topico"],
            fundamentacao=fundamentacao_para_analise
        )
        
        logger.debug(f"Prompt preparado ({len(user_prompt)} chars)")
        
        # ============================================
        # CHAMA LLM COM STRUCTURED OUTPUT
        # ============================================
        
        logger.info("📞 Chamando LLM01...")
        
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
        
        # Valida que cada parte tem conteúdo
        for i, parte in enumerate(response.partes, 1):
            if not parte.conteudo_completo or len(parte.conteudo_completo) < 50:
                logger.error(
                    f"❌ Parte {i} tem conteúdo insuficiente ({len(parte.conteudo_completo)} chars)"
                )
                raise ValueError(
                    f"Parte {i} não tem conteúdo adequado. "
                    "O LLM deve retornar o texto completo de cada parte."
                )
        
        # ============================================
        # PROCESSA DIVISÕES
        # ============================================
        
        divisoes_processadas = []
        
        for parte in response.partes:
            divisoes_processadas.append({
                "numero": parte.numero,
                "titulo": parte.titulo,
                "conteudo": parte.conteudo_completo,  # ✅ Agora é o conteúdo completo!
                "estimativa_mapas": parte.estimativa_mapas
            })
            
            logger.info(
                f"  📝 Parte {parte.numero}: {parte.titulo}\n"
                f"     └─ Tamanho: {len(parte.conteudo_completo)} chars, "
                f"~{parte.estimativa_mapas} mapa(s)"
            )
            
            # Preview do conteúdo (primeiros 100 chars)
            preview = parte.conteudo_completo[:100].replace('\n', ' ')
            logger.debug(f"     └─ Preview: {preview}...")
        
        # ============================================
        # VALIDAÇÃO FINAL
        # ============================================
        
        total_chars_partes = sum(len(p["conteudo"]) for p in divisoes_processadas)
        logger.info(f"📊 Total de caracteres nas partes: {total_chars_partes}")
        
        # Verifica se a soma das partes é razoável em relação ao original
        if total_chars_partes < len(fundamentacao) * 0.5:
            logger.warning(
                f"⚠️ As partes somam apenas {total_chars_partes} chars, "
                f"mas o original tem {len(fundamentacao)} chars. "
                "Pode haver perda de conteúdo."
            )
            
        # Após processar as divisões, logo antes de "ATUALIZA ESTADO"
        for i, divisao in enumerate(divisoes_processadas, 1):
            logger.debug(f"\n{'='*60}")
            logger.debug(f"PARTE {i}: {divisao['titulo']}")
            logger.debug(f"Tamanho: {len(divisao['conteudo'])} chars")
            logger.debug(f"Conteúdo completo:")
            logger.debug(divisao['conteudo'][:300])  # Primeiros 300 chars
            logger.debug(f"{'='*60}\n")
        
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
                "total_mapas_estimados": sum(p.estimativa_mapas for p in response.partes),
                "total_chars_partes": total_chars_partes,
                "tamanho_medio_parte": total_chars_partes // response.num_partes
            }
        })
        
        logger.success(
            f"✅ Divisão concluída: {response.num_partes} partes, "
            f"~{sum(p.estimativa_mapas for p in response.partes)} mapas estimados\n"
            f"📋 Justificativa: {response.justificativa}"
        )
        
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