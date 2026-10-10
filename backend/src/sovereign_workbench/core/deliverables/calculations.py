"""Small arithmetic evaluator; no eval, imports, attributes or executable code."""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def calculate(
    expression: str, resolve: Callable[[str], float] | None = None
) -> tuple[float, list[str]]:
    if len(expression) > 2000:
        raise ValueError("expression exceeds 2000 characters")
    tree = ast.parse(expression.lstrip("="), mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 200:
        raise ValueError("expression is too complex")
    steps: list[str] = []

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            result = float(node.value)
        elif isinstance(node, ast.Name) and resolve:
            result = resolve(node.id)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            result = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent exceeds supported range")
            result = float(_OPERATORS[type(node.op)](left, right))
            steps.append(f"{ast.unparse(node)} = {result:g}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            values = [visit(arg) for arg in node.args]
            name = node.func.id.upper()
            if name == "SUM":
                result = sum(values)
            elif name == "AVERAGE" and values:
                result = sum(values) / len(values)
            elif name == "MIN" and values:
                result = min(values)
            elif name == "MAX" and values:
                result = max(values)
            elif name == "ABS" and len(values) == 1:
                result = abs(values[0])
            else:
                raise ValueError(f"unsupported function: {name}")
            steps.append(f"{ast.unparse(node)} = {result:g}")
        else:
            raise ValueError(
                "only arithmetic, cell references and SUM/AVERAGE/MIN/MAX/ABS are supported"
            )
        if not math.isfinite(result):
            raise ValueError("result is not a finite number")
        return result

    result = visit(tree.body)
    return result, steps or [f"{expression} = {result:g}"]
