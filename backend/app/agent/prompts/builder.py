from pathlib import Path

PROMPT_VERSION = "v2.0"


def _load(name: str) -> str:
    return (Path(__file__).parent / f"{name}.txt").read_text().strip()


def build_generator_prompt(schema: str) -> str:
    return "\n\n".join(
        [
            _load("generator"),
            f"SCHEMA:\n```sql\n{schema}\n```",
            f"PROMPT_VERSION: {PROMPT_VERSION}",
        ]
    )


def build_planner_prompt(schema: str) -> str:
    return "\n\n".join(
        [_load("planner"), f"```sql\n{schema}\n```"],
    )
