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

# Patterns that strongly suggest SQL queries
SQL_PATTERNS = [r"\bhow many\b", r"\baverage\b", r"\btop \d+\b", r"\breport(s)? to\b"]

# Keywords that suggest data queries (could be either SQL or document-based)
DATA_QUERY_KEYWORDS = {"employee", "employees", "department", "salary", "bonus", "location", "skill"}


class QueryClassifier:
    """Lightweight heuristic classifier for user queries."""

    def classify(self, query: str) -> QueryType:
        normalized = query.lower()
        
        # Check for explicit keywords
        contains_sql_keyword = any(
            re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in SQL_KEYWORDS
        ) or any(re.search(pattern, normalized) for pattern in SQL_PATTERNS)
        
        contains_document_keyword = any(
            re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in DOCUMENT_KEYWORDS
        )
        
        contains_data_keyword = any(
            re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in DATA_QUERY_KEYWORDS
        )

        # Explicit document query
        if contains_document_keyword or re.search(r"\bpdf\b|\bdocx\b|\bfile\b", normalized):
            return QueryType.DOCUMENT if not contains_sql_keyword else QueryType.HYBRID
        
        # Strong SQL indicators with data keywords -> hybrid to cover both DB and docs
        if contains_sql_keyword and contains_data_keyword:
            return QueryType.HYBRID
        
        # Strong SQL indicators only
        if contains_sql_keyword:
            return QueryType.SQL
        
        # Data queries without strong SQL indicators -> hybrid (could be in DB or docs)
        if contains_data_keyword:
            return QueryType.HYBRID
        
        # Default to hybrid for ambiguous queries
        return QueryType.HYBRID
