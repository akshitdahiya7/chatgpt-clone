from app.llm.factory import LLMFactory
from app.llm.models import LLMResponse
from app.prompt.models import Prompt


class LLMService:

    def __init__(self):
        self.provider = LLMFactory.get_provider()

    def generate(
        self,
        prompt: Prompt,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
    ) -> LLMResponse:

        return self.provider.generate(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

    def stream(
        self,
        prompt: Prompt,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
    ):
        return self.provider.stream(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
