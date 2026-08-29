from app.llm import OpenRouterProvider
from app.real_agents import RealAgent
from app.models import AgentName
from app.debate import DebateEngine
from app.synthesis import MagiSynthesizer


provider = OpenRouterProvider(
    model="openrouter/free"
)

agents = [
    RealAgent(AgentName.MELCHIOR, provider),
    RealAgent(AgentName.BALTHASAR, provider),
    RealAgent(AgentName.CASPER, provider),
]

engine = DebateEngine(agents)

question = "Should a startup build its application using microservices?"

state = engine.start(question)

synthesizer = MagiSynthesizer(provider)

result = synthesizer.synthesize(
    question=state.question,
    decisions=state.decisions,
    messages=state.messages,
)

print()
print("=" * 60)
print("MAGI SYNTHESIS")
print("=" * 60)

print()
print("FINAL VERDICT:", result.verdict.value.upper())
print("CONFIDENCE:", result.confidence)

print()
print("SYNTHESIS:")
print(result.synthesis)

print()
print("KEY AGREEMENTS:")
for item in result.key_agreements:
    print("-", item)

print()
print("KEY DISAGREEMENTS:")
for item in result.key_disagreements:
    print("-", item)

print()
print("KEY RISKS:")
for item in result.key_risks:
    print("-", item)

print()
print("RECOMMENDATION:")
print(result.recommendation)