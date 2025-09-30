# backend/services/mermaid_validator.py
import re
from typing import Tuple, List

class MermaidValidator:
    """Validador de sintaxe Mermaid para mindmaps."""
    
    @staticmethod
    def validate_mindmap(content: str) -> Tuple[bool, List[str]]:
        """
        Valida sintaxe de um mindmap Mermaid.
        
        Args:
            content: Conteúdo do mindmap
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        # 1. Deve começar com 'mindmap'
        if not content.strip().startswith('mindmap'):
            errors.append("Arquivo deve começar com 'mindmap'")
        
        # 2. Deve ter um título raiz com {{**...**}}
        if not re.search(r'\{\{?\*\*.*?\*\*\}\}?', content):
            errors.append("Falta título raiz no formato {{**Título**}}")
        
        # 3. Verifica indentação consistente
        lines = content.split('\n')
        prev_indent = 0
        
        for i, line in enumerate(lines[1:], start=2):  # Pula primeira linha 'mindmap'
            if not line.strip():
                continue
            
            # Conta espaços de indentação
            indent = len(line) - len(line.lstrip(' '))
            
            # Indentação deve ser múltiplo de 2
            if indent % 2 != 0:
                errors.append(f"Linha {i}: Indentação inválida (deve ser múltiplo de 2)")
            
            # Não deve pular mais de um nível
            if indent > prev_indent + 2:
                errors.append(f"Linha {i}: Pulo de indentação muito grande")
            
            prev_indent = indent
        
        # 4. Valida ícones Font Awesome
        icon_pattern = r'::icon\(fa fa-[\w-]+\)'
        icons = re.findall(r'::icon\([^)]+\)', content)
        
        for icon in icons:
            if not re.match(icon_pattern, icon):
                errors.append(f"Ícone inválido: {icon} (deve ser ::icon(fa fa-nome))")
        
        # 5. Verifica caracteres problemáticos
        problematic_chars = ['`', '~', '^', '&', '<', '>']
        for char in problematic_chars:
            if char in content:
                errors.append(f"Caractere problemático encontrado: '{char}'")
        
        # 6. Verifica balanceamento de chaves
        open_braces = content.count('{')
        close_braces = content.count('}')
        
        if open_braces != close_braces:
            errors.append(f"Chaves desbalanceadas: {open_braces} aberturas, {close_braces} fechamentos")
        
        is_valid = len(errors) == 0
        
        return is_valid, errors
    
    @staticmethod
    def fix_common_issues(content: str) -> str:
        """
        Tenta corrigir problemas comuns de sintaxe.
        
        Args:
            content: Conteúdo do mindmap
        
        Returns:
            str: Conteúdo corrigido
        """
        # Remove markdown wrappers
        content = re.sub(r'^```mermaid\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)
        
        # Normaliza quebras de linha
        content = content.replace('\r\n', '\n')
        
        # Remove linhas vazias extras
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Corrige espaços em ícones
        content = re.sub(r'::icon\s*\(\s*fa\s+fa-', '::icon(fa fa-', content)
        
        # Remove espaços no final das linhas
        lines = [line.rstrip() for line in content.split('\n')]
        content = '\n'.join(lines)
        
        return content.strip()