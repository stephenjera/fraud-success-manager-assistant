from pathlib import Path


def load_schema() -> str:
    """Load the SQL schema text from the repo data folder.

    This mirrors the previous `load_schema` behavior in `main.py`.
    """
    path = Path(__file__).parent.parent / "data" / "schema.sql"
    return path.read_text()
