# 🤖 AI Agent Framework

A production-oriented **AI Agent Framework** built completely **from scratch in Python** to understand how modern AI agents work internally instead of relying on high-level frameworks.

The goal is to design and implement every layer ourselves—from planning and execution to memory, tools, workflows, RAG, and multi-agent orchestration.

---

# 🎯 Vision

Build an extensible AI Agent Framework capable of evolving into an enterprise-grade platform with support for:

- ✅ Multiple LLM Providers
- ✅ Intelligent Planning Engine
- ✅ Tool Calling
- ✅ Context Awareness
- ✅ Conversation Memory
- ✅ Workflow Orchestration
- ⏳ Retrieval-Augmented Generation (RAG)
- ⏳ Plugin Architecture
- ⏳ Multi-Agent Collaboration
- ⏳ Model Context Protocol (MCP)
- ⏳ Human-in-the-Loop Workflows

---

# 🚀 Current Version

## **v0.2.0 – Intelligent Planning Foundation**

The framework now includes a clean layered architecture with:

- Context Resolution
- Intent Ranking (Priority + Confidence)
- Modular Planner
- Executor Pipeline
- Tool System
- Conversation Memory
- Logging
- Automated Testing

This version establishes the foundation for multi-step planning and future multi-agent capabilities.

---

# 🏗 High-Level Architecture

```text
                         User
                          │
                          ▼
                     ChatAgent
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
      ContextResolver         ConversationMemory
              │
              ▼
         ToolPlanner
              │
              ▼
       IntentRegistry
              │
              ▼
      Intent Ranking Engine
     (Priority + Confidence)
              │
              ▼
             Plan
              │
              ▼
          Executor
              │
              ▼
       ActionRegistry
        ┌──────────────┐
        ▼              ▼
  ToolHandler    ChatHandler
        │              │
        ▼              ▼
 ToolManager    LLM Provider
        │
 ┌──────┴────────┐
 ▼               ▼
CalculatorTool  TimeTool
```

---

# 🧠 Current Request Flow

```text
User
 │
 ▼
ChatAgent
 │
 ▼
ContextResolver
 │
 ▼
ConversationMemory
 │
 ▼
ToolPlanner
 │
 ▼
IntentRegistry
 │
 ▼
Intent Ranking
 │
 ▼
Execution Plan
 │
 ▼
Executor
 │
 ▼
ActionRegistry
 │
 ▼
Handler
 │
 ├── ToolHandler
 │       │
 │       ▼
 │   ToolManager
 │
 └── ChatHandler
         │
         ▼
    LLM Provider
```

---

# 📁 Project Structure

```text
app/
│
├── agents/
├── config/
├── context/
│   ├── context_resolver.py
│   ├── conversation_context.py
│   ├── entity_extractor.py
│   └── pronoun_resolver.py
│
├── enums/
├── exceptions/
├── executor/
│   ├── handlers/
│   ├── action_registry.py
│   └── executor.py
│
├── factories/
├── memory/
├── models/
├── planner/
│   ├── intents/
│   ├── models.py
│   ├── registry.py
│   └── tool_planner.py
│
├── providers/
├── tools/
├── utils/
└── tests/
```

---

# ✅ Completed Modules

### Core

- Configuration Loader
- Provider Factory
- Ollama Provider
- Conversation Memory
- Logging Utility

### Context Layer

- Context Resolver
- Conversation Context
- Entity Extraction
- Pronoun Resolution

### Planning Layer

- Planner
- Intent Registry
- Intent Ranking
- Math Intent
- Time Intent

### Execution Layer

- Executor
- Action Registry
- Tool Handler
- Chat Handler

### Tool Layer

- Tool Manager
- Calculator Tool
- Time Tool

### Testing

- Entity Extraction Tests
- Pronoun Resolution Tests
- Context Resolver Tests

---

# 🧠 Intent Ranking Engine

Unlike traditional rule-based routing, every intent now returns an `IntentMatch` object.

```python
IntentMatch(
    matched=True,
    confidence=0.95,
    priority=100,
)
```

The registry evaluates every registered intent before selecting the highest-ranked match.

Benefits:

- Priority-based routing
- Confidence scoring
- Easy extensibility
- Future AI-based intent classification

---

# 🧠 Context Resolution

Current capabilities:

- Entity Extraction
- Pronoun Resolution
- Conversation Context
- Multi-turn Understanding

Example:

```
User:
Tell me about Python.

User:
Who created it?

↓

Resolved:

Who created Python?
```

---

# 🧪 Testing

The framework uses **pytest** for automated testing.

Run all tests:

```bash
pytest
```

Current coverage includes:

- Entity Extraction
- Pronoun Resolution
- Context Resolution

---

# 🏛 Design Principles

This framework is intentionally built using production-oriented software engineering practices.

### Design Patterns

- Factory Pattern
- Strategy Pattern
- Registry Pattern
- Command Pattern
- Dependency Injection (Gradually Introducing)

### Engineering Principles

- SOLID Principles
- Layered Architecture
- Separation of Concerns
- Open/Closed Principle
- Clean Code
- Type Safety
- Test-Driven Refactoring

---

# 🛣 Development Roadmap

## ✅ Phase 1 — Foundation

- Configuration
- Providers
- Memory
- Tool System
- Planner
- Executor
- Context Resolver
- Intent Ranking
- Testing

---

## 🚧 Phase 2 — Advanced Planning Engine

- Multi-Step Plans
- Execution Pipeline
- Composite Plans
- Tool Chaining
- Planning Graph

---

## 🚧 Phase 3 — Plugin Architecture

- Plugin Loader
- Plugin Discovery
- Dynamic Registration
- Dependency Injection

---

## 🚧 Phase 4 — Memory & RAG

- Vector Memory
- Semantic Search
- Knowledge Base
- Retrieval-Augmented Generation

---

## 🚧 Phase 5 — Agent Runtime

- ReAct Loop
- Reflection
- Self Correction
- Long-Term Memory

---

## 🚧 Phase 6 — Multi-Agent System

- Agent Registry
- Coordinator Agent
- Shared Memory
- Message Bus
- Task Delegation

---

## 🚧 Phase 7 — Enterprise Features

- Workflow Engine
- Human Approval
- REST API
- WebSockets
- Observability
- Docker
- Kubernetes
- MCP Integration

---

# 🎓 Learning Philosophy

This project is intentionally built **without relying on AI abstraction frameworks**.

Instead of using libraries that hide the implementation details, every architectural layer is implemented from scratch to understand:

- How planners work
- How executors work
- How tools are invoked
- How context is managed
- How memories are stored
- How workflows execute
- How modern AI agents are designed internally

The objective is to build an extensible framework that is educational, production-oriented, and capable of evolving into a complete AI platform.

---

# 📄 License

MIT License

---

# ⭐ Future Goal

By the final version, this framework aims to support:

- Multi-Agent Collaboration
- Workflow Automation
- Plugin Ecosystem
- RAG Pipelines
- Human-in-the-Loop
- MCP
- Distributed Execution
- Cloud Deployment
- Python Package (`pip install`)
- Production Dashboard

**Build the framework. Understand every layer. Own the architecture.**