# backend/agents/nodes/gerador_node.py
"""
Node do LLM02 - Gerador de Mapas Mentais.
VERSÃO CORRIGIDA - Fix loop infinito
"""

from ..state import MindmapState
from ...services.llm_factory import get_llm
from ...agents.prompts.gerador_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from ...utils.logger import logger
from datetime import datetime
import re


async def gerar_mindmap_node(state: MindmapState) -> MindmapState:
    """
    LLM02: Gera o código Mermaid do mapa mental.
    
    LÓGICA CORRIGIDA:
    - Processa apenas partes que ainda não foram aprovadas
    - Respeita o sistema de retry (max 3 tentativas por parte)
    - Não cria loops infinitos
    """
    
    logger.info("🤖 LLM02: Gerando mapa mental...")
    
    try:
        # ============================================
        # DETERMINA QUAL PARTE PROCESSAR
        # ============================================
        
        # Partes já aprovadas (não processar novamente)
        partes_aprovadas = [p for p in state["partes_processadas"] if p.get("aprovado")]
        
        # Total de partes
        total_partes = len(state["divisoes"])
        
        logger.info(f"📊 Progresso: {len(partes_aprovadas)}/{total_partes} partes aprovadas")
        
        # Se todas as partes já foram aprovadas, não faz nada
        if len(partes_aprovadas) >= total_partes:
            logger.success("✅ Todas as partes já foram processadas!")
            state["status"] = "concluido"
            return state
        
        # Determina qual parte processar
        # Se a última parte não foi aprovada, processa ela novamente (retry)
        # Senão, processa a próxima parte não aprovada
        
        if state["partes_processadas"] and not state["partes_processadas"][-1].get("aprovado"):
            # RETRY da última parte
            parte_index = state["partes_processadas"][-1]["parte_numero"] - 1
            is_retry = True
            state["tentativas_revisao"] += 1
            
            logger.warning(f"🔄 RETRY: Parte {parte_index + 1} (tentativa {state['tentativas_revisao']}/{state['max_tentativas']})")
            
            # Se esgotou tentativas, marca como aprovado forçadamente e pula para próxima
            if state["tentativas_revisao"] > state["max_tentativas"]:
                logger.error(f"❌ Esgotadas {state['max_tentativas']} tentativas na parte {parte_index + 1}")
                state["partes_processadas"][-1]["aprovado"] = True
                state["partes_processadas"][-1]["nota_geral"] = 5.0
                state["partes_processadas"][-1]["justificativa_revisao"] = "Auto-aprovado após esgotar tentativas"
                state["tentativas_revisao"] = 0
                
                # Processa próxima parte
                parte_index = len(partes_aprovadas)
                if parte_index >= total_partes:
                    state["status"] = "concluido"
                    return state
                is_retry = False
        else:
            # NOVA PARTE (não é retry)
            parte_index = len(partes_aprovadas)
            is_retry = False
            state["tentativas_revisao"] = 0  # Reset tentativas para nova parte
            
            logger.info(f"📝 Nova parte: {parte_index + 1}/{total_partes}")
        
        # Pega a parte atual
        parte_atual = state["divisoes"][parte_index]
        
        logger.info(f"🎯 Processando: Parte {parte_index + 1} - {parte_atual['titulo']}")
        
        # ============================================
        # OBTÉM LLM CONFIGURADO
        # ============================================
        
        llm = get_llm(
            provider=state["llm02_provider"],
            temperature=0.4,
            max_tokens=12000
        )
        
        logger.debug(f"LLM configurado: {state['llm02_provider']}")
        
        # ============================================
        # PREPARA PROMPT
        # ============================================
        
        user_prompt = USER_PROMPT_TEMPLATE.format(
            ramo_direito=state["ramo_direito"],
            topico=state["topico"],
            parte_titulo=parte_atual["titulo"],
            conteudo_parte=parte_atual.get("conteudo", state["fundamentacao"])
        )
        
        # ============================================
        # CHAMA LLM
        # ============================================
        
        logger.info("📞 Chamando LLM02...")
        
        response = await llm.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ])
        
        mapa_gerado = response.content
        
        # ============================================
        # LIMPA CÓDIGO MERMAID
        # ============================================
        
        # Remove markdown wrappers
        mapa_gerado = re.sub(r'^```mermaid\s*', '', mapa_gerado, flags=re.MULTILINE)
        mapa_gerado = re.sub(r'\s*```$', '', mapa_gerado, flags=re.MULTILINE)
        mapa_gerado = mapa_gerado.strip()
        
        logger.success(f"✅ Mapa gerado ({len(mapa_gerado)} chars)")
        
        # ============================================
        # ATUALIZA ESTADO
        # ============================================
        
        if is_retry:
            # Atualiza a parte existente
            state["partes_processadas"][-1]["mapa_gerado"] = mapa_gerado
            state["partes_processadas"][-1]["tentativas"] = state["tentativas_revisao"]
            
        else:
            # Adiciona nova parte
            state["partes_processadas"].append({
                "parte_numero": parte_index + 1,
                "parte_titulo": parte_atual["titulo"],
                "mapa_gerado": mapa_gerado,
                "aprovado": None,  # Será definido pelo revisor
                "tentativas": 1,
                "problemas": [],
                "nota_geral": None,
                "justificativa_revisao": None
            })
        
        state["status"] = "revisando"
        
        # Log estruturado
        state["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "node": "gerar_mindmap",
            "level": "success",
            "message": f"Mapa gerado para parte {parte_index + 1}",
            "data": {
                "llm": state["llm02_provider"],
                "parte": parte_index + 1,
                "total_partes": total_partes,
                "tamanho": len(mapa_gerado),
                "is_retry": is_retry,
                "tentativa": state["tentativas_revisao"] if is_retry else 1
            }
        })
        
        logger.success(f"✅ Parte {parte_index + 1} gerada com sucesso")
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Erro no LLM02: {str(e)}")
        logger.exception(e)
        
        state["status"] = "erro"
        state["erro_msg"] = f"Erro na geração: {str(e)}"
        
        state["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "node": "gerar_mindmap",
            "level": "error",
            "message": f"Erro no LLM02: {str(e)}",
            "data": {
                "llm": state["llm02_provider"],
                "error_type": type(e).__name__
            }
        })
        
        return state