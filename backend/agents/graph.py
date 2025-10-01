# backend/agents/graph.py
"""
Definição do grafo LangGraph para orquestração dos agentes.
VERSÃO CORRIGIDA - Fix loop infinito
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Literal

from .state import MindmapState
from .nodes.parser_node import parse_html_node
from .nodes.divisor_node import dividir_conteudo_node
from .nodes.gerador_node import gerar_mindmap_node
from .nodes.revisor_node import revisar_mindmap_node
from .nodes.salvar_node import salvar_mindmap_node

from ..utils.logger import logger


def create_mindmap_graph():
    """
    Cria e configura o grafo LangGraph para geração de mapas mentais.
    """
    
    logger.info("🏗️ Criando grafo LangGraph...")
    
    workflow = StateGraph(MindmapState)
    
    # Adiciona nodes
    workflow.add_node("parse_html", parse_html_node)
    workflow.add_node("dividir_conteudo", dividir_conteudo_node)
    workflow.add_node("gerar_mindmap", gerar_mindmap_node)
    workflow.add_node("revisar_mindmap", revisar_mindmap_node)
    workflow.add_node("salvar_mindmap", salvar_mindmap_node)
    
    # Entry point
    workflow.set_entry_point("parse_html")
    
    # Edges simples
    workflow.add_edge("parse_html", "dividir_conteudo")
    workflow.add_edge("dividir_conteudo", "gerar_mindmap")
    workflow.add_edge("gerar_mindmap", "revisar_mindmap")
    
    # ============================================
    # EDGE CONDICIONAL CORRIGIDO
    # ============================================
    
    def should_continue(state: MindmapState) -> Literal["gerar_mindmap", "salvar_mindmap"]:
        """
        Decide o próximo passo após revisão.
        
        Lógica corrigida:
        1. Verifica se há partes não processadas
        2. Se sim → volta para gerar_mindmap (próxima parte)
        3. Se não → vai para salvar_mindmap (fim)
        """
        
        # Pega resultado da última revisão
        ultima_parte = state["partes_processadas"][-1]
        aprovado = ultima_parte.get("aprovado", False)
        
        # Conta partes processadas vs total
        partes_concluidas = len([p for p in state["partes_processadas"] if p.get("aprovado")])
        total_partes = len(state["divisoes"])
        
        logger.info(f"📊 Status: {partes_concluidas}/{total_partes} partes concluídas")
        
        # Se ainda há partes para processar
        if partes_concluidas < total_partes:
            logger.info("➡️ Próxima parte...")
            return "gerar_mindmap"
        else:
            logger.info("✅ Todas as partes concluídas! Salvando...")
            return "salvar_mindmap"
    
    # Adiciona edge condicional
    workflow.add_conditional_edges(
        "revisar_mindmap",
        should_continue,
        {
            "gerar_mindmap": "gerar_mindmap",
            "salvar_mindmap": "salvar_mindmap"
        }
    )
    
    # Edge final
    workflow.add_edge("salvar_mindmap", END)
    
    # Compila com checkpointing
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    logger.success("✅ Grafo LangGraph compilado com sucesso!")
    
    return app


async def execute_graph(
    html_filename: str,
    llm01_provider: str,
    llm02_provider: str,
    llm03_provider: str,
    max_tentativas: int = 3
) -> dict:
    """Função auxiliar para executar o grafo."""
    
    graph = create_mindmap_graph()
    
    initial_state: MindmapState = {
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
    
    config = {"configurable": {"thread_id": html_filename}}
    
    logger.info(f"🚀 Iniciando processamento: {html_filename}")
    
    try:
        final_state = await graph.ainvoke(initial_state, config)
        logger.success(f"✅ Processamento concluído: {html_filename}")
        return final_state
    
    except Exception as e:
        logger.error(f"❌ Erro no processamento: {str(e)}")
        raise


if __name__ == "__main__":
    logger.info("Testando criação do grafo...")
    graph = create_mindmap_graph()
    logger.success("✅ Grafo criado com sucesso!")