# backend/agents/graph.py
"""
Definição do grafo LangGraph para orquestração dos agentes.

Este módulo cria e configura o workflow completo de processamento,
incluindo todos os nodes, edges e lógica de decisão.
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
    
    O grafo implementa o seguinte fluxo:
    1. Parse do HTML (extrai informações)
    2. Divisão do conteúdo (LLM01)
    3. Geração de mapas mentais (LLM02)
    4. Revisão dos mapas (LLM03)
    5. Salvamento dos arquivos .mmd
    
    O grafo suporta:
    - Retry automático (até 3 tentativas)
    - Checkpointing para recuperação de falhas
    - Processamento sequencial de múltiplas partes
    
    Returns:
        CompiledGraph: Grafo LangGraph compilado e pronto para uso
    """
    
    logger.info("🏗️ Criando grafo LangGraph...")
    
    # ============================================
    # INICIALIZA O GRAFO
    # ============================================
    
    workflow = StateGraph(MindmapState)
    
    logger.debug("Grafo inicializado com MindmapState")
    
    # ============================================
    # ADICIONA NODES
    # ============================================
    
    workflow.add_node("parse_html", parse_html_node)
    logger.debug("Node adicionado: parse_html")
    
    workflow.add_node("dividir_conteudo", dividir_conteudo_node)
    logger.debug("Node adicionado: dividir_conteudo")
    
    workflow.add_node("gerar_mindmap", gerar_mindmap_node)
    logger.debug("Node adicionado: gerar_mindmap")
    
    workflow.add_node("revisar_mindmap", revisar_mindmap_node)
    logger.debug("Node adicionado: revisar_mindmap")
    
    workflow.add_node("salvar_mindmap", salvar_mindmap_node)
    logger.debug("Node adicionado: salvar_mindmap")
    
    # ============================================
    # DEFINE PONTO DE ENTRADA
    # ============================================
    
    workflow.set_entry_point("parse_html")
    logger.debug("Entry point definido: parse_html")
    
    # ============================================
    # ADICIONA EDGES SIMPLES
    # ============================================
    
    # 1. Parse → Dividir
    workflow.add_edge("parse_html", "dividir_conteudo")
    
    # 2. Dividir → Gerar
    workflow.add_edge("dividir_conteudo", "gerar_mindmap")
    
    # 3. Gerar → Revisar
    workflow.add_edge("gerar_mindmap", "revisar_mindmap")
    
    logger.debug("Edges simples adicionados")
    
    # ============================================
    # ADICIONA EDGE CONDICIONAL (RETRY LOGIC)
    # ============================================
    
    def should_retry_or_continue(state: MindmapState) -> Literal["gerar_mindmap", "salvar_mindmap", "gerar_mindmap_loop"]:
        """
        Decide se deve refazer o mindmap, continuar para próxima parte,
        ou salvar e finalizar.
        
        Lógica:
        1. Se esgotou tentativas (3x) → salva mesmo com problemas
        2. Se revisor APROVOU → vai para próxima parte (ou salva se última)
        3. Se revisor REJEITOU e ainda tem tentativas → refaz (retry)
        
        Args:
            state: Estado atual do grafo
        
        Returns:
            str: Nome do próximo node
        """
        
        # Verifica se esgotou tentativas
        if state["tentativas_revisao"] >= state["max_tentativas"]:
            logger.warning(
                f"⚠️ Esgotadas {state['max_tentativas']} tentativas. "
                "Salvando mapa mesmo com problemas."
            )
            
            # Verifica se ainda há partes para processar
            partes_concluidas = len(state["partes_processadas"])
            total_partes = len(state["divisoes"])
            
            if partes_concluidas < total_partes:
                # Ainda tem partes, vai para próxima
                logger.info(f"📝 Processando próxima parte ({partes_concluidas + 1}/{total_partes})")
                return "gerar_mindmap_loop"
            else:
                # Todas as partes processadas, salva tudo
                logger.info("✅ Todas as partes processadas. Salvando...")
                return "salvar_mindmap"
        
        # Pega resultado da última revisão
        ultima_parte = state["partes_processadas"][-1]
        aprovado = ultima_parte.get("aprovado", False)
        
        if aprovado:
            logger.success("✅ Mapa aprovado pelo revisor!")
            
            # Verifica se ainda há partes para processar
            partes_concluidas = len(state["partes_processadas"])
            total_partes = len(state["divisoes"])
            
            if partes_concluidas < total_partes:
                # Ainda tem partes, vai para próxima
                logger.info(f"📝 Processando próxima parte ({partes_concluidas + 1}/{total_partes})")
                return "gerar_mindmap_loop"
            else:
                # Todas as partes processadas, salva tudo
                logger.info("✅ Todas as partes processadas. Salvando...")
                return "salvar_mindmap"
        else:
            # Rejeitado, faz retry
            nota = ultima_parte.get("nota_geral", 0)
            problemas = len(ultima_parte.get("problemas", []))
            
            logger.warning(
                f"⚠️ Mapa rejeitado (nota: {nota}, {problemas} problemas). "
                f"Tentando novamente ({state['tentativas_revisao']}/{state['max_tentativas']})..."
            )
            
            return "gerar_mindmap"
    
    # Adiciona edge condicional
    workflow.add_conditional_edges(
        "revisar_mindmap",
        should_retry_or_continue,
        {
            "gerar_mindmap": "gerar_mindmap",  # Retry
            "gerar_mindmap_loop": "gerar_mindmap",  # Próxima parte
            "salvar_mindmap": "salvar_mindmap"  # Finaliza
        }
    )
    
    logger.debug("Edge condicional adicionado (retry logic)")
    
    # ============================================
    # ADICIONA EDGE FINAL
    # ============================================
    
    # 6. Salvar → Fim
    workflow.add_edge("salvar_mindmap", END)
    
    logger.debug("Edge final adicionado: salvar_mindmap → END")
    
    # ============================================
    # CONFIGURA CHECKPOINTING
    # ============================================
    
    # Usa MemorySaver para desenvolvimento
    # Em produção, trocar por SqliteSaver ou PostgresSaver
    memory = MemorySaver()
    
    logger.debug("Checkpointing configurado: MemorySaver")
    
    # ============================================
    # COMPILA O GRAFO
    # ============================================
    
    app = workflow.compile(checkpointer=memory)
    
    logger.success("✅ Grafo LangGraph compilado com sucesso!")
    
    # ============================================
    # LOG DE INFORMAÇÕES DO GRAFO
    # ============================================
    
    nodes = list(app.nodes.keys()) if hasattr(app, 'nodes') else ['parse_html', 'dividir_conteudo', 'gerar_mindmap', 'revisar_mindmap', 'salvar_mindmap']
    logger.info(f"📊 Nodes no grafo: {len(nodes)}")
    logger.debug(f"Lista de nodes: {', '.join(nodes)}")
    
    return app


# ============================================
# FUNÇÃO AUXILIAR PARA EXECUTAR O GRAFO
# ============================================

async def execute_graph(
    html_filename: str,
    llm01_provider: str,
    llm02_provider: str,
    llm03_provider: str,
    max_tentativas: int = 3
) -> dict:
    """
    Função auxiliar para executar o grafo de forma simplificada.
    
    Args:
        html_filename: Nome do arquivo HTML
        llm01_provider: Provider do LLM01
        llm02_provider: Provider do LLM02
        llm03_provider: Provider do LLM03
        max_tentativas: Máximo de tentativas de revisão (padrão: 3)
    
    Returns:
        dict: Estado final do processamento
    """
    
    # Cria o grafo
    graph = create_mindmap_graph()
    
    # Estado inicial
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
    
    # Configuração com thread_id para checkpointing
    config = {"configurable": {"thread_id": html_filename}}
    
    # Executa o grafo
    logger.info(f"🚀 Iniciando processamento: {html_filename}")
    
    try:
        # Executa até o fim
        final_state = await graph.ainvoke(initial_state, config)
        
        logger.success(f"✅ Processamento concluído: {html_filename}")
        
        return final_state
    
    except Exception as e:
        logger.error(f"❌ Erro no processamento: {str(e)}")
        raise


# ============================================
# VISUALIZAÇÃO DO GRAFO (OPCIONAL)
# ============================================

def visualize_graph():
    """
    Gera visualização do grafo (requer graphviz instalado).
    
    Útil para debugging e documentação.
    """
    try:
        graph = create_mindmap_graph()
        
        # Tenta gerar visualização
        # Requer: pip install pygraphviz
        png_data = graph.get_graph().draw_mermaid_png()
        
        with open("graph_visualization.png", "wb") as f:
            f.write(png_data)
        
        logger.success("✅ Visualização do grafo salva em: graph_visualization.png")
    
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível gerar visualização: {str(e)}")
        logger.info("Instale pygraphviz para gerar visualizações: pip install pygraphviz")


if __name__ == "__main__":
    # Teste básico
    logger.info("Testando criação do grafo...")
    graph = create_mindmap_graph()
    logger.success("✅ Grafo criado com sucesso!")
    
    # Opcional: gera visualização
    # visualize_graph()