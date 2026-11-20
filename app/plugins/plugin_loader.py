import importlib
import inspect
import pkgutil
from types import ModuleType

from app.plugins.base_plugin import BasePlugin
from app.planner.intents.registry import IntentRegistry
from app.tools.tool_manager import ToolManager


class PluginLoader:
    """
    Loads plugins and registers their intents and tools.
    """

    def __init__(
        self,
        intent_registry: IntentRegistry,
        tool_manager: ToolManager,
    ):
        self.intent_registry = intent_registry
        self.tool_manager = tool_manager
        self.loaded_plugins: list[BasePlugin] = []

    def load(
        self,
        plugin: BasePlugin,
    ) -> BasePlugin:
        for intent in plugin.get_intents():
            self.intent_registry.register(intent)

        for tool in plugin.get_tools():
            self.tool_manager.register(tool)

        self.loaded_plugins.append(plugin)
        return plugin

    def discover(
        self,
        package_name: str = "app.plugins",
    ) -> list[BasePlugin]:
        package = importlib.import_module(package_name)
        loaded: list[BasePlugin] = []

        for module_info in pkgutil.iter_modules(
            package.__path__,
        ):
            if module_info.name.startswith("_"):
                continue

            subpackage_name = (
                f"{package_name}.{module_info.name}"
            )
            subpackage = importlib.import_module(
                subpackage_name,
            )
            loaded.extend(
                self._discover_in_module(subpackage)
            )

            if hasattr(subpackage, "__path__"):
                for plugin_module in pkgutil.iter_modules(
                    subpackage.__path__,
                ):
                    module_name = (
                        f"{subpackage_name}.{plugin_module.name}"
                    )
                    module = importlib.import_module(
                        module_name,
                    )
                    loaded.extend(
                        self._discover_in_module(module)
                    )

        return loaded

    def _discover_in_module(
        self,
        module: ModuleType,
    ) -> list[BasePlugin]:
        loaded: list[BasePlugin] = []

        for _, plugin_type in inspect.getmembers(
            module,
            inspect.isclass,
        ):
            if (
                plugin_type is BasePlugin
                or not issubclass(plugin_type, BasePlugin)
                or inspect.isabstract(plugin_type)
            ):
                continue

            plugin = plugin_type()
            loaded.append(
                self.load(plugin)
            )

        return loaded
