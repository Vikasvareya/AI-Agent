from app.providers.ollama_provider import OllamaProvider
from app.agents.chat_agent import ChatAgent
from app.factories.provider_factory import ProviderFactory
from app.memory.conversation_memory import ConversationMemory



def main():
    # Create the provider
    provider = ProviderFactory.create()
    memory = ConversationMemory()

    # Inject the provider into the agent
    agent = ChatAgent(
        provider=provider,
        memory=memory,
    )

    print("=" * 50)
    print("🤖 AI Agent Framework")
    print("Type 'exit' to quit")
    print("=" * 50)

    while True:
        prompt = input("\nYou: ").strip()

        if not prompt:
            continue

        if prompt.lower() == "exit":
            print("Goodbye!")
            break

        response = agent.chat(prompt)

        print(f"\nAI: {response}")


if __name__ == "__main__":
    main()