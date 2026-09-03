"""P1 DoD #3 — the ADR-0005 wall as a running test (AST, no LLM, no DB).

The load-bearing invariant (ADR-0005): ``core/`` is deterministic and
LLM-free, so it must never reach into ``agents/`` (which is where the LLM is).
The sanctioned edge is ``agents/ -> core/`` (the tools call the gates). This
test walks every ``.py`` under ``app/core`` and fails if any of them imports
`app.agents` / ``agents`` — making the wall a machine check, not a comment.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_CORE = _BACKEND / "app" / "core"

_AGENT_TOPLEVELS = {"agent", "agents"}


def _imported_modules(tree: ast.AST) -> set[str]:
    """Full dotted names every import references (``app.core`` → ``app.core``)."""
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def _reaches(mods: set[str], dotted: str) -> bool:
    """True if any imported name *is* or *is under* ``dotted`` (e.g. reaches ``app.core``)."""
    return any(m == dotted or m.startswith(dotted + ".") or m == dotted.split(".", 1)[0] for m in mods)


class WallTest(unittest.TestCase):
    """The three-layer wall: core does not depend on agents."""

    def setUp(self) -> None:
        if not _CORE.is_dir():
            self.skipTest("app/core not found")

    def test_core_imports_no_agents(self) -> None:
        """No module under ``app/core`` may import the `agents` package."""
        offenders: list[str] = []
        for path in sorted(_CORE.rglob("*.py")):
            mods = _imported_modules(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
            # core must never reach the agents package (top-level `agents` or `app.agents`).
            if _reaches(mods, "app.agents") or {"agent", "agents"} & {m.split(".", 1)[0] for m in mods}:
                offenders.append(f"{path.relative_to(_BACKEND)} reaches {sorted(m for m in mods if 'agent' in m)}")
        self.assertEqual(offenders, [], "ADR-0005 wall broken:\n  " + "\n  ".join(offenders))

    def test_core_module_exists(self) -> None:
        """core/ has the four P1 gate files (sql_validator, flags, db)."""
        for name in ("sql_validator.py", "flags.py", "db.py"):
            self.assertTrue((_CORE / name).is_file(), f"missing core gate: {name}")

    def test_agents_may_import_core(self) -> None:
        """The sanctioned edge: agents/tools may call core (sanity that the split is real)."""
        agents_dir = _BACKEND / "app" / "agents"
        self.assertTrue(agents_dir.is_dir())
        # At least one agent module references core (the gates live in core by design).
        hit = False
        for path in agents_dir.rglob("*.py"):
            if _reaches(_imported_modules(ast.parse(path.read_text("utf-8"))), "app.core"):
                hit = True
                break
        self.assertTrue(hit, "expected at least one app/agents module to import app.core (the gates)")


if __name__ == "__main__":
    unittest.main()
