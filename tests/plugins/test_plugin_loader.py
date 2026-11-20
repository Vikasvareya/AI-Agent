from app.plugins.plugin_loader import PluginLoader
from app.planner.intents.registry import IntentRegistry
from app.tools.tool_manager import ToolManager


def test_plugin_loader_registers_plugin_intents_and_tools():
    intent_registry = IntentRegistry()
    tool_manager = ToolManager()
    loader = PluginLoader(
        intent_registry,
        tool_manager,
    )

    from app.plugins.math.plugin import MathPlugin

    plugin = loader.load(MathPlugin())

    assert loader.loaded_plugins == [plugin]
    assert intent_registry.get_matching_intent("2 + 2") is not None
    assert tool_manager.get("calculator") is not None


def test_plugin_loader_discovers_math_plugin():
    intent_registry = IntentRegistry()
    tool_manager = ToolManager()
    loader = PluginLoader(
        intent_registry,
        tool_manager,
    )

    plugins = loader.discover()

    assert len(plugins) >= 1
    assert tool_manager.get("calculator") is not None
