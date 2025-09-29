from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Set

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend.api.database import get_connection


EMPLOYEE_SYNONYMS = {
    "employee": {"employee", "employees", "emp", "staff", "person", "personnel"},
    "department": {"department", "dept", "division", "team"},
    "salary": {"salary", "compensation", "pay", "pay_rate", "annual_salary"},
    "manager": {"manager", "lead", "supervisor", "head"},
    "hire_date": {"hire_date", "hired_on", "start_date", "join_date"},
    "location": {"location", "office", "city"},
    "skills": {"skill", "skills", "competency"},
    "title": {"title", "role", "position"}
}


class SchemaDiscovery:
    """Service responsible for analyzing databases and mapping queries to schema."""

    def __init__(self) -> None:
        self._synonym_index: Dict[str, Set[str]] = {
            canonical: synonyms for canonical, synonyms in EMPLOYEE_SYNONYMS.items()
        }

    def analyze_database(self, connection_string: str) -> Dict[str, Any]:
        """Connect to database and discover schema information."""
        with get_connection(connection_string) as conn:
            inspector = inspect(conn)
            tables = inspector.get_table_names()
            schema_tables = []
            schema_relationships = []

            for table in tables:
                columns = inspector.get_columns(table)
                sample_rows = self._fetch_sample_rows(conn, table)
                schema_tables.append(
                    {
                        "name": table,
                        "columns": [column["name"] for column in columns],
                        "types": {column["name"]: str(column["type"]) for column in columns},
                        "sample_rows": sample_rows,
                    }
                )

                foreign_keys = inspector.get_foreign_keys(table)
                for fk in foreign_keys:
                    schema_relationships.append(
                        {
                            "from_table": table,
                            "to_table": fk.get("referred_table"),
                            "via_columns": dict(zip(fk.get("constrained_columns", []), fk.get("referred_columns", [])))
                        }
                    )

            synonym_map_raw = self._build_synonym_map(schema_tables)
            synonym_map = {table: sorted(list(synonyms)) for table, synonyms in synonym_map_raw.items()}
            return {
                "tables": schema_tables,
                "relationships": schema_relationships,
                "synonyms": synonym_map,
            }

    def map_natural_language_to_schema(self, query: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Map user's natural language to actual database structure."""
        tokens = self._tokenize(query)
        synonym_map = schema.get("synonyms", {})
        matched_columns: Dict[str, List[str]] = defaultdict(list)

        for token in tokens:
            canonical = self._find_canonical(token, synonym_map)
            if not canonical:
                continue
            for table, table_synonyms in synonym_map.items():
                if canonical in table_synonyms:
                    matched_columns[table].append(canonical)

        likely_tables = sorted(matched_columns, key=lambda key: len(matched_columns[key]), reverse=True)
        return {
            "tokens": tokens,
            "matches": matched_columns,
            "likely_tables": likely_tables,
        }

    def _fetch_sample_rows(self, conn: Connection, table: str, limit: int = 5) -> List[Dict[str, Any]]:
        preparer = conn.dialect.identifier_preparer
        query = text(f"SELECT * FROM {preparer.quote_identifier(table)} LIMIT :limit")
        result = conn.execute(query, {"limit": limit})
        return [dict(row._mapping) for row in result]

    def _build_synonym_map(self, tables: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        table_map: Dict[str, Set[str]] = {}
        for table in tables:
            table_synonyms = set()
            normalized_name = table["name"].lower()
            table_synonyms.add(normalized_name)
            for canonical, synonyms in self._synonym_index.items():
                if canonical in normalized_name or any(synonym in normalized_name for synonym in synonyms):
                    table_synonyms.update(synonyms)
            for column in table["columns"]:
                normalized_column = column.lower()
                table_synonyms.add(normalized_column)
                for canonical, synonyms in self._synonym_index.items():
                    if canonical in normalized_column or any(synonym in normalized_column for synonym in synonyms):
                        table_synonyms.update(synonyms)
            table_map[table["name"]] = table_synonyms
        return table_map

    def _tokenize(self, query: str) -> List[str]:
        return [token for token in re.split(r"\W+", query.lower()) if token]

    def _find_canonical(self, token: str, synonym_map: Dict[str, Set[str]]) -> str | None:
        for table_synonyms in synonym_map.values():
            if token in table_synonyms:
                return token
        for canonical, synonyms in self._synonym_index.items():
            if token == canonical or token in synonyms:
                return canonical
        return None
