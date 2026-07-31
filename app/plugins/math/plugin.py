from app.plugins.base_plugin import BasePlugin
from app.planner.intents.math_intent import MathIntent
from app.tools.calculator_tool import CalculatorTool


class MathPlugin(BasePlugin):
    """
    Registers all math-related components.
    """

    def get_intents(self):
        return [
            MathIntent(),
        ]

    def get_tools(self):
        return [
            CalculatorTool(),
        ]