from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import create_engine, text

from backend.api.services.query_engine import QueryEngine


class DummySentenceTransformer:
    def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - simple stub
        self._dimension = 16

    def get_sentence_embedding_dimension(self) -> int:
        return self._dimension

    def encode(self, sentences, show_progress_bar: bool = False):  # noqa: D401
        vectors = []
        for sentence in sentences:
            seed = abs(hash(sentence)) % 10_000
            rng = np.random.default_rng(seed)
            vectors.append(rng.random(self._dimension))
        return np.array(vectors)


@pytest.fixture(scope="module")
def sqlite_db(tmp_path_factory) -> str:
    db_path = tmp_path_factory.mktemp("db") / "employees.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE departments (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                );
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE employees (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    department_id INTEGER,
                    compensation REAL,
                    skills TEXT,
                    hire_date TEXT,
                    FOREIGN KEY(department_id) REFERENCES departments(id)
                );
                """
            )
        )
        conn.execute(text("INSERT INTO departments (id, name) VALUES (1, 'Engineering'), (2, 'HR')"))
        conn.execute(
            text(
                """
                INSERT INTO employees (id, name, department_id, compensation, skills, hire_date) VALUES
                (1, 'Alice Johnson', 1, 125000, 'Python,SQL,Leadership', '2022-03-15'),
                (2, 'Bob Smith', 1, 118000, 'Java,Microservices', '2021-07-01'),
                (3, 'Carol White', 2, 95000, 'Recruiting,Excel', '2023-01-10');
                """
            )
        )
    return f"sqlite:///{db_path}"


@pytest.fixture(autouse=True)
def patch_sentence_transformer(monkeypatch):
    monkeypatch.setattr("backend.api.services.query_engine.SentenceTransformer", DummySentenceTransformer)
    yield


def test_schema_discovery(sqlite_db):
    engine = QueryEngine(sqlite_db)
    schema_tables = {table["name"] for table in engine.schema["tables"]}
    assert "employees" in schema_tables
    assert "departments" in schema_tables


def test_sql_query_processing(sqlite_db):
    engine = QueryEngine(sqlite_db)
    response = engine.process_query("How many employees do we have?")
    assert response["query_type"] == "sql"
    assert response["results"]
    assert response["results"][0]["total"] == 3


def test_document_ingestion_and_search(tmp_path, sqlite_db):
    sample_path = tmp_path / "resume.txt"
    sample_path.write_text(
        """Jane Doe\nPython Developer\nSkills: Python, FastAPI, SQL\nExperience: Built internal tools.""",
        encoding="utf-8",
    )

    engine = QueryEngine(sqlite_db)
    engine.document_processor.process_documents([sample_path])

    response = engine.process_query("Find resumes mentioning Python skills", top_k=3)
    assert response["query_type"] == "document"
    assert response.get("sources")
    assert any("Python" in chunk["content"] for chunk in response["sources"])
