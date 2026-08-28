from app.agents import get_profile
from app.models import AgentName


for agent in AgentName:
    profile = get_profile(agent)

    print(f"\n{profile.name.value.upper()}")
    print(f"Role: {profile.role}")
    print(f"Objective: {profile.objective}")

    print("Priorities:")
    for priority in profile.priorities:
        print(f"  - {priority}")

    print("Rules:")
    for rule in profile.behavioral_rules:
        print(f"  - {rule}")