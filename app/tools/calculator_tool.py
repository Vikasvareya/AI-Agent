from app.tools.base_tool import BaseTool


class CalculatorTool(BaseTool):
    """
    Tool for evaluating simple mathematical expressions.
    """

    name = "calculator"

    description = (
        "Evaluate mathematical expressions like "
        "'2 + 2' or '10 * 5'."
    )

    def run(
        self,
        args: dict,
    ) -> str:
        """
        Execute the calculator tool.
        """

        expression = args.get("expression")

        if not expression:
            return "No expression provided."

        try:
            result = eval(expression)
            return str(result)

        except Exception as e:
            return f"Calculation failed: {e}"