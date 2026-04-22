import pandas as pd
from click.testing import CliRunner
from pollster.cli import cli
from pollster.db import get_connection


def test_query_command(tmp_data_dir, monkeypatch):
    monkeypatch.setattr("pollster.config.DATA_DIR_NAME", str(tmp_data_dir))
    con = get_connection(tmp_data_dir)
    con.execute("CREATE TABLE test_t AS SELECT 1 AS x, 'hello' AS y")
    con.close()

    runner = CliRunner()
    result = runner.invoke(cli, ["query", "SELECT * FROM test_t"])
    assert result.exit_code == 0
    assert "hello" in result.output


def test_query_csv_format(tmp_data_dir, monkeypatch):
    monkeypatch.setattr("pollster.config.DATA_DIR_NAME", str(tmp_data_dir))
    con = get_connection(tmp_data_dir)
    con.execute("CREATE TABLE test_t AS SELECT 1 AS x, 'hello' AS y")
    con.close()

    runner = CliRunner()
    result = runner.invoke(cli, ["query", "--format", "csv", "SELECT * FROM test_t"])
    assert result.exit_code == 0
    assert "x,y" in result.output
