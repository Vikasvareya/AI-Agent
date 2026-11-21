# AI Brain Master Architecture

## Product identity

**AI Brain** is the long-term architecture name for this repository's autonomous
cognitive intelligence platform. AI Brain means an engineered, governable
cognitive architecture: it does not claim consciousness, biological
equivalence, unlimited intelligence, or guaranteed autonomy.

The platform direction is: **One Cognitive Core. Many specialized agents.
Expandable skills. Multiple models. Continuously improving capabilities.**

The current repository is a foundation for this direction. It contains a
Python framework, chat API and UI, provider adapters, bounded agent prototypes,
memory components, tools, workflows, MCP building blocks, and a scoped coding
workspace. It does not yet implement a complete Cognitive Core or autonomous
self-evolution.

See [Current Implementation](./CURRENT_IMPLEMENTATION.md),
[Implementation Status](./IMPLEMENTATION_STATUS.md),
[Known Limitations](./KNOWN_LIMITATIONS.md), and
[Product Roadmap](./PRODUCT_ROADMAP.md) for evidence-based release boundaries.

## Cognitive architecture

The Cognitive Core is an orchestration concept, not a large proposed class.
It should coordinate independent modules and preserve their existing
interfaces.

| Cognitive system | Long-term responsibility | Current evidence |
| --- | --- | --- |
| 1. Perception | Text and future multimodal, document, sensor, and environmental inputs | Text chat and selected workspace files; no general media/sensor pipeline |
| 2. Reasoning | Decomposition, alternatives, reflection, and strategy selection | Intent/rule planning, ReAct and reflective prototypes, hardened sequential Executor v2 |
| 3. Memory | Working, short/long-term, episodic, semantic, procedural, and shared memory | Conversation, JSON long-term, in-memory vector, and shared-memory prototypes |
| 4. Executive/goal management | Goals, prioritization, plans, delegation, monitoring, and verification | Intent plans and workflow DAG foundations; no goal engine |
| 5. Learning | Verified feedback, strategy/skill improvement, and model training separated by lifecycle | No learned-weight training; no verified learning pipeline |
| 6. Social/multi-agent | Structured tasking, delegation, collaboration, review, and aggregation | Permission-controlled fan-out, durable task/message records, and result aggregation; execution remains process-local |
| 7. Autonomous research | Evidence gathering, source evaluation, hypotheses, and reports | Optional Brave query and search citation support |
| 8. Temporal | Historical analysis, present monitoring, and uncertain scenario simulation | Health/workflow events; no temporal intelligence engine |
| 9. Self-repair | Diagnostics, patch proposals, tests, recovery, and rollback | Scoped coding proposals and workflow/coding fail-safe recovery |
| 10. Innovation/capability creation | Missing-capability detection, experiments, benchmarks, and approval | Not implemented |
| 11. Model intelligence | Model discovery, datasets, training, evaluation, versioning, and deployment | Ollama/OpenAI-compatible inference only |
| 12. Safety/governance | Least privilege, authorization, auditing, approvals, isolation, and rollback | Static auth, workspace scoping, manual patch review, and audit foundations |

## Current agent ecosystem

- **ChatAgent:** conversational context, intent planning, tool/executor dispatch,
  and in-process conversation memory.
- **CodingAgent:** workspace-scoped source analysis and validated patch
  proposals. Writes and patch applications require the configured permission
  boundary; shell execution is not available.
- **ReActAgent:** bounded reason/action/observe/retry trace around the existing
  planner and executor. Trace text is implementation metadata, not evidence of
  hidden model reasoning.
- **ReflectiveAgent:** bounded result usability checks and retries. It is a
  marker-based prototype, not general outcome evaluation.
- **CoordinatorAgent:** explicit-name, name-match, or default routing to one
  registered agent.
- **AgentRegistry:** in-process agent name registration and lookup.
- **SharedMemory:** process-local values and message history. It is not a
  distributed message bus.

Future Research, Planning, Testing, Reviewing, Mechanical, Robotics, Model
Training, Innovation, and Language Engineering agents are roadmap concepts,
not implemented classes.

## Skills, tools, and capabilities

The architecture separates:

- **Agent:** specialized autonomous actor.
- **Skill:** reusable knowledge and procedures.
- **Tool:** executable capability with explicit input/output and permissions.
- **Model:** parameterized inference system.
- **Workflow:** orchestrated operation sequence.
- **Memory:** stored information or experience.

Dynamic skill and tool creation require discovery, versioning, tests, security
review, permission grants, human approval, revocation, and negative-result
records. A generated tool must never imply execution permission. Generated code
and languages must not execute inside the unrestricted API process.

## Model and innovation boundaries

Provider configuration and model inference are not model training. The future
Model Studio must distinguish:

- model configuration and selection;
- dataset creation and validation;
- supervised fine-tuning and preference optimization;
- pretraining and continued pretraining;
- embedding/reranker or multimodal training;
- evaluation and benchmarking;
- versioned deployment and rollback.

No current source verifies any training, fine-tuning, new-language creation,
robotics, or autonomous physical actuation.

## Self-repair and evolution

Task-level improvement is a bounded execute-observe-reflect-correct-retry
cycle. Platform-level evolution requires isolated experiments, security review,
approval, versioned deployment, monitoring, and rollback. Production code must
never be rewritten without an independent recovery mechanism.

## Temporal and physical intelligence

Future temporal capabilities must separate historical evidence, live state,
and scenario estimates. Predictions require assumptions and uncertainty and
must not be presented as facts.

Robotics begins with research and simulation. Hardware actuation requires
approved adapters, limits, emergency stops, collision controls, and human
safety procedures.

## Safety and governance

Every agent, skill, tool, model, workflow, and external integration requires:

- explicit permissions and least privilege;
- resource, network, filesystem, and time limits;
- attributable audit records;
- human approval for consequential actions;
- secret and data-governance controls;
- testable failure and rollback behavior;
- revocation and emergency stop.

Model outputs, source files, search results, session history, and plugin data
are untrusted inputs. UI restrictions are not authorization.

## Studio mapping

The existing UI should be described by its verified surfaces only:

- **Agent Studio:** future interface; current registry/routing is a prototype.
- **Model Studio:** future interface; current UI has provider/model selection.
- **Capability & Innovation Studio:** future interface; current plugin/MCP and
  coding boundaries are foundations.
- **Workflow Studio:** future interface for a broader cognitive platform; the
  existing workflow operator UI is an implemented in-process workflow surface.

No future studio capability should appear as an available button or completed
feature.

## Development phases

1. Existing foundation.
2. Planning and execution hardening.
3. Agent runtime and structured multi-agent collaboration.
4. Advanced memory, RAG, provenance, and evaluation.
5. Governed dynamic skill and tool intelligence.
6. Cognitive Core goal/reasoning/executive coordination.
7. Research and self-repair with isolated experimentation.
8. Model Studio datasets, training, evaluation, registry, and deployment.
9. Innovation and language-engineering research.
10. Temporal intelligence.
11. Robotics and physical intelligence.
12. Controlled, measured autonomous cognitive evolution.

The phases are evidence gates, not delivery commitments or dates.
