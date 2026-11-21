# Project Vision

## Purpose

AI Brain is the product identity for this extensible Python agent framework
and evolving workspace for planning, tools, memory, workflows, chat, and coding
assistance. The long-term goal is a dependable cognitive platform that can be
extended by developers and operated responsibly—not a claim that the current
repository is already production-scale.

The canonical architecture is
[AI_BRAIN_MASTER_ARCHITECTURE.md](./AI_BRAIN_MASTER_ARCHITECTURE.md).

## Intended users

- Developers learning, evaluating, or extending agent-runtime components.
- Operators integrating the current chat, workflow, and coding-workspace APIs.
- Future platform teams that need governed, observable agent services.

## Product principles

1. Make capabilities and limitations visible; distinguish working software
   from prototypes and roadmap proposals.
2. Keep model providers, tools, memory, workflows, and user interfaces behind
   explicit boundaries so they can evolve independently.
3. Default to bounded context, explicit permissions, safe workspace scope, and
   human review for writes.
4. Prefer measurable reliability, security, and operability over feature
   breadth.
5. Treat tenant isolation, secrets, external data, and generated code as
   first-class risks.
6. Preserve an educational, inspectable implementation while establishing
   tests and operational evidence for any production claim.

## Current product shape

The repository currently contains a Python framework, a threaded HTTP API,
workflow operator UI, React chat, and a separate administrator coding
workspace. The current provider implementation is Ollama. Some agent,
memory, plugin, MCP, workflow, and observability components are prototypes or
local-process foundations. See [Current Implementation](./CURRENT_IMPLEMENTATION.md)
and [Implementation Status](./IMPLEMENTATION_STATUS.md).

## Long-term direction

The intended direction is a modular service platform with secure identity and
tenant boundaries, durable execution, provider choice, governed extensions,
robust evaluation, and independently scalable services. Each capability must
earn its status through an implementation, tests, security review, operational
evidence, and documentation. These are goals, not current guarantees.

ARES is a proposed research and evolution track described in
[ARES Research and Evolution](./ARES_RESEARCH_EVOLUTION.md). Its acronym
expansion, detailed requirements, and implementation are not established in
the repository; no ARES capability should be treated as available today.

## Non-goals for the current release

- Claiming high availability, heavy-traffic readiness, or tenant isolation.
- Presenting model training, image/video generation, or autonomous execution
  as implemented.
- Running untrusted code, shell commands, or arbitrary plugins in the API
  process.
- Treating examples and deployment manifests as a production certification.
