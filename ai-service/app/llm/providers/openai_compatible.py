from openai import OpenAI

from app.llm.models import LLMResponse
from app.llm.providers.base import BaseLLMProvider
from app.prompt.models import Prompt


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    """Any backend that speaks the OpenAI chat-completions API.

    Covers OpenAI itself and GitHub Models, which is API-compatible:

        OpenAI         base_url=https://api.openai.com/v1        key=sk-...
        GitHub Models  base_url=https://models.github.ai/inference key=<PAT>
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
    ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or None,
        )

    def generate(
        self,
        prompt: Prompt,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> LLMResponse:

        response = self.client.chat.completions.create(
            model=model,
            messages=[
                message.to_dict()
                for message in prompt.messages
            ],
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
        )

    def stream(
        self,
        prompt: Prompt,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ):

        stream = self.client.chat.completions.create(
            model=model,
            messages=[
                message.to_dict()
                for message in prompt.messages
            ],
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
