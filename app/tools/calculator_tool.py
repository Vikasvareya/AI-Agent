from app.tools.base_tool import BaseTool


class CalculatorTool(BaseTool):
    """
    Tool for evaluating simple mathematical expressions.
    """

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Evaluate mathematical expressions like "
            "'2 + 2' or '10 * 5'."
        )

    def execute(
        self,
        **kwargs,
    ) -> str:
        """
        Execute the calculator tool.
        """

        expression = kwargs.get("expression")

        if not expression:
            return "No expression provided."

        try:
            result = eval(expression)
            return str(result)

        except Exception as e:
            return f"Calculation failed: {e}"