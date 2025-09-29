from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SQLQuery:
    sql: str
    params: Dict[str, object]
    description: str


class SQLGenerator:
    """Rule-based SQL generator that supports common HR analytics queries."""

    def __init__(self, schema: Dict[str, object]) -> None:
        self._schema = schema

    def generate(self, query: str, table: str | None = None) -> Optional[SQLQuery]:
        normalized = query.lower()
        target_table = table or self._default_employee_table()
        if not target_table:
            return None

        if "how many" in normalized or "count" in normalized:
            return SQLQuery(
                sql=f"SELECT COUNT(*) AS total FROM {target_table}",
                params={},
                description="Count rows",
            )

        if "average" in normalized and "department" in normalized:
            salary_column = self._find_column(target_table, {"salary", "compensation", "pay", "pay_rate"})
            department_column = self._find_column(target_table, {"department", "dept", "division"})
            if salary_column and department_column:
                return SQLQuery(
                    sql=(
                        f"SELECT {department_column} AS department, AVG({salary_column}) AS average_salary "
                        f"FROM {target_table} GROUP BY {department_column} ORDER BY average_salary DESC"
                    ),
                    params={},
                    description="Average salary grouped by department",
                )

        if "hired" in normalized or "joined" in normalized:
            date_column = self._find_column(target_table, {"join_date", "start_date", "hired_on", "hire_date"})
            if date_column:
                if "this year" in normalized:
                    return SQLQuery(
                        sql=(
                            f"SELECT * FROM {target_table} "
                            f"WHERE strftime('%Y', {date_column}) = strftime('%Y', 'now')"
                        ),
                        params={},
                        description="Employees hired this year",
                    )
                match = re.search(r"last (\d+) year", normalized)
                if "last year" in normalized or match:
                    years = int(match.group(1)) if match else 1
                    return SQLQuery(
                        sql=(
                            f"SELECT * FROM {target_table} "
                            f"WHERE {date_column} >= DATE('now', '-{years} years')"
                        ),
                        params={},
                        description="Employees hired in recent years",
                    )

        if "reports to" in normalized:
            manager_column = self._find_column(target_table, {"reports_to", "manager_id", "manager"})
            name_column = self._find_column(target_table, {"name", "full_name", "employee_name"})
            if manager_column and name_column:
                manager_name = self._extract_name(normalized)
                if manager_name:
                    return SQLQuery(
                        sql=(
                            f"SELECT * FROM {target_table} "
                            f"WHERE lower({manager_column}) = :manager"
                        ),
                        params={"manager": manager_name.lower()},
                        description="Employees reporting to manager",
                    )

        if "top" in normalized and "highest" in normalized:
            salary_column = self._find_column(target_table, {"salary", "compensation", "pay", "pay_rate"})
            department_column = self._find_column(target_table, {"department", "division", "dept"})
            top_match = re.search(r"top (\d+)", normalized)
            limit = int(top_match.group(1)) if top_match else 5
            if salary_column:
                order_clause = f"ORDER BY {salary_column} DESC"
                select_columns = "*"
                if department_column and "each" in normalized and "department" in normalized:
                    select_columns = f"{department_column}, {salary_column}, *"
                return SQLQuery(
                    sql=(
                        f"SELECT {select_columns} FROM {target_table} "
                        f"{order_clause} LIMIT {limit}"
                    ),
                    params={},
                    description="Top earners",
                )

        if "skill" in normalized or "skills" in normalized:
            skills_column = self._find_column(target_table, {"skills", "skillset", "competencies"})
            salary_column = self._find_column(target_table, {"salary", "compensation", "pay"})
            keyword = self._extract_skill(normalized)
            salary_threshold = self._extract_salary_threshold(normalized)
            if skills_column:
                conditions: List[str] = []
                params: Dict[str, object] = {}
                if keyword:
                    conditions.append(f"lower({skills_column}) LIKE :skill")
                    params["skill"] = f"%{keyword.lower()}%"
                if salary_column and salary_threshold:
                    conditions.append(f"{salary_column} >= :salary")
                    params["salary"] = salary_threshold
                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
                return SQLQuery(
                    sql=f"SELECT * FROM {target_table}{where_clause}",
                    params=params,
                    description="Employees filtered by skill and salary",
                )

        return None

    def _default_employee_table(self) -> Optional[str]:
        tables = self._schema.get("tables", [])
        for table in tables:
            if any(keyword in table["name"].lower() for keyword in ("employee", "staff", "person")):
                return table["name"]
        return tables[0]["name"] if tables else None

    def _find_column(self, table: str, keywords: set[str]) -> Optional[str]:
        for schema_table in self._schema.get("tables", []):
            if schema_table["name"] != table:
                continue
            for column in schema_table["columns"]:
                lower = column.lower()
                if any(keyword in lower for keyword in keywords):
                    return column
        return None

    def _extract_name(self, normalized: str) -> Optional[str]:
        match = re.search(r"reports to ([a-z\s]+)", normalized)
        if match:
            return match.group(1).strip()
        return None

    def _extract_skill(self, normalized: str) -> Optional[str]:
        match = re.search(r"(python|java|aws|azure|sql|excel)", normalized)
        if match:
            return match.group(1)
        return None

    def _extract_salary_threshold(self, normalized: str) -> Optional[int]:
        match = re.search(r"over (\d{2,6})", normalized)
        if match:
            return int(match.group(1))
        match = re.search(r"(\d{2,6})k", normalized)
        if match:
            return int(match.group(1)) * 1000
        return None
