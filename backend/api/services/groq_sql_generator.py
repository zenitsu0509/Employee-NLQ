from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    from groq import Groq  # Groq client
except ImportError:  # pragma: no cover - optional dependency
    Groq = None  # type: ignore

try:
    from openai import OpenAI  # OpenAI unified client (>=1.x)
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from backend.api.config import get_settings


@dataclass
class SQLQuery:
    sql: str
    params: Dict[str, object]
    description: str


class GroqSQLGenerator:
    """LLM-powered SQL generator using Groq or OpenAI backends.

    Falls back to a smaller Groq model if the requested Groq-hosted model fails.
    """

    def __init__(self, schema: Dict[str, Any]) -> None:
        self._schema = schema
        self._settings = get_settings()
        if not self._settings.groq or not self._settings.groq.api_key:
            raise ValueError("LLM API key is not configured in config.yml (groq.api_key)")

        provider = getattr(self._settings.groq, "provider", "groq")
        model = self._settings.groq.model

        if provider == "groq":
            if Groq is None:
                raise RuntimeError("groq package not installed; add 'groq' to requirements.txt")
            self._client = Groq(api_key=self._settings.groq.api_key)
            self._invoke_fn = self._invoke_groq
        elif provider == "openai":
            if OpenAI is None:
                raise RuntimeError("openai package not installed; add 'openai' to requirements.txt")
            # OpenAI client will use passed api_key; model string must exist (e.g. gpt-4.1, gpt-oss-120b)
            self._client = OpenAI(api_key=self._settings.groq.api_key)
            self._invoke_fn = self._invoke_openai
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        # Log chosen provider/model after client has been initialized
        print(f"[GroqSQLGenerator] Using provider='{provider}' model='{model}'")

    def generate(self, query: str, table: str | None = None) -> Optional[SQLQuery]:
        prompt = self._build_prompt(query)
        try:
            print(f"[GroqSQLGenerator] Calling Groq API for query: '{query}'")
            response_content = self._invoke_fn(prompt)
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
            print(f"[GroqSQLGenerator] Error calling LLM provider: {e}")
            # Attempt Groq fallback when using Groq provider and primary model is gpt-oss-120b
            provider = getattr(self._settings.groq, "provider", "groq") if self._settings.groq else "groq"
            primary_model = self._settings.groq.model if self._settings.groq else ""
            if provider == "groq" and primary_model == "gpt-oss-120b":
                try:
                    fallback = "llama-3.1-8b-instant"
                    print(f"[GroqSQLGenerator] Fallback to '{fallback}' after failure with '{primary_model}'.")
                    self._settings.groq.model = fallback  # mutate settings instance for this process
                    response_content = self._invoke_fn(prompt)
                    if response_content and "INVALID" not in response_content.upper():
                        sql = self._extract_sql(response_content)
                        if sql and len(sql) >= 10:
                            print(f"[GroqSQLGenerator] Fallback generated SQL: {sql}")
                            return SQLQuery(sql=sql, params={}, description="LLM Generated Query (fallback)")
                except Exception as inner:
                    print(f"[GroqSQLGenerator] Fallback model also failed: {inner}")
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

    # --- Provider-specific invocation helpers ---
    def _invoke_groq(self, prompt: str) -> str:
        completion = self._client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert PostgreSQL query generator. You MUST respond with ONLY valid SQL. You can generate SELECT, INSERT, UPDATE, DELETE. No explanations. For UPDATE/DELETE never use LIMIT (use WHERE). If unsure respond EXACTLY 'INVALID'.",
                },
                {"role": "user", "content": prompt},
            ],
            model=self._settings.groq.model,
            temperature=0.1,
            max_tokens=1024,
        )
        return completion.choices[0].message.content

    def _invoke_openai(self, prompt: str) -> str:
        # OpenAI Chat API mirrors interface; adapt differences if they arise.
        completion = self._client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert PostgreSQL query generator. Return ONLY raw SQL (SELECT/INSERT/UPDATE/DELETE). No commentary. Never use LIMIT in UPDATE/DELETE. If unsure reply 'INVALID'.",
                },
                {"role": "user", "content": prompt},
            ],
            model=self._settings.groq.model,  # Reusing same config slot for model
            temperature=0.1,
            max_tokens=800,
        )
        return completion.choices[0].message.content or ""

