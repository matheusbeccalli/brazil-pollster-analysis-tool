import duckdb
import pandas as pd

from pollster.db import get_connection, register_parquet, query_to_df


def test_get_connection(tmp_data_dir):
    con = get_connection(tmp_data_dir)
    result = con.execute("SELECT 1 AS x").fetchone()
    assert result == (1,)
    con.close()


def test_register_parquet(tmp_data_dir):
    parquet_dir = tmp_data_dir / "parquet"
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = parquet_dir / "test.parquet"
    df.to_parquet(path)

    con = get_connection(tmp_data_dir)
    register_parquet(con, "test_table", path)
    result = con.execute("SELECT COUNT(*) FROM test_table").fetchone()
    assert result == (2,)
    con.close()


def test_query_to_df(tmp_data_dir):
    con = get_connection(tmp_data_dir)
    con.execute("CREATE TABLE t AS SELECT 1 AS x, 'hello' AS y")
    df = query_to_df(con, "SELECT * FROM t")
    assert len(df) == 1
    assert df.iloc[0]["y"] == "hello"
    con.close()
