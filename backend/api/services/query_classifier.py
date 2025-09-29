from __future__ import annotations

import re
from enum import Enum


class QueryType(str, Enum):
    SQL = "sql"
    DOCUMENT = "document"
    HYBRID = "hybrid"


DOCUMENT_KEYWORDS = {"document", "resume", "review", "note", "certificate", "policy", "resumes"}
SQL_KEYWORDS = {
    "select",
    "from",
    "where",
    "group",
    "average",
    "count",
    "sum",
    "join",
    "order"
}

SQL_PATTERNS = [r"\bhow many\b", r"\baverage\b", r"\btop \d+\b", r"\breport(s)? to\b"]


class QueryClassifier:
    """Lightweight heuristic classifier for user queries."""

    def classify(self, query: str) -> QueryType:
        normalized = query.lower()
        contains_sql_keyword = any(
            re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in SQL_KEYWORDS
        ) or any(re.search(pattern, normalized) for pattern in SQL_PATTERNS)
        contains_document_keyword = any(
            re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in DOCUMENT_KEYWORDS
        )

        if contains_sql_keyword and contains_document_keyword:
            return QueryType.HYBRID
        if contains_sql_keyword:
            return QueryType.SQL
        if contains_document_keyword:
            return QueryType.DOCUMENT
        if re.search(r"\bpdf\b|\bdocx\b|\bfile\b", normalized):
            return QueryType.DOCUMENT
        return QueryType.HYBRID
