import json
import os
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from agent.graph import create_graph


def create_user_profile():
    """
    Collect user details from the terminal and save them
    to data/user.json.
    """

    print("\n🛍️ Welcome to StyleAI")
    print("Let's create your shopping profile.\n")

    name = input("Name: ").strip()
    age = int(input("Age: ").strip())
    gender = input("Gender (male/female/unisex): ").strip().lower()
    city = input("City: ").strip()

    total_budget = int(
        input("Total shopping budget (₹): ").strip()
    )

    per_item_budget = int(
        input("Maximum budget per item (₹): ").strip()
    )

    categories = input(
        "Preferred categories (comma separated): "
    ).strip()

    occasions = input(
        "Occasions (comma separated): "
    ).strip()

    # Age Group
    if age < 18:
        age_group = "16-18"
    elif age <= 24:
        age_group = "18-24"
    elif age <= 34:
        age_group = "25-34"
    elif age <= 44:
        age_group = "35-44"
    else:
        age_group = "45+"

    now = datetime.now(timezone.utc).isoformat()

    profile = {
        "user_id": f"usr-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "name": name,
        "age": age,
        "age_group": age_group,
        "gender": gender,
        "location": {
            "city": city,
            "state": "",
            "currency": "INR"
        },
        "budget": {
            "total": total_budget,
            "per_item_max": per_item_budget,
            "flexibility_percent": 10
        },
        "style_preferences": {
            "categories": [
                x.strip().lower()
                for x in categories.split(",")
                if x.strip()
            ],
            "avoid": [],
            "favorite_colors": [],
            "favorite_fabrics": [],
            "occasions": [
                x.strip().lower()
                for x in occasions.split(",")
                if x.strip()
            ]
        },
        "body_profile": {},
        "photo_path": "",
        "created_at": now,
        "last_active": now
    }

    os.makedirs("data", exist_ok=True)

    with open("data/user.json", "w") as f:
        json.dump(profile, f, indent=2)

    print("\n✅ Profile created successfully!\n")

    return profile

def run_shopping_assistant(graph):

    config = {
        "configurable": {
            "thread_id": "shopping-user"
        }
    }


    # Store profile in memory
    graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=f"""
                    Show me the user profile
                    """
                )
            ]
        },
        config=config
    )

    # Welcome message
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content="""
                    Welcome the user to the shopping platform.
                    Introduce yourself as a shopping assistant.
                    Mention personalized recommendations,
                    deals, cart management and budget-aware shopping.
                    """
                )
            ]
        },
        config=config
    )

    print("\n🤖 Assistant:")
    print(result["messages"][-1].content)

    print("\n(Type 'exit' to quit)\n")

    while True:

        query = input("🛒 You: ")

        if query.lower() in {"exit", "quit", "bye"}:
            print("\n👋 Thank you for shopping with us!")
            break

        result = graph.invoke(
            {
                "messages": [
                    HumanMessage(content=query)
                ]
            },
            config=config
        )

        print(
            f"\n🤖 Assistant: "
            f"{result['messages'][-1].content}\n"
        )

def main():
    """
    Entry point for the shopping assistant application.

    Workflow:
    1. Collect user details from the terminal.
    2. Save the profile to data/user.json.
    3. Create the LangGraph agent.
    4. Load the user profile into agent memory.
    5. Display a personalized welcome message.
    6. Start the interactive shopping chat session.
    """

    try:
        print("\n🛍️ Starting StyleAI Shopping Assistant...\n")

        # Create user profile and save to data/user.json
        create_user_profile()

        # Initialize graph
        graph = create_graph()

        # Launch chatbot
        run_shopping_assistant(graph)

    except KeyboardInterrupt:
        print("\n\n👋 Session ended by user.")

    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()