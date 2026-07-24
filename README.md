# 🤖 AI Agent Framework

A production-oriented AI Agent Framework built **from scratch in
Python** to understand how modern AI agents work internally instead of
relying on abstraction libraries.

## 🎯 Vision

Build a modular, extensible framework that can evolve into a
production-ready AI platform supporting:

-   Multiple LLM providers
-   Intelligent planning
-   Tool execution
-   Context awareness
-   Workflow orchestration
-   Retrieval-Augmented Generation (RAG)
-   Multi-agent collaboration
-   Model Context Protocol (MCP)

------------------------------------------------------------------------

# 🚀 Current Version

**v0.8 -- Core Architecture Complete**

The framework has a clean layered architecture and is ready for
intelligent capabilities.

## 🏗 Architecture

``` text
                   User
                     │
                     ▼
                ChatAgent
                     │
         Save Conversation
                     │
                     ▼
               ToolPlanner
                     │
                     ▼
             IntentRegistry
          ┌─────────┴─────────┐
          ▼                   ▼
     MathIntent          TimeIntent
                     │
                     ▼
                    Plan
                     │
                     ▼
                 Executor
                     │
                     ▼
              ActionRegistry
          ┌─────────┴─────────┐
          ▼                   ▼
      ToolHandler       ChatHandler
          │                   │
          ▼                   ▼
    ToolManager         OllamaProvider
          │
   ┌──────┴──────┐
   ▼             ▼
CalculatorTool  TimeTool
```

## 📁 Project Structure

``` text
app/
├── agents/
├── config/
├── enums/
├── executor/
│   ├── handlers/
│   └── action_registry.py
├── factories/
├── memory/
├── models/
├── planner/
│   └── intents/
├── providers/
└── tools/
```

## ✅ Completed Modules

-   Configuration Loader
-   Provider Factory
-   Ollama Provider
-   Conversation Memory
-   Tool System
-   Planner Layer
-   Intent Registry
-   Executor Layer
-   Action Registry

## 🧠 Design Patterns

-   Factory Pattern
-   Strategy Pattern
-   Registry Pattern
-   Command Pattern
-   Dependency Injection
-   Layered Architecture
-   SOLID Principles

## 🔄 Request Flow

``` text
User
 ↓
ChatAgent
 ↓
ConversationMemory
 ↓
ToolPlanner
 ↓
IntentRegistry
 ↓
Intent
 ↓
Plan
 ↓
Executor
 ↓
ActionRegistry
 ↓
Handler
 ↓
Tool / LLM
```

## 🛣 Roadmap

1.  Context Resolver
2.  Memory Manager
3.  Search Tools
4.  Workflow Engine
5.  RAG
6.  Multi-Agent System
7.  MCP Integration

## 🎓 Purpose

This project is designed as an educational and production-oriented
framework to deeply understand AI agent architecture while remaining
clean, extensible, and maintainable.
