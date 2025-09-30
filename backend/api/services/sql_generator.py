from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


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

        if ("how many" in normalized or "count" in normalized) and "employee" in normalized:
            dept_match = re.search(r"in (the )?([a-z\s]+) department", normalized)
            if not dept_match:
                dept_match = re.search(r"in ([a-z\s]+)", normalized)

            if dept_match:
                dept_name = dept_match.group(2).strip()
                # Find tables and join conditions
                employees_table = self._find_table_by_synonym("employee")
                departments_table = self._find_table_by_synonym("department")
                
                if employees_table and departments_table:
                    relationship = self._find_relationship(employees_table, departments_table)
                    if relationship:
                        from_col = list(relationship["via_columns"].keys())[0]
                        to_col = list(relationship["via_columns"].values())[0]
                        
                        # Find the name column in the departments table
                        dept_name_col = self._find_column(departments_table, {"name"})

                        if dept_name_col:
                            return SQLQuery(
                                sql=(
                                    f"SELECT COUNT(e.*) as count FROM {employees_table} e "
                                    f"JOIN {departments_table} d ON e.{from_col} = d.{to_col} "
                                    f"WHERE lower(d.{dept_name_col}) = :dept_name"
                                ),
                                params={"dept_name": dept_name.lower()},
                                description="Count of employees in a specific department",
                            )

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

        # Top earners (globally or per department)
        if "top" in normalized and (
            "earner" in normalized or "salary" in normalized or "paid" in normalized
            or "compensation" in normalized or "salaries" in normalized or "highest" in normalized
        ):
            salary_column = self._find_column(target_table, {"salary", "compensation", "pay", "pay_rate"})
            department_column = self._find_column(target_table, {"department", "division", "dept", "team"})
            top_match = re.search(r"top\s+(\d+)", normalized)
            limit = int(top_match.group(1)) if top_match else 5
            if salary_column:
                per_dept = (
                    ("each" in normalized and "department" in normalized)
                    or ("per" in normalized and "department" in normalized)
                    or ("by" in normalized and "department" in normalized)
                    or ("in" in normalized and "each department" in normalized)
                ) and department_column is not None

                if per_dept and department_column:
                    # Window function to get top N per department
                    return SQLQuery(
                        sql=(
                            "SELECT * FROM ("
                            f" SELECT *, ROW_NUMBER() OVER (PARTITION BY {department_column} ORDER BY {salary_column} DESC) AS rn"
                            f" FROM {target_table}"
                            ") t WHERE rn <= :limit "
                            f"ORDER BY {department_column}, {salary_column} DESC"
                        ),
                        params={"limit": limit},
                        description="Top earners per department",
                    )
                else:
                    return SQLQuery(
                        sql=(
                            f"SELECT * FROM {target_table} ORDER BY {salary_column} DESC LIMIT :limit"
                        ),
                        params={"limit": limit},
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

    def _find_table_by_synonym(self, table_synonym: str) -> Optional[str]:
        """Finds the first table name that matches a synonym like 'employee' or 'department'."""
        for table_data in self._schema.get("tables", []):
            table_name = table_data["name"]
            # Check table name itself
            if table_synonym in table_name.lower():
                return table_name
            # Check synonyms for the table
            if table_name in self._schema.get("synonyms", {}):
                for syn in self._schema["synonyms"][table_name]:
                    if table_synonym in syn:
                        return table_name
        return None

    def _find_relationship(self, from_table: str, to_table: str) -> Optional[Dict[str, Any]]:
        """Finds a relationship between two tables."""
        for rel in self._schema.get("relationships", []):
            if (rel["from_table"] == from_table and rel["to_table"] == to_table):
                return rel
            if (rel["from_table"] == to_table and rel["to_table"] == from_table):
                # Reverse the relationship to make it usable
                return {
                    "from_table": to_table,
                    "to_table": from_table,
                    "via_columns": {v: k for k, v in rel["via_columns"].items()}
                }
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
