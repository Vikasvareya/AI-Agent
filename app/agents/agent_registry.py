from typing import Protocol


class Agent(Protocol):
    def chat(self, prompt: str) -> str:
        ...


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def register(self, name: str, agent: Agent) -> None:
        if not name.strip():
            raise ValueError("Agent name cannot be empty.")
        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered.")
        self._agents[name] = agent

    def get(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def names(self) -> list[str]:
        return list(self._agents)
