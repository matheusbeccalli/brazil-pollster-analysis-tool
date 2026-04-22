import pathlib
import duckdb
import pandas as pd
import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    (tmp_path / "parquet").mkdir()
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.fixture
def tmp_db(tmp_data_dir):
    db_path = tmp_data_dir / "pollster.duckdb"
    con = duckdb.connect(str(db_path))
    yield con
    con.close()
