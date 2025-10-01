# backend/services/llm_factory.py
"""
Factory para criação de instâncias de LLMs.

Fornece uma interface unificada para trabalhar com diferentes
provedores de LLM (OpenAI, Anthropic, Google, DeepSeek) usando
as integrações nativas do LangChain.
"""

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_deepseek import ChatDeepSeek
from typing import Optional
import os

from ..core.config import get_settings
from ..utils.logger import logger


# ============================================
# MAPEAMENTO DE MODELOS PADRÃO
# ============================================

DEFAULT_MODELS = {
    "openai": "gpt-4.1",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.5-pro",
    "deepseek": "deepseek-reasoner"
}


# ============================================
# FUNÇÃO PRINCIPAL - FACTORY
# ============================================

def get_llm(
    provider: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    **kwargs
):
    """
    Factory para obter instância de LLM configurada.
    
    Usa as integrações nativas do LangChain para cada provider,
    garantindo compatibilidade total com recursos como structured output,
    streaming, e function calling.
    
    Args:
        provider: Nome do provider (openai, anthropic, gemini, deepseek)
        model: Nome do modelo (opcional, usa padrão do provider)
        temperature: Temperatura para geração (0.0 a 1.0)
        max_tokens: Máximo de tokens na resposta
        **kwargs: Argumentos adicionais específicos do provider
    
    Returns:
        ChatModel: Instância do modelo configurado
    
    Raises:
        ValueError: Se provider for inválido ou não configurado
    
    Examples:
        >>> llm = get_llm("anthropic", temperature=0.3)
        >>> response = llm.invoke("Hello!")
        
        >>> llm = get_llm("openai", model="gpt-4-turbo")
        >>> response = await llm.ainvoke([{"role": "user", "content": "Hi"}])
    """
    
    settings = get_settings()
    provider = provider.lower()
    
    # Valida provider
    valid_providers = ["openai", "anthropic", "gemini", "deepseek"]
    if provider not in valid_providers:
        raise ValueError(
            f"Provider '{provider}' não é válido. "
            f"Opções: {', '.join(valid_providers)}"
        )
    
    # Verifica se provider está configurado
    if not settings.is_provider_configured(provider):
        configured = settings.list_configured_providers()
        raise ValueError(
            f"Provider '{provider}' não está configurado no .env\n"
            f"Providers configurados: {', '.join(configured) if configured else 'nenhum'}\n"
            f"Adicione a API key correspondente no arquivo .env"
        )
    
    # Usa modelo padrão se não especificado
    if model is None:
        model = DEFAULT_MODELS[provider]
    
    logger.debug(
        f"Criando LLM: provider={provider}, model={model}, "
        f"temp={temperature}, max_tokens={max_tokens}"
    )
    
    # ============================================
    # OPENAI
    # ============================================
    
    if provider == "openai":
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout,
            **kwargs
        )
    
    # ============================================
    # ANTHROPIC
    # ============================================
    
    elif provider == "anthropic":
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout,
            **kwargs
        )
    
    # ============================================
    # GOOGLE GEMINI
    # ============================================
    
    elif provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            google_api_key=settings.google_api_key,
            timeout=settings.llm_timeout,
            **kwargs
        )
    
    # ============================================
    # DEEPSEEK
    # ============================================
    
    elif provider == "deepseek":
        return ChatDeepSeek(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.deepseek_api_key,
            timeout=settings.llm_timeout,
            **kwargs
        )
    
    else:
        # Não deve chegar aqui devido à validação anterior
        raise ValueError(f"Provider não implementado: {provider}")


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def list_available_providers() -> list[str]:
    """
    Lista providers que estão configurados e disponíveis.
    
    Returns:
        list: Lista de nomes de providers configurados
    """
    settings = get_settings()
    return settings.list_configured_providers()


def get_default_model(provider: str) -> str:
    """
    Retorna o modelo padrão de um provider.
    
    Args:
        provider: Nome do provider
    
    Returns:
        str: Nome do modelo padrão
    
    Raises:
        ValueError: Se provider for inválido
    """
    provider = provider.lower()
    
    if provider not in DEFAULT_MODELS:
        raise ValueError(
            f"Provider '{provider}' não existe. "
            f"Opções: {', '.join(DEFAULT_MODELS.keys())}"
        )
    
    return DEFAULT_MODELS[provider]


def validate_provider_config(provider: str) -> tuple[bool, str]:
    """
    Valida se um provider está corretamente configurado.
    
    Args:
        provider: Nome do provider
    
    Returns:
        tuple: (is_valid, error_message)
    """
    settings = get_settings()
    return settings.validate_provider(provider)


def get_provider_info(provider: str) -> dict:
    """
    Retorna informações sobre um provider.
    
    Args:
        provider: Nome do provider
    
    Returns:
        dict: Informações do provider
    """
    settings = get_settings()
    provider = provider.lower()
    
    if provider not in DEFAULT_MODELS:
        return {
            "provider": provider,
            "exists": False,
            "configured": False,
            "default_model": None
        }
    
    return {
        "provider": provider,
        "exists": True,
        "configured": settings.is_provider_configured(provider),
        "default_model": DEFAULT_MODELS[provider],
        "api_key_set": bool(settings.get_provider_key(provider))
    }


# ============================================
# TESTE DA FACTORY
# ============================================

async def test_llm_factory():
    """
    Testa a factory com todos os providers configurados.
    
    Útil para validar configuração durante desenvolvimento.
    """
    from ..utils.logger import logger
    
    logger.info("🧪 Testando LLM Factory...")
    
    providers = list_available_providers()
    
    if not providers:
        logger.error("❌ Nenhum provider configurado!")
        return False
    
    logger.info(f"📋 Providers configurados: {', '.join(providers)}")
    
    success = True
    
    for provider in providers:
        try:
            logger.info(f"\n🔍 Testando {provider}...")
            
            # Cria LLM
            llm = get_llm(provider, temperature=0.5, max_tokens=100)
            
            # Testa invocação simples
            response = await llm.ainvoke("Say 'Hello' in one word")
            
            logger.success(f"✅ {provider}: {response.content[:50]}")
            
        except Exception as e:
            logger.error(f"❌ {provider} falhou: {str(e)}")
            success = False
    
    if success:
        logger.success("\n🎉 Todos os providers funcionando!")
    else:
        logger.warning("\n⚠️ Alguns providers falharam")
    
    return success


# ============================================
# SCRIPT DE TESTE
# ============================================

if __name__ == "__main__":
    import asyncio
    
    print("="*60)
    print("LLM FACTORY - TESTE")
    print("="*60)
    
    # Lista providers disponíveis
    print("\n📋 Providers disponíveis:")
    for provider in DEFAULT_MODELS.keys():
        info = get_provider_info(provider)
        status = "✅ Configurado" if info["configured"] else "❌ Não configurado"
        print(f"  {provider}: {status} (modelo: {info['default_model']})")
    
    # Testa factory
    print("\n🧪 Executando testes...")
    asyncio.run(test_llm_factory())