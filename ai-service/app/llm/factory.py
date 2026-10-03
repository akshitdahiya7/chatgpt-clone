from app.settings import get_settings


class LLMFactory:

    @staticmethod
    def get_provider():
        settings = get_settings()

        match settings.llm_provider:
            case "openai":
                from app.llm.providers.openai_compatible import (
                    OpenAICompatibleLLMProvider,
                )

                if not settings.openai_api_key:
                    raise ValueError(
                        "OPENAI_API_KEY is required when LLM_PROVIDER='openai'"
                    )

                return OpenAICompatibleLLMProvider(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                )

            case "ollama":
                from app.llm.providers.ollama import OllamaLLMProvider

                if not settings.ollama_base_url:
                    raise ValueError(
                        "OLLAMA_BASE_URL is required when LLM_PROVIDER='ollama'"
                    )

                return OllamaLLMProvider(
                    base_url=settings.ollama_base_url,
                    api_key=settings.ollama_api_key,
                )

            case _:
                raise ValueError(
                    f"Unsupported provider: {settings.llm_provider}"
                )
