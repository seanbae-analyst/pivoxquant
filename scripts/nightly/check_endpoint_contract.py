#!/usr/bin/env python
"""Frontend->backend endpoint contract check.

tsc and vitest cannot catch a deleted backend route: the frontend keeps its
paths as plain string constants, so removing a blueprint leaves a green
typecheck and a runtime 404. This reads every `/api/...` literal out of the
frontend endpoint table and asserts some blueprint in `routes/` still declares
a matching rule.

Parses the route files with `ast` rather than importing the app: booting Flask
starts the scheduler and fires live market calls, which an unattended nightly
run must not do. Read-only. Exits 1 if any frontend path is orphaned.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENDPOINTS_TS = REPO / "frontend/src/lib/endpoints.ts"
ROUTES_DIR = REPO / "routes"
DORMANT_LIST = Path(__file__).with_name("dormant_endpoints.txt")

_TS_PLACEHOLDER = re.compile(r"\$\{[^}]*\}")     # `${id}` in a template literal
_FLASK_PLACEHOLDER = re.compile(r"<[^>]+>")      # `<int:id>` in a Flask rule
_API_LITERAL = re.compile(r"""['"`](/api/[^'"`\s]*)['"`]""")


def frontend_paths() -> list[tuple[str, int]]:
    """Live `/api/...` literals, skipping the ones quoted inside comments.

    The table documents removed and renamed routes in prose; counting those
    would report orphans nobody can act on.
    """
    if not ENDPOINTS_TS.exists():
        print(f"MISSING {ENDPOINTS_TS.relative_to(REPO)}")
        return []
    out: list[tuple[str, int]] = []
    in_block = False
    for lineno, line in enumerate(ENDPOINTS_TS.read_text().splitlines(), 1):
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("/*"):
            in_block = "*/" not in stripped
            continue
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        for raw in _API_LITERAL.findall(line.split("//", 1)[0] if "://" not in line else line):
            out.append((raw, lineno))
    return out


def dormant_paths() -> set[str]:
    """Paths knowingly left without a backend, from dormant_endpoints.txt."""
    if not DORMANT_LIST.exists():
        return set()
    out = set()
    for line in DORMANT_LIST.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line)
    return out


def _literal(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def backend_rules() -> list[str]:
    """Every `url_prefix + route` declared by a blueprint under routes/."""
    rules: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            print(f"UNPARSEABLE {path.relative_to(REPO)}: {exc}")
            continue

        prefixes: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            if getattr(func, "id", None) != "Blueprint" and getattr(func, "attr", None) != "Blueprint":
                continue
            prefix = ""
            for kw in node.value.keywords:
                if kw.arg == "url_prefix":
                    prefix = _literal(kw.value) or ""
            for target in node.targets:
                if isinstance(target, ast.Name):
                    prefixes[target.id] = prefix

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                fn = dec.func
                if not isinstance(fn, ast.Attribute) or fn.attr not in ("route", "add_url_rule"):
                    continue
                owner = getattr(fn.value, "id", None)
                if owner not in prefixes or not dec.args:
                    continue
                rule = _literal(dec.args[0])
                if rule is not None:
                    rules.append(prefixes[owner].rstrip("/") + rule)
    return rules


def main() -> int:
    paths = frontend_paths()
    if not paths:
        print("FAIL no /api literals found — endpoint table missing or moved")
        return 1

    rules = backend_rules()
    if not rules:
        print("FAIL no blueprint routes parsed — routes/ missing or restructured")
        return 1

    matchers = [
        re.compile("^" + _FLASK_PLACEHOLDER.sub("[^/]+", re.escape(r).replace(r"\<", "<").replace(r"\>", ">")) + "/?$")
        for r in rules
    ]

    dormant_declared = dormant_paths()
    orphans, dormant_hit, seen = [], [], set()
    for raw, lineno in paths:
        if raw in seen:
            continue
        seen.add(raw)
        probe = _TS_PLACEHOLDER.sub("X", raw).split("?", 1)[0].rstrip("/")
        if any(m.match(probe) for m in matchers):
            continue
        (dormant_hit if raw in dormant_declared else orphans).append((raw, lineno))

    # A dormant entry whose route came back is stale bookkeeping, not an error,
    # but it must be said out loud or the list rots into a blanket suppression.
    stale = sorted(d for d in dormant_declared if d not in {r for r, _ in dormant_hit})

    if dormant_hit:
        print(f"DORMANT {len(dormant_hit)} declared in dormant_endpoints.txt (not counted)")
    if stale:
        print(f"STALE {len(stale)} dormant entries now served or renamed — prune the list:")
        for d in stale:
            print(f"  {d}")

    if not orphans:
        print(f"OK {len(seen) - len(dormant_hit)} live frontend endpoints all match "
              f"a backend route ({len(rules)} rules parsed)")
        return 0

    print(f"ORPHANED {len(orphans)} of {len(seen)} frontend endpoints have no backend route "
          f"({len(rules)} rules parsed):")
    for raw, lineno in sorted(orphans):
        print(f"  endpoints.ts:{lineno}  {raw}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
