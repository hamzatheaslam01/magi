import asyncio

from app.llm import OpenRouterProvider
from app.real_agents import RealAgent
from app.models import AgentName


provider = OpenRouterProvider(
    model="openai/gpt-oss-20b"
)

agents = [
    RealAgent(name, provider)
    for name in AgentName
]


async def main():
    question = "Should a startup build its application using microservices?"

    results = await asyncio.gather(
        *[
            asyncio.to_thread(
                agent.initial_position,
                question,
            )
            for agent in agents
        ],
        return_exceptions=True,
    )

    for agent, result in zip(agents, results):
        print()
        print("=" * 60)
        print(agent.name.value.upper())
        print("=" * 60)

        if isinstance(result, Exception):
            print("ERROR:", type(result).__name__)
            print("MESSAGE:", result)
        else:
            print("SUCCESS")
            print("VERDICT:", result.verdict.value)
            print("CONFIDENCE:", result.confidence)


if __name__ == "__main__":
    asyncio.run(main())