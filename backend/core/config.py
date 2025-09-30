# backend/core/config.py
"""
Configurações da aplicação usando Pydantic Settings.

Este módulo gerencia todas as variáveis de ambiente e configurações
do sistema, com validação automática e suporte a .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    Configurações da aplicação.
    
    Todas as variáveis podem ser definidas no arquivo .env
    ou como variáveis de ambiente do sistema.
    """
    
    # ============================================
    # INFORMAÇÕES DA APLICAÇÃO
    # ============================================
    app_name: str = "Gerador de Mapas Mentais"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # ============================================
    # DIRETÓRIOS
    # ============================================
    upload_dir: str = "uploads"
    output_dir: str = "output"
    logs_dir: str = "logs"
    
    # ============================================
    # API KEYS DOS PROVEDORES DE LLM
    # ============================================
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    deepseek_api_key: str = ""
    
    # ============================================
    # CONFIGURAÇÕES DE PROCESSAMENTO
    # ============================================
    max_tentativas_revisao: int = 3
    """Número máximo de tentativas de revisão por mapa mental"""
    
    max_files_per_upload: int = 10
    """Número máximo de arquivos HTML por upload"""
    
    # ============================================
    # CONFIGURAÇÕES DE LOGGING
    # ============================================
    log_level: str = "INFO"
    """Níveis: DEBUG, INFO, WARNING, ERROR, CRITICAL"""
    
    log_rotation: str = "100 MB"
    """Rotação de logs por tamanho"""
    
    log_retention: str = "30 days"
    """Tempo de retenção dos logs"""
    
    # ============================================
    # CONFIGURAÇÕES DO SERVIDOR
    # ============================================
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    
    # ============================================
    # CORS (Cross-Origin Resource Sharing)
    # ============================================
    cors_origins: list[str] = ["*"]
    """Lista de origens permitidas. Use ["*"] para permitir todas em dev"""
    
    # ============================================
    # TIMEOUTS E LIMITES
    # ============================================
    llm_timeout: int = 300
    """Timeout para chamadas LLM em segundos (5 minutos)"""
    
    max_file_size_mb: int = 10
    """Tamanho máximo de arquivo HTML em MB"""
    
    # ============================================
    # CONFIGURAÇÃO PYDANTIC
    # ============================================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ============================================
    # MÉTODOS AUXILIARES
    # ============================================
    
    def get_provider_key(self, provider: str) -> Optional[str]:
        """
        Retorna a API key do provider especificado.
        
        Args:
            provider: Nome do provider (openai, anthropic, gemini, deepseek)
        
        Returns:
            API key ou None se não configurada
        """
        provider = provider.lower()
        
        key_mapping = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.google_api_key,
            "google": self.google_api_key,
            "deepseek": self.deepseek_api_key,
        }
        
        return key_mapping.get(provider)
    
    def is_provider_configured(self, provider: str) -> bool:
        """
        Verifica se o provider está configurado com API key.
        
        Args:
            provider: Nome do provider
        
        Returns:
            True se configurado, False caso contrário
        """
        key = self.get_provider_key(provider)
        return key is not None and len(key) > 10
    
    def list_configured_providers(self) -> list[str]:
        """
        Lista todos os providers que estão configurados.
        
        Returns:
            Lista de nomes de providers configurados
        """
        providers = []
        
        if self.is_provider_configured("openai"):
            providers.append("openai")
        
        if self.is_provider_configured("anthropic"):
            providers.append("anthropic")
        
        if self.is_provider_configured("gemini"):
            providers.append("gemini")
        
        if self.is_provider_configured("deepseek"):
            providers.append("deepseek")
        
        return providers
    
    def validate_provider(self, provider: str) -> tuple[bool, str]:
        """
        Valida se um provider pode ser usado.
        
        Args:
            provider: Nome do provider
        
        Returns:
            Tuple (is_valid, error_message)
        """
        valid_providers = ["openai", "anthropic", "gemini", "deepseek"]
        
        if provider.lower() not in valid_providers:
            return False, f"Provider '{provider}' não é válido. Opções: {', '.join(valid_providers)}"
        
        if not self.is_provider_configured(provider):
            return False, f"Provider '{provider}' não está configurado. Adicione a API key no arquivo .env"
        
        return True, ""


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna instância singleton das configurações.
    
    O decorator @lru_cache() garante que apenas uma instância
    seja criada e reutilizada em toda a aplicação.
    
    Returns:
        Settings: Configurações da aplicação
    """
    return Settings()


# Exemplo de uso:
# from backend.core.config import get_settings
# settings = get_settings()
# print(settings.app_name)