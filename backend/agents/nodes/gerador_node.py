# backend/agents/nodes/gerador_node.py
from ..state import MindmapState
from ...services.llm_factory import get_llm
from ...agents.prompts.gerador_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from ...utils.logger import logger
import re

async def gerar_mindmap_node(state: MindmapState) -> MindmapState:
    """
    LLM02: Gera o código Mermaid do mapa mental.
    
    Este node processa uma parte por vez em loop.
    """
    logger.info("LLM02: Gerando mapa mental...")
    
    try:
        # Determina qual parte processar
        partes_concluidas = len(state["partes_processadas"])
        total_partes = len(state["divisoes"])
        
        if partes_concluidas >= total_partes:
            # Todas as partes foram processadas
            state["status"] = "concluido"
            return state
        
        # Pega a próxima parte
        parte_atual = state["divisoes"][partes_concluidas]
        
        logger.info(f"Processando parte {partes_concluidas + 1}/{total_partes}: {parte_atual['titulo']}")
        
        # Obtém LLM configurado
        llm = get_llm(
            provider=state["llm02_provider"],
            temperature=0.4,
            max_tokens=3000
        )
        
        # Prepara prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            ramo_direito=state["ramo_direito"],
            topico=state["topico"],
            parte_titulo=parte_atual["titulo"],
            conteudo_parte=parte_atual.get("conteudo", state["fundamentacao"])
        )
        
        # Chama LLM
        response = await llm.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ])
        
        # Extrai código Mermaid
        mapa_gerado = response.content
        
        # Remove markdown wrappers se houver
        mapa_gerado = re.sub(r'^```mermaid\s*', '', mapa_gerado, flags=re.MULTILINE)
        mapa_gerado = re.sub(r'\s*```$', '', mapa_gerado, flags=re.MULTILINE)
        mapa_gerado = mapa_gerado.strip()
        
        # Adiciona aos resultados (será revisado no próximo node)
        state["partes_processadas"].append({
            "parte_numero": partes_concluidas + 1,
            "parte_titulo": parte_atual["titulo"],
            "mapa_gerado": mapa_gerado,
            "aprovado": None,  # Será definido pelo revisor
            "tentativas": 1,
            "problemas": []
        })
        
        state["tentativas_revisao"] = 0  # Reset para a nova parte
        state["status"] = "revisando"
        
        state["logs"].append({
            "node": "gerar_mindmap",
            "llm": state["llm02_provider"],
            "parte": partes_concluidas + 1,
            "total_partes": total_partes,
            "tamanho_mapa": len(mapa_gerado)
        })
        
        logger.success(f"Mapa gerado para parte {partes_concluidas + 1}")
        return state
        
    except Exception as e:
        logger.error(f"Erro no LLM02: {str(e)}")
        state["status"] = "erro"
        state["erro_msg"] = str(e)
        return state