# Planning Engine

The planner layer provides intent matching and plan data structures. The
default intent registry includes math and time intents and selects a match by
priority and confidence. This is a deterministic routing mechanism, not a
general language-model planning system.

An `ExecutionPlan` contains `ExecutionStep` objects, their action arguments,
dependencies, and status. `ExecutionContext` carries variables, results, and
metadata. These planning models are separate from DAG workflow definitions.

See `app/planner/` and the [executor guide](./12-executor.md). Dependency
validation and scheduling behavior must be confirmed in the executor
implementation; a plan model having dependency fields does not itself imply
parallel plan execution.
