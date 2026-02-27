from __future__ import annotations

import re
from pathlib import Path

import duckdb


class DuckDBEngine:
    """DuckDB connection manager and query executor."""

    def __init__(self, connection_string: str, base_path: Path | None = None):
        db_path = self._resolve_path(connection_string, base_path)
        self.conn = duckdb.connect(str(db_path))

    @staticmethod
    def _resolve_path(connection_string: str, base_path: Path | None) -> Path:
        # Parse "duckdb:///path/to/db" or "duckdb://path/to/db"
        match = re.match(r"duckdb:///?(.*)", connection_string)
        if not match:
            raise ValueError(f"Invalid DuckDB connection string: {connection_string}")
        db_path = Path(match.group(1))
        if base_path and not db_path.is_absolute():
            db_path = base_path / db_path
        return db_path

    def execute(self, sql: str) -> dict:
        """Execute SQL and return results as {columns, rows}."""
        result = self.conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return {"columns": columns, "rows": [list(row) for row in rows]}

    def get_tables(self) -> list[str]:
        """Return list of table names in the database."""
        result = self.conn.execute("SHOW TABLES")
        return [row[0] for row in result.fetchall()]

    def validate_tables(self, expected: list[str]) -> list[str]:
        """Return list of expected tables that are missing."""
        existing = set(self.get_tables())
        return [t for t in expected if t not in existing]

    def close(self):
        self.conn.close()
