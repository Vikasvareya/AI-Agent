import re
import ast
import operator

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
        if len(expression) > 500:
            return "Calculation failed: expression exceeds 500 characters."
        expression = expression.strip()
        expression_for_parser = re.sub(r"(?<![=<>])=(?![=])", "==", expression)

        try:
            tree = ast.parse(expression_for_parser, mode="eval")
        except SyntaxError as exc:
            return f"Calculation failed: {exc}"

        binary_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }
        comparison_ops = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
        }

        def evaluate(node):
            if isinstance(node, ast.Expression):
                return evaluate(node.body)
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)) and not isinstance(
                    node.value,
                    bool,
                ):
                    return node.value
                raise ValueError("Only numeric constants are allowed.")
            if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
                left = evaluate(node.left)
                right = evaluate(node.right)
                try:
                    return binary_ops[type(node.op)](left, right)
                except ZeroDivisionError as exc:
                    raise ValueError("Division by zero.") from exc
            if isinstance(node, ast.Compare) and len(node.ops) == 1:
                left = evaluate(node.left)
                right = evaluate(node.comparators[0])
                if type(node.ops[0]) not in comparison_ops:
                    raise ValueError("Unsupported comparison operator.")
                return comparison_ops[type(node.ops[0])](left, right)
            if isinstance(node, ast.UnaryOp) and isinstance(
                node.op,
                (ast.UAdd, ast.USub),
            ):
                operand = evaluate(node.operand)
                return operand if isinstance(node.op, ast.UAdd) else -operand
            raise ValueError("Unsupported or unsafe expression.")

        try:
            result = evaluate(tree)
            return str(result)
        except (ValueError, ArithmeticError) as exc:
            return f"Calculation failed: {exc}"