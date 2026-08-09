"""Shared helper for the static-analysis rule tests in test_rules.py.

Walks the AST of our own app/ package (never executes it) to answer: "is
module X reachable, by import, from module Y?" Used to prove things like
"no Anthropic client is reachable from the feed/article render path" without
needing to actually import anthropic (which the render path shouldn't do -
that's the whole point).

This file is small enough to unit-test its own correctness against synthetic
fixtures (see test_rules.py's test_static_analysis_helper_catches_a_real_case)
rather than trusting it blindly.
"""

from __future__ import annotations

import ast
from pathlib import Path


def module_file(root: Path, dotted: str) -> Path | None:
    """dotted like 'app.web.routes', root is the directory CONTAINING the
    top-level package (e.g. repo root, so root/app/web/routes.py)."""
    parts = dotted.split(".")
    candidate = root.joinpath(*parts)
    if candidate.with_suffix(".py").exists():
        return candidate.with_suffix(".py")
    if (candidate / "__init__.py").exists():
        return candidate / "__init__.py"
    return None


def direct_imports(py_file: Path, package_root: Path) -> set[str]:
    """All module names directly imported by py_file, as dotted names.
    Relative imports are resolved against py_file's own position under
    package_root (e.g. repo root).

    "containing_package" is py_file's own dotted path minus its last
    component - this works uniformly whether py_file is a regular module
    (pkg/sub/mod.py -> containing package is pkg.sub) or an __init__.py
    (pkg/sub/__init__.py -> containing package is pkg.sub, since __init__'s
    own dotted identity IS the package, and level=1 there also means
    "this same package").
    """
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    names: set[str] = set()

    own_parts = py_file.relative_to(package_root).with_suffix("").parts
    containing_package = own_parts[:-1]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    names.add(node.module)
                continue

            # level >= 1: base is containing_package, walked up (level-1) more times
            up = len(containing_package) - (node.level - 1)
            base = list(containing_package[: max(up, 0)])

            if node.module:
                # from .sub import X  -> the module being imported FROM is base.sub;
                # X may be a symbol inside it, not itself a followable module.
                names.add(".".join(base + [node.module]))
            else:
                # from . import X, Y  -> each of X, Y may be a submodule of `base`.
                for alias in node.names:
                    names.add(".".join(base + [alias.name]))
    return names


def imports_reachable_from(
    dotted_module: str, package_root: Path, top_level_package: str = "app"
) -> set[str]:
    """Recursively follow imports starting at dotted_module, staying inside
    top_level_package for recursion, but collecting EVERY name encountered
    along the way (including third-party names like 'anthropic') into the
    result set. Returns empty set if dotted_module doesn't exist (a module
    that isn't built yet cannot reach anything)."""
    seen: set[str] = set()
    collected: set[str] = set()
    stack = [dotted_module]

    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)

        path = module_file(package_root, current)
        if path is None:
            continue

        direct = direct_imports(path, package_root)
        collected |= direct
        for name in direct:
            if name == top_level_package or name.startswith(top_level_package + "."):
                stack.append(name)

    return collected
