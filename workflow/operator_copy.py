"""Resolve the dashboard operator copy shared by its two language guards."""

from __future__ import annotations

import ast

_STREAMLIT = frozenset({"caption", "error", "info", "warning"})
_SCOPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


class _AmbiguousBinding:
    pass


class _RuntimeBinding:
    pass


class _UnreadableExpression(Exception):
    def __init__(self, node: ast.AST) -> None:
        self.node = node


_AMBIGUOUS = _AmbiguousBinding()
_RUNTIME = _RuntimeBinding()


def _scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    current: ast.AST | None = node
    while current is not None and not isinstance(current, _SCOPES):
        current = parents.get(current)
    assert current is not None
    return current


def _binding(
    name: str, scope: ast.AST, parents: dict[ast.AST, ast.AST]
) -> tuple[ast.AST, ast.AST] | _AmbiguousBinding | _RuntimeBinding | None:
    current: ast.AST | None = scope
    while current is not None:
        if isinstance(current, _SCOPES):
            stores = 0
            parameters = 0
            values: list[ast.AST] = []
            for node in ast.walk(current):
                if _scope(node, parents) is not current:
                    continue
                stores += int(
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Store)
                    and node.id == name
                )
                parameters += int(isinstance(node, ast.arg) and node.arg == name)
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    target, assigned_value = node.targets[0], node.value
                elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
                    target, assigned_value = node.target, node.value
                else:
                    continue
                if isinstance(target, ast.Name) and target.id == name:
                    values.append(assigned_value)
            if parameters:
                return _RUNTIME if stores == 0 else _AMBIGUOUS
            if stores:
                return (current, values[0]) if stores == len(values) == 1 else _AMBIGUOUS
        current = parents.get(current)
    return None


def _resolve(
    node: ast.AST,
    scope: ast.AST,
    parents: dict[ast.AST, ast.AST],
    seen: frozenset[tuple[int, str]] = frozenset(),
) -> tuple[ast.Constant, ...] | None:
    if isinstance(node, ast.Constant):
        return (node,) if isinstance(node.value, str) else ()
    if isinstance(node, ast.JoinedStr):
        parts: list[ast.Constant] = []
        for value in node.values:
            resolved = (
                _resolve(value.value, scope, parents, seen)
                if isinstance(value, ast.FormattedValue)
                else _resolve(value, scope, parents, seen)
            )
            if resolved is not None:
                parts.extend(resolved)
        return tuple(parts)
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ast.Add):
            return None
        left = _resolve(node.left, scope, parents, seen)
        right = _resolve(node.right, scope, parents, seen)
        return None if left is None or right is None else (*left, *right)
    if isinstance(node, ast.IfExp):
        body = _resolve(node.body, scope, parents, seen)
        other = _resolve(node.orelse, scope, parents, seen)
        return None if body is None or other is None else (*body, *other)
    if isinstance(node, ast.Name):
        key = (id(scope), node.id)
        if key in seen:
            raise _UnreadableExpression(node)
        binding = _binding(node.id, scope, parents)
        if isinstance(binding, _AmbiguousBinding):
            raise _UnreadableExpression(node)
        if isinstance(binding, _RuntimeBinding) or binding is None:
            return None
        binding_scope, bound_value = binding
        return _resolve(bound_value, binding_scope, parents, seen | {key})
    return None


def _arguments(call: ast.Call, scope: ast.AST) -> tuple[tuple[ast.AST, bool], ...]:
    if isinstance(call.func, ast.Name) and call.func.id == "_stat_row":
        labels = [*call.args[:1], *(kw.value for kw in call.keywords if kw.arg == "label")]
        return tuple((label, True) for label in labels)
    if not isinstance(call.func, ast.Attribute):
        return ()
    direct = (
        isinstance(call.func.value, ast.Name)
        and call.func.value.id == "st"
        and call.func.attr in _STREAMLIT
    )
    if not direct and call.func.attr != "metric":
        return ()
    keywords = tuple((kw.value, True) for kw in call.keywords if kw.arg in {"delta", "help"})
    if direct:
        return (*((argument, True) for argument in call.args), *keywords)
    positional = tuple((argument, index == 0) for index, argument in enumerate(call.args))
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) and scope.name == "_stat_row":
        positional = tuple(
            (argument, False if isinstance(argument, ast.Name) else strict)
            for argument, strict in positional
        )
    return (*positional, *keywords)


def operator_literal_parts(source: str, *, filename: str) -> tuple[ast.Constant, ...]:
    """Return every static literal fragment reaching a governed dashboard call."""
    tree = ast.parse(source, filename=filename)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    found: dict[tuple[int, int, int, int], ast.Constant] = {}
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        call_scope = _scope(call, parents)
        for argument, strict in _arguments(call, call_scope):
            unreadable = argument
            try:
                resolved = _resolve(argument, call_scope, parents)
            except _UnreadableExpression as error:
                resolved = None
                unreadable = error.node
                strict = True
            if resolved is None and strict:
                expression = ast.get_source_segment(source, unreadable) or ast.dump(unreadable)
                raise ValueError(
                    f"{filename}:{getattr(unreadable, 'lineno', '?')}: operator copy expression "
                    f"is not statically resolvable: {expression}"
                )
            if resolved is None:
                continue
            for literal in resolved:
                if literal.end_lineno is not None and literal.end_col_offset is not None:
                    found[
                        literal.lineno,
                        literal.col_offset,
                        literal.end_lineno,
                        literal.end_col_offset,
                    ] = literal
    return tuple(found.values())


def without_operator_literals(source: str, *, filename: str) -> str:
    """Blank exactly the literal fragments returned by :func:`operator_literal_parts`."""
    lines, starts, position = source.splitlines(keepends=True), [], 0
    for line in lines:
        starts.append(position)
        position += len(line)
    mask = [False] * len(source)
    for node in operator_literal_parts(source, filename=filename):
        assert node.end_lineno is not None and node.end_col_offset is not None
        start_line, end_line = node.lineno - 1, node.end_lineno - 1
        start = starts[start_line] + len(lines[start_line].encode()[: node.col_offset].decode())
        end = starts[end_line] + len(lines[end_line].encode()[: node.end_col_offset].decode())
        mask[start:end] = [True] * (end - start)
    return "".join(
        " " if hidden and char not in "\r\n" else char
        for char, hidden in zip(source, mask, strict=True)
    )
