from app.debate import DebateEngine
from app.llm.openrouter import OpenRouterProvider


provider = OpenRouterProvider(
    model="openrouter/free"
)

engine = DebateEngine(provider)


question = (
    "Should I learn C++ before learning Python?"
)


state = engine.start(question)


print("\n")
print("=" * 70)
print("                         MAGI")
print("=" * 70)

print("\nQUESTION:")
print(question)


print("\n")
print("=" * 70)
print("FINAL DECISIONS")
print("=" * 70)

for decision in state.decisions:

    print(
        f"\n{decision.agent.value.upper()}"
    )

    print(
        f"VERDICT: "
        f"{decision.verdict.value.upper()}"
    )

    print(
        f"CONFIDENCE: "
        f"{decision.confidence}"
    )

    print(
        f"SUMMARY: "
        f"{decision.summary}"
    )


print("\n")
print("=" * 70)
print("                         DEBATE")
print("=" * 70)

for message in state.messages:

    print(
        f"\n[ROUND {message.round_number}] "
        f"{message.sender.value.upper()} "
        f"{message.message_type.value.upper()}"
    )

    print(message.content)