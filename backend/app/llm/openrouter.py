import os

from dotenv import load_dotenv
from openai import OpenAI

from app.llm import LLMProvider


load_dotenv()


class OpenRouterProvider(LLMProvider):

    def __init__(self, model: str):
        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set."
            )

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        self.model = model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        )

        return response.choices[0].message.content