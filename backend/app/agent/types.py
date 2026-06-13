from dataclasses import dataclass

import duckdb


@dataclass
class AgentDependencies:
    db: duckdb.DuckDBPyConnection
    current_rule_state: str | None = None
