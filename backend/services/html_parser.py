# backend/services/html_parser.py
"""
Serviço de parsing de arquivos HTML.

Fornece funções utilitárias para extrair informações
de arquivos HTML formatados conforme padrão esperado.
"""

from bs4 import BeautifulSoup
from pathlib import Path
import re
from typing import Dict, Optional
from ..utils.logger import logger


class HTMLParseError(Exception):
    """Exceção customizada para erros de parsing."""
    pass


def parse_html_file(filepath: Path) -> Dict[str, str]:
    """
    Faz parsing de um arquivo HTML e extrai informações estruturadas.
    
    Args:
        filepath: Caminho do arquivo HTML
    
    Returns:
        dict: {
            "ramo_direito": str,
            "topico": str,
            "fundamentacao": str,
            "title": str
        }
    
    Raises:
        HTMLParseError: Se houver problemas no parsing
        FileNotFoundError: Se arquivo não existir
    """
    
    if not filepath.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")
    
    try:
        # Lê o arquivo
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Parse com BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extrai dados
        title = extract_title(soup)
        ramo_direito, topico = parse_title_pattern(title)
        fundamentacao = extract_fundamentacao(soup)
        
        return {
            "ramo_direito": ramo_direito,
            "topico": topico,
            "fundamentacao": fundamentacao,
            "title": title
        }
    
    except HTMLParseError:
        raise
    except Exception as e:
        raise HTMLParseError(f"Erro ao processar HTML: {str(e)}")


def extract_title(soup: BeautifulSoup) -> str:
    """
    Extrai o título do HTML.
    
    Args:
        soup: Objeto BeautifulSoup
    
    Returns:
        str: Texto do título
    
    Raises:
        HTMLParseError: Se título não for encontrado
    """
    title_tag = soup.find('title')
    
    if not title_tag:
        raise HTMLParseError("Tag <title> não encontrada no HTML")
    
    title = title_tag.get_text(strip=True)
    
    if not title:
        raise HTMLParseError("Tag <title> está vazia")
    
    return title


def parse_title_pattern(title: str) -> tuple[str, str]:
    """
    Faz parsing do título seguindo o padrão esperado.
    
    Padrão: [RAMO DO DIREITO] - [TÓPICO] - Guia Completo para Concursos
    
    Args:
        title: Texto do título
    
    Returns:
        tuple: (ramo_direito, topico)
    
    Raises:
        HTMLParseError: Se título não seguir o padrão
    """
    
    # Padrão principal: com colchetes
    pattern = r'^\[(.+?)\]\s*-\s*\[(.+?)\]\s*-'
    match = re.match(pattern, title)
    
    if match:
        return match.group(1).strip(), match.group(2).strip()
    
    # Padrão alternativo: sem colchetes
    pattern_alt = r'^(.+?)\s*-\s*(.+?)\s*-'
    match = re.match(pattern_alt, title)
    
    if match:
        logger.warning("⚠️ Título sem colchetes, usando padrão alternativo")
        return match.group(1).strip(), match.group(2).strip()
    
    raise HTMLParseError(
        f"Título não segue o padrão esperado.\n"
        f"Esperado: [RAMO DO DIREITO] - [TÓPICO] - Guia Completo para Concursos\n"
        f"Recebido: {title}"
    )


def extract_fundamentacao(soup: BeautifulSoup) -> str:
    """
    Extrai o conteúdo da fundamentação teórica.
    
    Args:
        soup: Objeto BeautifulSoup
    
    Returns:
        str: Texto da fundamentação
    
    Raises:
        HTMLParseError: Se section não for encontrada ou estiver vazia
    """
    
    fundamentacao_section = soup.find('section', id='fundamentacao')
    
    if not fundamentacao_section:
        raise HTMLParseError(
            "Section com id='fundamentacao' não encontrada.\n"
            "Certifique-se de que existe: <section id=\"fundamentacao\">...</section>"
        )
    
    # Extrai texto
    fundamentacao = fundamentacao_section.get_text(separator='\n', strip=True)
    
    if not fundamentacao or len(fundamentacao) < 100:
        raise HTMLParseError(
            f"Fundamentação muito curta ou vazia ({len(fundamentacao)} chars)."
        )
    
    # Normaliza texto
    fundamentacao = normalize_text(fundamentacao)
    
    return fundamentacao


def normalize_text(text: str) -> str:
    """
    Normaliza o texto removendo espaços/linhas extras.
    
    Args:
        text: Texto a normalizar
    
    Returns:
        str: Texto normalizado
    """
    
    # Remove linhas vazias extras
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove espaços múltiplos
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove espaços no início/fim de linhas
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def validate_html_structure(filepath: Path) -> tuple[bool, Optional[str]]:
    """
    Valida se o HTML tem a estrutura esperada.
    
    Args:
        filepath: Caminho do arquivo HTML
    
    Returns:
        tuple: (is_valid, error_message)
    """
    
    try:
        parse_html_file(filepath)
        return True, None
    except HTMLParseError as e:
        return False, str(e)
    except FileNotFoundError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Erro inesperado: {str(e)}"


def extract_metadata(filepath: Path) -> Optional[Dict]:
    """
    Extrai metadados do arquivo HTML sem processar conteúdo completo.
    
    Útil para listagem rápida de arquivos.
    
    Args:
        filepath: Caminho do arquivo
    
    Returns:
        dict ou None: Metadados básicos ou None se houver erro
    """
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Lê apenas os primeiros 2KB (suficiente para <head>)
            content = f.read(2048)
        
        soup = BeautifulSoup(content, 'lxml')
        
        title = soup.find('title')
        if not title:
            return None
        
        title_text = title.get_text(strip=True)
        
        try:
            ramo, topico = parse_title_pattern(title_text)
        except HTMLParseError:
            return None
        
        return {
            "filename": filepath.name,
            "ramo_direito": ramo,
            "topico": topico,
            "size_bytes": filepath.stat().st_size
        }
    
    except Exception:
        return None