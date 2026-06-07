from dataclasses import dataclass

import duckdb


@dataclass
class AgentDependencies:
    """Type-safe dependency bucket containing thread-safe execution engines."""

    db: duckdb.DuckDBPyConnection
