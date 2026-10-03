from abc import ABC, abstractmethod

from app.llm.models import LLMResponse
from app.prompt.models import Prompt


class BaseLLMProvider(ABC):

    @abstractmethod
    def generate(
        self,
        prompt: Prompt,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def stream(
        self,
        prompt: Prompt,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ):
        ...
