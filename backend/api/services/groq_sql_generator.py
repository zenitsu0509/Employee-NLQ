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
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert SQL generator. Given a database schema and a natural language question, generate a single, valid PostgreSQL query. Do not provide any explanation, only the SQL query itself. If you cannot generate a query, respond with 'INVALID'.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                model=self._settings.groq.model,
                temperature=0.1,
                max_tokens=1024,
                stop=["```"],
            )
            response_content = chat_completion.choices[0].message.content
            if not response_content or "INVALID" in response_content:
                return None

            sql = self._extract_sql(response_content)
            if not sql:
                return None

            return SQLQuery(sql=sql, params={}, description="LLM Generated Query")

        except Exception as e:
            print(f"Error calling Groq API: {e}")
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

Generate the PostgreSQL query for the user's question based on the provided schema.
Respond with only the SQL query.
"""

    def _extract_sql(self, text: str) -> str:
        # Remove markdown code blocks
        match = re.search(r"```(?:sql)?\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

