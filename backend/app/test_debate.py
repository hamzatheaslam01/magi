from app.llm import OpenRouterProvider
from app.real_agents import RealAgent
from app.models import AgentName
from app.debate import DebateEngine


provider = OpenRouterProvider(
    model="openai/gpt-oss-20b"
)

agents = [
    RealAgent(AgentName.MELCHIOR, provider),
    RealAgent(AgentName.BALTHASAR, provider),
    RealAgent(AgentName.CASPER, provider),
]

engine = DebateEngine(agents)

question = "Should a startup build its application using microservices?"

state = engine.start(question)

print()
print("=" * 60)
print("QUESTION")
print("=" * 60)
print(state.question)

print()
print("=" * 60)
print("FINAL DECISIONS")
print("=" * 60)

for decision in state.decisions:

    print()
    print(decision.agent.value.upper())
    print("-" * 40)
    print("VERDICT:", decision.verdict.value.upper())
    print("CONFIDENCE:", decision.confidence)
    print("SEVERITY:", decision.severity.value)
    print()
    print("SUMMARY:")
    print(decision.summary)

print()
print("=" * 60)
print("DEBATE MESSAGES")
print("=" * 60)

for message in state.messages:

    print(
        f"[Round {message.round_number}] "
        f"{message.sender.value.upper()} "
        f"{message.message_type.value.upper()}:"
    )

    print(message.content)
    print()