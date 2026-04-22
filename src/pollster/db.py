import pathlib

import duckdb
import pandas as pd

from pollster.config import DB_FILENAME


def get_connection(data_dir: pathlib.Path) -> duckdb.DuckDBPyConnection:
    db_path = data_dir / DB_FILENAME
    return duckdb.connect(str(db_path))


def register_parquet(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    parquet_path: pathlib.Path,
) -> None:
    con.execute(
        f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM '{parquet_path}'"
    )


def query_to_df(
    con: duckdb.DuckDBPyConnection, sql: str
) -> pd.DataFrame:
    return con.execute(sql).fetchdf()
