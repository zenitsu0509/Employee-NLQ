from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from groq import Groq

from backend.api.config import get_settings


# ---------------------------------------------------------------------------
# GUARDRAILS — only block DESTRUCTIVE operations (DELETE / DROP / TRUNCATE etc.)
# SELECT, UPDATE, INSERT are all permitted.
# ---------------------------------------------------------------------------

# Patterns that indicate a DESTRUCTIVE statement — these are always blocked.
_DESTRUCTIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*DELETE\b",    re.IGNORECASE),   # DELETE FROM …
    re.compile(r"\bDROP\b",        re.IGNORECASE),   # DROP TABLE / DROP DATABASE
    re.compile(r"^\s*TRUNCATE\b",  re.IGNORECASE),   # TRUNCATE TABLE …
    re.compile(r"\bALTER\b",       re.IGNORECASE),   # ALTER TABLE …
    re.compile(r"^\s*CREATE\b",    re.IGNORECASE),   # CREATE TABLE …
    re.compile(r"\bGRANT\b",       re.IGNORECASE),   # GRANT …
    re.compile(r"\bREVOKE\b",      re.IGNORECASE),   # REVOKE …
    re.compile(r"--",              re.IGNORECASE),   # SQL comment injection
    re.compile(r"/\*.*?\*/",       re.DOTALL),       # Block comment injection
]

# UPDATE without a WHERE clause is also blocked (mass update protection)
_UPDATE_WITHOUT_WHERE = re.compile(
    r"^\s*UPDATE\s+\S+\s+SET\b(?!.*\bWHERE\b)", re.IGNORECASE | re.DOTALL
)

# Allowed statement prefixes
_ALLOWED_PREFIXES = re.compile(r"^\s*(SELECT|UPDATE|INSERT)\b", re.IGNORECASE)


def _is_safe_sql(sql: str) -> bool:
    """
    Returns True only if the SQL is a safe, non-destructive statement:
      ✅ SELECT — always allowed
      ✅ UPDATE — allowed IF it has a WHERE clause (prevents mass updates)
      ✅ INSERT — allowed
      ❌ DELETE, DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE — always blocked
      ❌ UPDATE without WHERE — blocked (mass update protection)
      ❌ SQL comment injections — blocked
    """
    stripped = sql.strip()

    # Must start with an allowed keyword
    if not _ALLOWED_PREFIXES.match(stripped):
        return False

    # Reject any destructive pattern
    for pattern in _DESTRUCTIVE_PATTERNS:
        if pattern.search(stripped):
            return False

    # Reject UPDATE without WHERE
    if _UPDATE_WITHOUT_WHERE.match(stripped):
        return False

    return True


@dataclass
class SQLQuery:
    sql: str
    params: Dict[str, object]
    description: str


class GroqSQLGenerator:
    """LLM-powered SQL generator using Groq — guardrails enforce no destructive operations."""

    _SYSTEM_PROMPT = (
        "You are a PostgreSQL query assistant for an HR analytics system.\n\n"
        "STRICT RULES — follow without exception:\n"
        "1. You may generate SELECT, UPDATE, or INSERT statements ONLY.\n"
        "2. You may NEVER generate DELETE, DROP, TRUNCATE, ALTER, CREATE, GRANT, or REVOKE.\n"
        "3. Every UPDATE statement MUST include a WHERE clause targeting specific rows.\n"
        "   Never write UPDATE without WHERE (that would affect all rows).\n"
        "4. Never include SQL comments (-- or /* */) in your output.\n"
        "5. If the user asks to delete rows, remove records, wipe data, or drop a table,\n"
        "   respond with exactly: BLOCKED_DESTRUCTIVE_OPERATION\n"
        "6. Respond with ONLY the raw SQL — no markdown, no explanations.\n"
        "7. If you cannot produce a valid safe query, respond with exactly: INVALID\n\n"
        "PostgreSQL notes:\n"
        "- Use LOWER() for case-insensitive string comparisons.\n"
        "- Use NOW(), CURRENT_DATE for date operations.\n"
        "- Use proper JOINs when referencing related tables.\n"
        "- UPDATE example: UPDATE employees SET department = 'Engineering' WHERE first_name = 'Victor' AND last_name = 'White';\n"
    )

    def __init__(self, schema: Dict[str, Any]) -> None:
        self._schema = schema
        self._settings = get_settings()
        if not self._settings.groq or not self._settings.groq.api_key:
            raise ValueError("Groq API key is not configured in config.yml")
        self._client = Groq(api_key=self._settings.groq.api_key)

    def generate(self, query: str, table: str | None = None) -> Optional[SQLQuery]:
        # ── Pre-flight: block clearly destructive user intent ────────────
        lower_query = query.lower()
        destructive_intents = [
            "delete", "remove all", "drop table", "drop database",
            "truncate", "erase all", "wipe", "clear table", "clear all",
            "remove record", "purge",
        ]
        for intent in destructive_intents:
            if intent in lower_query:
                print(f"[GroqSQLGenerator] Blocked destructive intent: '{intent}' in query")
                return None

        prompt = self._build_prompt(query)
        try:
            print(f"[GroqSQLGenerator] Calling Groq (model={self._settings.groq.model}) for: '{query}'")
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                model=self._settings.groq.model,
                temperature=0.1,
                max_tokens=1024,
            )
            response_content = chat_completion.choices[0].message.content or ""
            print(f"[GroqSQLGenerator] LLM Response: {response_content!r}")

            # ── Check for explicit refusal signals ──────────────────────
            upper = response_content.upper().strip()
            if "INVALID" in upper or "BLOCKED_DESTRUCTIVE_OPERATION" in upper:
                print("[GroqSQLGenerator] LLM refused the request")
                return None

            sql = self._extract_sql(response_content)
            if not sql or len(sql) < 10:
                print("[GroqSQLGenerator] Failed to extract SQL from response")
                return None

            # ── Post-generation hard safety check ──────────────────────
            if not _is_safe_sql(sql):
                print(f"[GroqSQLGenerator] BLOCKED unsafe SQL: {sql[:200]}")
                return None

            print(f"[GroqSQLGenerator] Safe SQL generated: {sql}")
            return SQLQuery(sql=sql, params={}, description=f"LLM Generated: {sql[:80]}")

        except Exception as e:
            print(f"[GroqSQLGenerator] Error calling Groq API: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _build_prompt(self, user_query: str) -> str:
        schema_json = json.dumps(self._schema, indent=2)
        return f"""Database Schema:
```json
{schema_json}
```

User Request:
"{user_query}"

Rules:
- Today's date: {__import__('datetime').date.today().isoformat()}
- Generate a valid PostgreSQL SELECT, UPDATE, or INSERT statement
- Every UPDATE MUST have a WHERE clause with specific conditions
- NEVER generate DELETE, DROP, TRUNCATE, ALTER, or CREATE
- Use LOWER() for string comparisons (e.g. LOWER(first_name) = 'victor')
- Return ONLY the SQL, no explanations

SQL:
"""

    def _extract_sql(self, text: str) -> str:
        """Extract SQL from LLM response."""
        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        cleaned = text.strip()
        for prefix in ["sql:", "query:", "answer:"]:
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        return cleaned
