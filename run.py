#!/usr/bin/env python3
"""
Script de inicialização do Gerador de Mapas Mentais.

Uso:
    python run.py              # Modo desenvolvimento
    python run.py --prod       # Modo produção
    python run.py --port 8080  # Porta customizada
"""

import sys
import argparse
import uvicorn
from pathlib import Path

def check_environment():
    """Verifica se o ambiente está configurado corretamente."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ ERRO: Arquivo .env não encontrado!")
        print("\n📝 Copie o arquivo .env.example para .env e configure suas API keys:")
        print("   cp .env.example .env")
        print("\nDepois edite o arquivo .env com suas credenciais.")
        sys.exit(1)
    
    print("✅ Arquivo .env encontrado")
    
    # Verifica se os diretórios existem
    from backend.services.file_manager import ensure_directories
    ensure_directories()
    print("✅ Diretórios criados")

def main():
    parser = argparse.ArgumentParser(description="Gerador de Mapas Mentais")
    parser.add_argument("--prod", action="store_true", help="Modo produção")
    parser.add_argument("--port", type=int, default=8000, help="Porta do servidor")
    parser.add_argument("--host", default="0.0.0.0", help="Host do servidor")
    
    args = parser.parse_args()
    
    # Verifica ambiente
    check_environment()
    
    # Configurações
    reload = not args.prod
    log_level = "info" if args.prod else "debug"
    
    print("\n" + "="*60)
    print("🚀 INICIANDO GERADOR DE MAPAS MENTAIS")
    print("="*60)
    print(f"📍 Modo: {'PRODUÇÃO' if args.prod else 'DESENVOLVIMENTO'}")
    print(f"🌐 URL: http://{args.host}:{args.port}")
    print(f"📊 Logs: {'INFO' if args.prod else 'DEBUG'}")
    print(f"🔄 Hot reload: {'Desabilitado' if args.prod else 'Habilitado'}")
    print("="*60)
    print("\n💡 Acesse a interface: http://localhost:{}\n".format(args.port))
    
    # Inicia servidor
    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=reload,
        log_level=log_level,
        access_log=True
    )

if __name__ == "__main__":
    main()