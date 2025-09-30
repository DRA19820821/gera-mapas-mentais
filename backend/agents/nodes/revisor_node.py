# backend/agents/nodes/revisor_node.py
from ..state import MindmapState
from ...services.llm_factory import get_llm
from ...agents.prompts.revisor_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from ...utils.logger import logger
from pydantic import BaseModel, Field
from typing import List, Literal

class Problema(BaseModel):
    categoria: Literal["sintaxe", "alucinacao", "cobertura", "precisao", "portugues"]
    gravidade: Literal["critica", "alta", "media", "baixa"]
    descricao: str
    localizacao: str

class AvaliacaoMapa(BaseModel):
    aprovado: bool
    nota_geral: float = Field(ge=0, le=10)
    problemas: List[Problema]
    sugestoes_melhoria: List[str]
    justificativa: str

async def revisar_mindmap_node(state: MindmapState) -> MindmapState:
    """
    LLM03: Revisa o mapa mental gerado pelo LLM02.
    """
    logger.info("LLM03: Revisando mapa mental...")
    
    try:
        # Pega a última parte processada
        parte_atual = state["partes_processadas"][-1]
        
        # Incrementa tentativas
        state["tentativas_revisao"] += 1
        parte_atual["tentativas"] = state["tentativas_revisao"]
        
        logger.info(f"Revisão tentativa {state['tentativas_revisao']}/{state['max_tentativas']}")
        
        # Obtém LLM configurado
        llm = get_llm(
            provider=state["llm03_provider"],
            temperature=0.2,  # Mais determinístico para revisão
            max_tokens=2000
        )
        
        # Structured output
        structured_llm = llm.with_structured_output(AvaliacaoMapa)
        
        # Prepara prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            ramo_direito=state["ramo_direito"],
            topico=state["topico"],
            parte_titulo=parte_atual["parte_titulo"],
            conteudo_original=state["divisoes"][parte_atual["parte_numero"]-1].get("conteudo", ""),
            mapa_gerado=parte_atual["mapa_gerado"],
            tentativa=state["tentativas_revisao"],
            max_tentativas=state["max_tentativas"]
        )
        
        # Chama LLM
        avaliacao = await structured_llm.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ])
        
        # Atualiza parte com avaliação
        parte_atual["aprovado"] = avaliacao.aprovado
        parte_atual["nota_geral"] = avaliacao.nota_geral
        parte_atual["problemas"] = [p.model_dump() for p in avaliacao.problemas]
        parte_atual["sugestoes_melhoria"] = avaliacao.sugestoes_melhoria
        parte_atual["justificativa_revisao"] = avaliacao.justificativa
        
        state["logs"].append({
            "node": "revisar_mindmap",
            "llm": state["llm03_provider"],
            "parte": parte_atual["parte_numero"],
            "tentativa": state["tentativas_revisao"],
            "aprovado": avaliacao.aprovado,
            "nota": avaliacao.nota_geral,
            "num_problemas": len(avaliacao.problemas)
        })
        
        if avaliacao.aprovado:
            logger.success(f"Mapa APROVADO (nota: {avaliacao.nota_geral})")
            state["status"] = "gerando"  # Vai para próxima parte
        else:
            logger.warning(f"Mapa REJEITADO (nota: {avaliacao.nota_geral})")
            logger.warning(f"Problemas: {len(avaliacao.problemas)}")
            
            # Se não esgotou tentativas, remove a parte para regerar
            if state["tentativas_revisao"] < state["max_tentativas"]:
                state["partes_processadas"].pop()
                state["status"] = "gerando"
            else:
                logger.error(f"Esgotadas {state['max_tentativas']} tentativas. Salvando mesmo assim.")
                state["status"] = "gerando"
        
        return state
        
    except Exception as e:
        logger.error(f"Erro no LLM03: {str(e)}")
        
        # Em caso de erro, aprova automaticamente para não travar
        parte_atual = state["partes_processadas"][-1]
        parte_atual["aprovado"] = True
        parte_atual["nota_geral"] = 5.0
        parte_atual["justificativa_revisao"] = f"Auto-aprovado devido a erro: {str(e)}"
        
        state["status"] = "gerando"
        return state