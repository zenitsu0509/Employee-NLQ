from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.engine import Engine


@dataclass
class ImportOptions:
    table_name: Optional[str] = None
    if_exists: str = "append"  # 'fail' | 'replace' | 'append'
    chunksize: int = 5000
    delimiter: Optional[str] = None  # CSV delimiter override
    sheet_name: Optional[str] = None  # Excel sheet name/index


_SAFE_TABLE = re.compile(r"[^a-z0-9_]+")


def _sanitize_table_name(name: str) -> str:
    name = name.strip().lower()
    name = name.replace(" ", "_")
    name = _SAFE_TABLE.sub("_", name)
    name = name.strip("_")
    if not name:
        name = "imported_table"
    return name[:63]  # Postgres identifier limit


def import_file_to_db(engine: Engine, path: Path, options: ImportOptions) -> str:
    """Import a CSV or Excel file into the target database using pandas.to_sql.

    Returns the final table name used.
    """
    suffix = path.suffix.lower()
    table = options.table_name or _sanitize_table_name(path.stem)

    if suffix in {".csv", ".tsv"}:
        sep = options.delimiter or ("\t" if suffix == ".tsv" else ",")
        # Use chunked reads to control memory and support large files
        # If file is small, read it fully (chunksize=None) to preserve dtypes better
        try:
            # Try chunked import first for scalability
            reader = pd.read_csv(path, sep=sep, chunksize=options.chunksize)
            first = True if options.if_exists == "replace" else False
            for chunk in reader:
                chunk.to_sql(
                    table,
                    engine,
                    if_exists=("replace" if first and options.if_exists == "replace" else "append"),
                    index=False,
                )
                first = False
        except ValueError:
            # Fallback to non-chunked (e.g., for very small files)
            df = pd.read_csv(path, sep=sep)
            df.to_sql(table, engine, if_exists=options.if_exists, index=False)
        return table

    if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        df = pd.read_excel(path, sheet_name=options.sheet_name or 0, engine="openpyxl")
        df.to_sql(table, engine, if_exists=options.if_exists, index=False)
        return table

    raise ValueError(f"Unsupported tabular file type: {path.name}")
