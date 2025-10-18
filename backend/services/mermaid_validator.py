# backend/services/mermaid_validator.py
import re
import argparse
from pathlib import Path
from typing import Tuple, List

class MermaidValidator:
    """Validador e corretor de sintaxe Mermaid para mindmaps."""
    
    @staticmethod
    def validate_mindmap(content: str) -> Tuple[bool, List[str]]:
        """
        Valida a sintaxe de um mindmap Mermaid, incluindo a regra de não usar parênteses/colchetes.
        """
        errors = []
        lines = content.split('\n')

        if not content.strip().startswith('mindmap'):
            errors.append("Arquivo deve começar com 'mindmap'")
        
        if not re.search(r'\{\{?\*\*.*?\*\*\}\}?', content):
            errors.append("Falta título raiz no formato {{**Título**}}")
        
        for i, line in enumerate(lines, start=1):
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith('::icon(') or stripped_line == 'mindmap':
                continue

            if '(' in stripped_line or ')' in stripped_line or '[' in stripped_line or ']' in stripped_line:
                if not stripped_line.startswith('{'):
                    errors.append(f"Linha {i}: Parênteses ou colchetes não permitidos. Encontrado: '{stripped_line}'")

        return len(errors) == 0, errors
    
    @staticmethod
    def fix_common_issues(content: str) -> str:
        """
        Corrige problemas comuns de sintaxe, incluindo a substituição de parênteses e colchetes.
        """
        content = re.sub(r'^```mermaid\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)
        content = content.replace('\r\n', '\n')
        content = re.sub(r'::icon\s*\(\s*fa\s+fa-', '::icon(fa fa-', content)
        
        lines = content.split('\n')
        processed_lines = []
        
        for line in lines:
            stripped_line = line.strip()
            
            if stripped_line.startswith('::icon('):
                processed_lines.append(line)
                continue
            
            modified_line = line.replace('(', '-').replace(')', '-').replace('[', '-').replace(']', '-')
            processed_lines.append(modified_line)
            
        content = '\n'.join(processed_lines)
        content = re.sub(r'\n{3,}', '\n\n', content)
        lines = [line.rstrip() for line in content.split('\n')]
        content = '\n'.join(lines)
        
        return content.strip()

# --- BLOCO ADICIONADO PARA EXECUÇÃO VIA LINHA DE COMANDO ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Valida e corrige arquivos de mapa mental Mermaid (.mmd)."
    )
    parser.add_argument(
        "files",
        metavar="FILE",
        type=str,
        nargs='+',
        help="Caminho para um ou mais arquivos .mmd a serem processados."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve os arquivos originais com as correções."
    )
    
    args = parser.parse_args()
    
    for filepath_str in args.files:
        filepath = Path(filepath_str)
        if not filepath.exists() or not filepath.is_file():
            print(f"ERRO: Arquivo não encontrado: {filepath}")
            continue

        print(f"--- Processando: {filepath.name} ---")
        original_content = filepath.read_text(encoding='utf-8')
        
        # Corrige o conteúdo
        corrected_content = MermaidValidator.fix_common_issues(original_content)
        
        # Valida o conteúdo corrigido
        is_valid, errors = MermaidValidator.validate_mindmap(corrected_content)
        
        if is_valid:
            print("Status: ✅ Válido")
        else:
            print(f"Status: ❌ Inválido. Problemas encontrados:")
            for error in errors:
                print(f"  - {error}")
        
        if original_content != corrected_content:
            print("INFO: Foram aplicadas correções no arquivo.")
            if args.overwrite:
                filepath.write_text(corrected_content, encoding='utf-8')
                print("INFO: O arquivo foi sobrescrito com as correções.")
        else:
            print("INFO: Nenhuma correção foi necessária.")
        print("-" * (len(filepath.name) + 14))