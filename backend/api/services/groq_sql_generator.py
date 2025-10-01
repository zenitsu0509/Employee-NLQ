from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from groq import Groq

from backend.api.config import get_settings


@dataclass
class SQLQuery:
    sql: str
    params: Dict[str, object]
    description: str


class GroqSQLGenerator:
    """LLM-powered SQL generator using Groq."""

    def __init__(self, schema: Dict[str, Any]) -> None:
        self._schema = schema
        self._settings = get_settings()
        if not self._settings.groq or not self._settings.groq.api_key:
            raise ValueError("Groq API key is not configured in config.yml")
        self._client = Groq(api_key=self._settings.groq.api_key)

    def generate(self, query: str, table: str | None = None) -> Optional[SQLQuery]:
        prompt = self._build_prompt(query)
        try:
            print(f"[GroqSQLGenerator] Calling Groq API for query: '{query}'")
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert PostgreSQL query generator. You MUST respond with ONLY valid SQL, nothing else. You can generate SELECT, INSERT, UPDATE, or DELETE queries. No explanations, no markdown formatting unless it contains SQL code. Important: PostgreSQL does not support LIMIT in UPDATE/DELETE statements - use WHERE conditions instead. If you cannot generate a query, respond with exactly 'INVALID'.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                model=self._settings.groq.model,
                temperature=0.1,
                max_tokens=1024,
            )
            response_content = chat_completion.choices[0].message.content
            print(f"[GroqSQLGenerator] LLM Response: {response_content}")
            
            if not response_content or "INVALID" in response_content.upper():
                print("[GroqSQLGenerator] Invalid or empty response from LLM")
                return None

            sql = self._extract_sql(response_content)
            if not sql or len(sql) < 10:  # Basic sanity check
                print("[GroqSQLGenerator] Failed to extract valid SQL from response")
                return None

            print(f"[GroqSQLGenerator] Generated SQL: {sql}")
            return SQLQuery(sql=sql, params={}, description="LLM Generated Query")

        except Exception as e:
            print(f"[GroqSQLGenerator] Error calling Groq API: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _build_prompt(self, user_query: str) -> str:
        schema_json = json.dumps(self._schema, indent=2)
        return f"""
Database Schema:
```json
{schema_json}
```

User Question:
"{user_query}"

Important Notes:
- Today's date is 2025-10-01
- Generate a valid PostgreSQL query that answers the user's question
- Use proper SQL syntax with JOINs when needed
- For date comparisons, use PostgreSQL date functions
- You can generate SELECT, INSERT, UPDATE, or DELETE queries
- IMPORTANT: PostgreSQL does NOT support LIMIT in UPDATE/DELETE statements
- For UPDATE/DELETE, use WHERE clauses to limit affected rows
- Return ONLY the SQL query, no explanations

Generate the PostgreSQL query:
"""

    def _extract_sql(self, text: str) -> str:
        """Extract SQL from LLM response, handling various formats."""
        # Remove markdown code blocks
        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Try without backticks - just clean the response
        cleaned = text.strip()
        # Remove common prefixes
        for prefix in ["sql:", "query:", "answer:"]:
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        return cleaned

