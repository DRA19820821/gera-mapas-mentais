# backend/agents/state.py
from typing import TypedDict, List, Literal, Optional

class MindmapState(TypedDict):
    """
    Estado compartilhado entre todos os nodes do grafo LangGraph.
    
    Este estado é passado e modificado por cada node durante a execução.
    """
    
    # ============================================
    # DADOS EXTRAÍDOS DO HTML
    # ============================================
    html_filename: str
    """Nome do arquivo HTML sendo processado"""
    
    ramo_direito: str
    """Ramo do Direito extraído (ex: Direito Administrativo)"""
    
    topico: str
    """Tópico específico (ex: Controle da Administração Pública)"""
    
    fundamentacao: str
    """Conteúdo completo da fundamentação teórica"""
    
    # ============================================
    # DIVISÃO DO CONTEÚDO (LLM01)
    # ============================================
    divisoes: List[dict]
    """
    Lista de partes em que o conteúdo foi dividido.
    Cada item é um dict:
    {
        "numero": 1,
        "titulo": "Controle Interno",
        "conteudo": "texto...",
        "estimativa_mapas": 2
    }
    """
    
    # ============================================
    # PROCESSAMENTO DE PARTES
    # ============================================
    partes_processadas: List[dict]
    """
    Lista de partes já processadas (geradas e revisadas).
    Cada item é um dict:
    {
        "parte_numero": 1,
        "parte_titulo": "Controle Interno",
        "mapa_gerado": "mindmap...",
        "aprovado": True/False,
        "nota_geral": 8.5,
        "tentativas": 2,
        "problemas": [...],
        "sugestoes_melhoria": [...],
        "justificativa_revisao": "..."
    }
    """
    
    # ============================================
    # CONTROLE DE RETRY
    # ============================================
    tentativas_revisao: int
    """Número de tentativas da parte atual"""
    
    max_tentativas: int
    """Máximo de tentativas permitidas (padrão: 3)"""
    
    # ============================================
    # STATUS E ERROS
    # ============================================
    status: Literal["parsing", "dividindo", "gerando", "revisando", "concluido", "erro"]
    """Status atual do processamento"""
    
    erro_msg: Optional[str]
    """Mensagem de erro, se houver"""
    
    # ============================================
    # CONFIGURAÇÃO DE LLMS
    # ============================================
    llm01_provider: str
    """Provider do LLM01 - Divisor (openai|anthropic|gemini|deepseek)"""
    
    llm02_provider: str
    """Provider do LLM02 - Gerador (openai|anthropic|gemini|deepseek)"""
    
    llm03_provider: str
    """Provider do LLM03 - Revisor (openai|anthropic|gemini|deepseek)"""
    
    # ============================================
    # LOGS E TELEMETRIA
    # ============================================
    logs: List[dict]
    """
    Lista de eventos de log.
    Cada item é um dict:
    {
        "timestamp": "2025-09-30T14:30:00",
        "node": "nome_do_node",
        "level": "info|success|warning|error",
        "message": "...",
        "data": {...}
    }
    """