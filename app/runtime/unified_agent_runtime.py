from app.agents.chat_agent import ChatAgent
from app.context.context_resolver import ContextResolver
from app.enums.action_type import ActionType
from app.executor.action_registry import ActionRegistry
from app.executor.executor import Executor
from app.executor.handlers.chat_handler import ChatHandler
from app.executor.handlers.tool_handler import ToolHandler
from app.memory.conversation_memory import ConversationMemory
from app.planner.intents.math_intent import MathIntent
from app.planner.intents.registry import IntentRegistry
from app.planner.intents.time_intent import TimeIntent
from app.planner.tool_planner import ToolPlanner
from app.providers.base_provider import BaseProvider
from app.tools.calculator_tool import CalculatorTool
from app.tools.time_tool import TimeTool
from app.tools.tool_manager import ToolManager
from app.prompts.agent_constitution import SHARED_AGENT_CONSTITUTION


class UnifiedAgentRuntime:
    def __init__(self, provider: BaseProvider):
        self.provider = provider
        self.intent_registry = IntentRegistry()
        self.intent_registry.register(MathIntent())
        self.intent_registry.register(TimeIntent())
        self.planner = ToolPlanner(self.intent_registry)

        self.tool_manager = ToolManager()
        self.tool_manager.register(TimeTool())
        self.tool_manager.register(CalculatorTool())

    def execute(
        self,
        *,
        owner_id: str,
        conversation_id: str,
        content: str,
        history: list[dict[str, str]],
        model: str | None = None,
        extra_messages: list[dict[str, str]] | None = None,
        activity_callback=None,
    ) -> str:
        del owner_id, conversation_id
        memory = ConversationMemory()
        prior_history = list(history)
        if (
            prior_history
            and prior_history[-1].get("role") == "user"
            and prior_history[-1].get("content") == content
        ):
            prior_history = prior_history[:-1]
        for message in prior_history:
            role = message.get("role")
            message_content = message.get("content")
            if role in ("user", "assistant") and isinstance(message_content, str):
                memory.save(role, message_content)

        context_resolver = ContextResolver()
        for message in prior_history:
            if message.get("role") == "user":
                context_resolver.resolve(message["content"])

        normalized_content = context_resolver.resolve(content)

        runtime_extra_messages = list(extra_messages or [])
        if not any(
            message.get("role") == "system"
            for message in runtime_extra_messages
        ):
            runtime_extra_messages.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "You are the ChatAgent in the AI Brain platform. "
                        f"{SHARED_AGENT_CONSTITUTION} "
                        "Be clear, accurate, and concise."
                    ),
                },
            )

        action_registry = ActionRegistry()
        action_registry.register(
            ActionType.TOOL,
            ToolHandler(self.tool_manager),
        )
        action_registry.register(
            ActionType.CHAT,
            ChatHandler(
                self.provider,
                memory,
                model=model,
                extra_messages=runtime_extra_messages,
            ),
        )
        plan = self.planner.plan(normalized_content)
        if activity_callback:
            activity_callback(
                "context.resolved",
                "completed",
                "Conversation context resolved.",
                {},
            )
            activity_callback(
                "cognitive.context.completed",
                "completed",
                "Conversation context retrieved.",
                {},
            )
            activity_callback(
                "cognitive.planning.started",
                "running",
                "Preparing an execution plan.",
                {},
            )
            activity_callback(
                "cognitive.planning.completed",
                "completed",
                "Execution plan created.",
                {},
            )
            intent_name = (
                "MathIntent"
                if plan.steps and plan.steps[0].args.get("tool") == "calculator"
                else "TimeIntent"
                if plan.steps and plan.steps[0].args.get("tool") == "time"
                else None
            )
            if intent_name:
                activity_callback(
                    "intent.selected",
                    "completed",
                    f"{intent_name} selected.",
                    {"intent": intent_name},
                )
            if plan.steps and plan.steps[0].args.get("tool"):
                tool_name = plan.steps[0].args["tool"]
                activity_callback(
                    "tool.selected",
                    "completed",
                    f"{tool_name.title()} tool selected.",
                    {"tool": tool_name},
                )
                activity_callback(
                    "tool.started",
                    "running",
                    (
                        f"Resolving timezone: {plan.steps[0].args['timezone']}"
                        if tool_name == "time" and plan.steps[0].args.get("timezone")
                        else f"Executing {tool_name.title()} tool."
                    ),
                    {"tool": tool_name, **plan.steps[0].args},
                )
                if tool_name == "time" and plan.steps[0].args.get("timezone"):
                    activity_callback(
                        "timezone.resolved",
                        "completed",
                        f"Timezone resolved: {plan.steps[0].args['timezone']}.",
                        {
                            "timezone": plan.steps[0].args["timezone"],
                            "location": plan.steps[0].args.get("location"),
                        },
                    )
        try:
            agent = ChatAgent(
            memory=memory,
            planner=self.planner,
            executor=Executor(action_registry),
            context_resolver=context_resolver,
            )
            result = agent.chat(normalized_content)
        except Exception as exc:
            if activity_callback:
                activity_callback(
                    "tool.failed",
                    "failed",
                    "The selected tool could not complete.",
                    {"error": type(exc).__name__},
                )
                activity_callback(
                    "execution.failed",
                    "failed",
                    "Execution could not be completed.",
                    {},
                )
            raise
        if activity_callback:
            activity_callback(
                "tool.completed",
                "completed",
                "Tool execution completed.",
                {},
            ) if plan.steps and plan.steps[0].args.get("tool") else None
            activity_callback(
                "execution.completed",
                "completed",
                "Execution completed.",
                {},
            )
        return result
