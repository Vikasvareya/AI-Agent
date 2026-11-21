from app.config.loader import Loader
from app.factories.provider_factory import ProviderFactory
from app.runtime.unified_agent_runtime import UnifiedAgentRuntime


def main():
    loader = Loader()
    settings = loader.load()
    provider_factory = ProviderFactory(settings)
    provider = provider_factory.create()
    runtime = UnifiedAgentRuntime(provider)
    terminal_history: list[dict[str, str]] = []

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

        response = runtime.execute(
            owner_id="terminal",
            conversation_id="terminal",
            content=prompt,
            history=terminal_history,
        )
        terminal_history.extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": str(response)},
        ])

        print(f"\nAI: {response}")


if __name__ == "__main__":
    main()