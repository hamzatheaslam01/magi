from app.llm.openrouter import OpenRouterProvider
from app.models import AgentName
from app.real_agents import RealAgent


# Use the same free model you configured for MAGI.
MODEL = "openrouter/free"

provider = OpenRouterProvider(model=MODEL)

agents = [
    RealAgent(AgentName.MELCHIOR, provider),
    RealAgent(AgentName.BALTHASAR, provider),
    RealAgent(AgentName.CASPER, provider),
]

question = "Should I confront a friend who repeatedly disrespects them?"


print()
print("INITIAL POSITIONS")
print("=" * 60)


for agent in agents:

    print()
    print(f"Testing {agent.name.value.upper()}...")
    print("-" * 60)

    try:

        decision = agent.initial_position(question)

        if decision is None:
            print("❌ RETURNED NONE")

        else:
            print("✅ SUCCESS")
            print(f"Verdict: {decision.verdict.value}")
            print(f"Confidence: {decision.confidence}")
            print(f"Severity: {decision.severity.value}")
            print(f"Summary: {decision.summary}")

    except Exception as e:

        print("❌ ERROR")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {e}")