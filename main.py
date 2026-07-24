from app.config.loader import Loader
from app.providers.ollama_provider import OllamaProvider
from app.agents.chat_agent import ChatAgent
from app.factories.provider_factory import ProviderFactory
from app.memory.conversation_memory import ConversationMemory
from app.tools.tool_manager import ToolManager
from app.tools.calculator_tool import CalculatorTool
from app.tools.time_tool import TimeTool
from app.planner.tool_planner import ToolPlanner
from app.planner.intents.registry import IntentRegistry
from app.planner.intents.math_intent import MathIntent
from app.planner.intents.time_intent import TimeIntent
from app.executor.executor import Executor
from app.executor.action_registry import ActionRegistry
from app.executor.handlers.tool_handler import ToolHandler
from app.executor.handlers.chat_handler import ChatHandler
from app.enums.action_type import ActionType


def main():
    # Create the provider

    registry = IntentRegistry()
    loader = Loader()
    settings = loader.load()
    provider_factory = ProviderFactory(settings)
    provider = provider_factory.create()
    memory = ConversationMemory()
    tool_manager = ToolManager()

    action_registry = ActionRegistry()

    tool_manager.register(
    CalculatorTool()
     )

    tool_manager.register(
    TimeTool()
     )


    action_registry.register(
        ActionType.TOOL,
        ToolHandler(
            tool_manager,
        ),
    )

    action_registry.register(
        ActionType.CHAT,
        ChatHandler(
            provider,
            memory,
        ),
    )
    
    registry.register_default_intents()

    planner = ToolPlanner(
        registry,
    )


    executor = Executor(
        action_registry,
    )

    # Inject the provider into the agent
    agent = ChatAgent(
        memory=memory,
        planner=planner,
        executor=executor,
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