from app.llm.openrouter import OpenRouterProvider


provider = OpenRouterProvider(
    model="openrouter/free"
)


response = provider.generate(
    system_prompt=(
        "You are a helpful AI assistant. "
        "Answer clearly and concisely."
    ),
    user_prompt="Explain what multi-agent AI means in one paragraph.",
)


print("\nMODEL RESPONSE:\n")
print(response)