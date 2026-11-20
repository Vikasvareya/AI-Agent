from app.agents.agent_registry import AgentRegistry
from app.agents.shared_memory import SharedMemory


class CoordinatorAgent:
    def __init__(
        self,
        registry: AgentRegistry,
        shared_memory: SharedMemory,
        default_agent: str,
    ):
        self.registry = registry
        self.shared_memory = shared_memory
        self.default_agent = default_agent

    def route(self, prompt: str, *, agent_name: str | None = None) -> str:
        target_name = agent_name or self._match_agent(prompt) or self.default_agent
        target = self.registry.get(target_name)
        if target is None:
            raise ValueError(f"No agent registered as '{target_name}'.")

        self.shared_memory.publish("coordinator", target_name, prompt)
        result = target.chat(prompt)
        self.shared_memory.set(f"result:{target_name}", result)
        self.shared_memory.publish(target_name, "coordinator", result)
        return result

    def chat(self, prompt: str) -> str:
        return self.route(prompt)

    def _match_agent(self, prompt: str) -> str | None:
        normalized = prompt.lower()
        for name in self.registry.names():
            if name.lower() in normalized:
                return name
        return None
