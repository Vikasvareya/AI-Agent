# Executor

The executor dispatches framework plans/actions through registered handlers
and tools. Plan-step execution is sequential in the current executor path;
the separate workflow engine supports bounded parallel DAG execution.

Execution is in-process. The executor does not create an operating-system
sandbox or isolate arbitrary code. Errors and retry behavior depend on the
specific agent/handler; the ReAct and reflective agents are bounded
prototypes, not an unrestricted autonomous loop.

See `app/executor/`, `app/agents/react_agent.py`, and
`app/agents/reflective_agent.py`.
