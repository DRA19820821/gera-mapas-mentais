# backend/agents/nodes/revisor_node.py
"""
Node do LLM03 - Revisor de Mapas Mentais.
VERSÃO CORRIGIDA - Fix loop infinito
"""

from ..state import MindmapState
from ...services.llm_factory import get_llm
from ...agents.prompts.revisor_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from ...utils.logger import logger
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Literal


# ============================================
# MODELS PARA STRUCTURED OUTPUT
# ============================================

class Problema(BaseModel):
    """Representa um problema encontrado no mapa."""
    categoria: Literal["sintaxe", "alucinacao", "cobertura", "precisao", "portugues"]
    gravidade: Literal["critica", "alta", "media", "baixa"]
    descricao: str
    localizacao: str


class AvaliacaoMapa(BaseModel):
    """Avaliação estruturada do mapa mental."""
    aprovado: bool
    nota_geral: float = Field(ge=0, le=10)
    problemas: List[Problema]
    sugestoes_melhoria: List[str]
    justificativa: str


# ============================================
# NODE FUNCTION
# ============================================

async def revisar_mindmap_node(state: MindmapState) -> MindmapState:
    """
    LLM03: Revisa o mapa mental gerado pelo LLM02.
    
    LÓGICA CORRIGIDA:
    - Avalia o mapa e decide aprovar ou rejeitar
    - Se APROVAR: marca parte como aprovada (vai para próxima parte)
    - Se REJEITAR: mantém parte como não aprovada (vai fazer retry)
    - Respeita limite de tentativas
    """
    
    logger.info("🔍 LLM03: Revisando mapa mental...")
    
    try:
        # ============================================
        # PEGA PARTE ATUAL
        # ============================================
        
        if not state["partes_processadas"]:
            logger.error("❌ Nenhuma parte para revisar!")
            state["status"] = "erro"
            state["erro_msg"] = "Nenhuma parte processada para revisão"
            return state
        
        # Pega a última parte (que acabou de ser gerada)
        parte_atual = state["partes_processadas"][-1]
        
        parte_num = parte_atual["parte_numero"]
        tentativa = state["tentativas_revisao"]
        max_tentativas = state["max_tentativas"]
        
        logger.info(
            f"📝 Revisando parte {parte_num} "
            f"(tentativa {tentativa}/{max_tentativas})"
        )
        
        # ============================================
        # OBTÉM LLM CONFIGURADO
        # ============================================
        
        llm = get_llm(
            provider=state["llm03_provider"],
            temperature=0.2,  # Mais determinístico para revisão
            max_tokens=12000
        )
        
        logger.debug(f"LLM configurado: {state['llm03_provider']}")
        
        # ============================================
        # PREPARA PROMPT
        # ============================================
        
        # Pega conteúdo original da parte
        divisao_original = state["divisoes"][parte_num - 1]
        conteudo_original = divisao_original.get("conteudo", "")
        
        user_prompt = USER_PROMPT_TEMPLATE.format(
            ramo_direito=state["ramo_direito"],
            topico=state["topico"],
            parte_titulo=parte_atual["parte_titulo"],
            conteudo_original=conteudo_original,
            mapa_gerado=parte_atual["mapa_gerado"],
            tentativa=tentativa,
            max_tentativas=max_tentativas
        )
        
        # ============================================
        # CHAMA LLM COM STRUCTURED OUTPUT
        # ============================================
        
        logger.info("📞 Chamando LLM03...")
        
        structured_llm = llm.with_structured_output(AvaliacaoMapa)
        
        avaliacao = await structured_llm.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ])
        
        logger.success(f"✅ LLM03 respondeu: {'APROVADO' if avaliacao.aprovado else 'REJEITADO'}")
        
        # ============================================
        # ATUALIZA PARTE COM AVALIAÇÃO
        # ============================================
        
        parte_atual["aprovado"] = avaliacao.aprovado
        parte_atual["nota_geral"] = avaliacao.nota_geral
        parte_atual["problemas"] = [p.model_dump() for p in avaliacao.problemas]
        parte_atual["sugestoes_melhoria"] = avaliacao.sugestoes_melhoria
        parte_atual["justificativa_revisao"] = avaliacao.justificativa
        
        # ============================================
        # LOG DETALHADO
        # ============================================
        
        if avaliacao.aprovado:
            logger.success(
                f"✅ Parte {parte_num} APROVADA! "
                f"(nota: {avaliacao.nota_geral:.1f}/10)"
            )
            
            state["status"] = "gerando"  # Próxima parte ou salvar
            
        else:
            logger.warning(
                f"⚠️ Parte {parte_num} REJEITADA "
                f"(nota: {avaliacao.nota_geral:.1f}/10, "
                f"{len(avaliacao.problemas)} problemas)"
            )
            
            # Mostra problemas principais
            for problema in avaliacao.problemas[:3]:  # Primeiros 3
                logger.warning(
                    f"   • [{problema.gravidade.upper()}] {problema.categoria}: "
                    f"{problema.descricao}"
                )
            
            # Verifica se ainda pode fazer retry
            if tentativa >= max_tentativas:
                logger.error(
                    f"❌ Esgotadas {max_tentativas} tentativas! "
                    "Auto-aprovando para continuar..."
                )
                # Auto-aprova forçadamente
                parte_atual["aprovado"] = True
                parte_atual["nota_geral"] = 5.0
                parte_atual["justificativa_revisao"] = (
                    f"Auto-aprovado após {max_tentativas} tentativas. "
                    f"Nota original: {avaliacao.nota_geral:.1f}. "
                    f"Problemas: {len(avaliacao.problemas)}"
                )
                state["status"] = "gerando"  # Próxima parte
            else:
                logger.info(f"🔄 Tentando novamente... ({tentativa}/{max_tentativas})")
                state["status"] = "gerando"  # Retry da mesma parte
        
        # ============================================
        # LOG ESTRUTURADO
        # ============================================
        
        state["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "node": "revisar_mindmap",
            "level": "success" if avaliacao.aprovado else "warning",
            "message": f"Parte {parte_num} {'aprovada' if avaliacao.aprovado else 'rejeitada'}",
            "data": {
                "llm": state["llm03_provider"],
                "parte": parte_num,
                "tentativa": tentativa,
                "aprovado": avaliacao.aprovado,
                "nota": avaliacao.nota_geral,
                "num_problemas": len(avaliacao.problemas),
                "problemas_criticos": len([p for p in avaliacao.problemas if p.gravidade == "critica"])
            }
        })
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Erro no LLM03: {str(e)}")
        logger.exception(e)
        
        # Em caso de erro, aprova automaticamente para não travar
        if state["partes_processadas"]:
            parte_atual = state["partes_processadas"][-1]
            parte_atual["aprovado"] = True
            parte_atual["nota_geral"] = 5.0
            parte_atual["justificativa_revisao"] = f"Auto-aprovado devido a erro no revisor: {str(e)}"
            
            logger.warning("⚠️ Auto-aprovando devido a erro no revisor")
        
        state["status"] = "gerando"
        
        state["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "node": "revisar_mindmap",
            "level": "error",
            "message": f"Erro no LLM03: {str(e)}",
            "data": {
                "llm": state["llm03_provider"],
                "error_type": type(e).__name__,
                "auto_approved": True
            }
        })
        
        return state