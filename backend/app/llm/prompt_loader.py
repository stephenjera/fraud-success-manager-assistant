from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).parent / "prompts"

env = Environment(
    loader=FileSystemLoader(BASE_DIR),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def parse_prompt(text: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    current_role: str | None = None
    buffer: list[str] = []

    def flush():
        nonlocal buffer, current_role
        if current_role and buffer:
            messages.append(
                {
                    "role": current_role,
                    "content": "\n".join(buffer).strip(),
                }
            )
            buffer = []

    for line in text.splitlines():
        line = line.strip()

        if line.startswith("---system"):
            flush()
            current_role = "system"
        elif line.startswith("---user"):
            flush()
            current_role = "user"
        elif line.startswith("---assistant"):
            flush()
            current_role = "assistant"
        else:
            buffer.append(line)

    flush()

    return messages


def render_prompt(
    name: str,
    version: str,
    context: dict[str, object],
) -> list[dict[str, str]]:
    template_path = f"{name}/{version}.jinja"
    template = env.get_template(template_path)

    rendered = template.render(**context)

    return parse_prompt(rendered)
