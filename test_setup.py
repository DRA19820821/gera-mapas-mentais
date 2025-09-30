#!/usr/bin/env python3
"""
Script de validação da instalação.
Testa se todos os componentes estão configurados corretamente.

Uso: python test_setup.py
"""

import sys
import os
from pathlib import Path

def print_header(text):
    """Imprime cabeçalho formatado."""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def check_python_version():
    """Verifica versão do Python."""
    print("\n🐍 Verificando Python...")
    version = sys.version_info
    
    if version.major == 3 and version.minor >= 9:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} (OK)")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (Requer 3.9+)")
        return False

def check_packages():
    """Verifica pacotes instalados."""
    print("\n📦 Verificando pacotes...")
    
    required_packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("langgraph", "LangGraph"),
        ("langchain", "LangChain"),
        ("bs4", "BeautifulSoup4"),
        ("loguru", "Loguru"),
    ]
    
    all_ok = True
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} (não instalado)")
            all_ok = False
    
    return all_ok

def check_directories():
    """Verifica estrutura de diretórios."""
    print("\n📁 Verificando diretórios...")
    
    required_dirs = [
        "backend",
        "backend/agents",
        "backend/api",
        "backend/core",
        "backend/services",
        "backend/utils",
        "frontend",
        "logs",
        "output",
        "uploads",
    ]
    
    all_ok = True
    for directory in required_dirs:
        path = Path(directory)
        if path.exists():
            print(f"   ✅ {directory}")
        else:
            print(f"   ❌ {directory} (não existe)")
            all_ok = False
    
    return all_ok

def check_files():
    """Verifica arquivos essenciais."""
    print("\n📄 Verificando arquivos essenciais...")
    
    required_files = [
        ".env",
        "requirements.txt",
        "run.py",
        "backend/main.py",
        "backend/core/config.py",
        "backend/agents/state.py",
        "backend/agents/graph.py",
        "frontend/index.html",
    ]
    
    all_ok = True
    for file in required_files:
        path = Path(file)
        if path.exists():
            print(f"   ✅ {file}")
        else:
            print(f"   ⚠️  {file} (não encontrado)")
            all_ok = False
    
    return all_ok

def check_env_file():
    """Verifica configuração do .env."""
    print("\n🔑 Verificando .env...")
    
    env_path = Path(".env")
    if not env_path.exists():
        print("   ❌ Arquivo .env não encontrado")
        return False
    
    with open(env_path) as f:
        content = f.read()
    
    providers = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Google": "GOOGLE_API_KEY",
        "DeepSeek": "DEEPSEEK_API_KEY",
    }
    
    configured = []
    for name, key in providers.items():
        if key in content and len(content.split(f"{key}=")[1].split("\n")[0].strip()) > 10:
            print(f"   ✅ {name}")
            configured.append(name)
        else:
            print(f"   ⚠️  {name} (não configurado)")
    
    if configured:
        print(f"\n   ℹ️  {len(configured)} provider(s) configurado(s)")
        return True
    else:
        print("\n   ❌ Nenhum provider configurado!")
        return False

def check_imports():
    """Testa imports do projeto."""
    print("\n🔍 Testando imports...")
    
    try:
        # Tenta importar módulos do projeto
        sys.path.insert(0, str(Path.cwd()))
        
        from backend.core.config import get_settings
        print("   ✅ backend.core.config")
        
        from backend.agents.state import MindmapState
        print("   ✅ backend.agents.state")
        
        from backend.utils.logger import setup_logger
        print("   ✅ backend.utils.logger")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Erro ao importar: {e}")
        return False
    except Exception as e:
        print(f"   ⚠️  Aviso: {e}")
        return True

def test_server_start():
    """Testa se o servidor pode iniciar."""
    print("\n🚀 Testando inicialização do servidor...")
    
    try:
        from backend.main import app
        print("   ✅ FastAPI app carregado")
        
        # Verifica rotas
        routes = [route.path for route in app.routes]
        print(f"   ℹ️  {len(routes)} rotas registradas")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False

def print_summary(results):
    """Imprime resumo dos testes."""
    print_header("RESUMO")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\n   ✅ Passou: {passed}/{total}")
    print(f"   ❌ Falhou: {total - passed}/{total}")
    
    if passed == total:
        print("\n   🎉 TUDO OK! Sistema pronto para uso.")
        print("\n   Execute: python run.py")
        return True
    else:
        print("\n   ⚠️  Alguns problemas encontrados.")
        print("\n   Revise a instalação seguindo o README.md")
        return False

def main():
    """Executa todos os testes."""
    print_header("VALIDAÇÃO DA INSTALAÇÃO")
    print("\nVerificando configuração do sistema...")
    
    results = {
        "Python": check_python_version(),
        "Pacotes": check_packages(),
        "Diretórios": check_directories(),
        "Arquivos": check_files(),
        "Variáveis": check_env_file(),
        "Imports": check_imports(),
        "Servidor": test_server_start(),
    }
    
    success = print_summary(results)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()