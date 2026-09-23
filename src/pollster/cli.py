import pathlib
import click
from pollster import config
from pollster import db as db_module


@click.group()
def cli():
    """Brazilian election pollster accuracy analysis tool."""
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def fetch(force):
    """Download poll and results data from Base dos Dados."""
    from pollster.stages.fetch import fetch_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    fetch_data(data_dir, force=force)


@cli.command("fetch-2026")
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def fetch_2026_cmd(force):
    """Download 2026 presidential polls from the Poder360 aggregator."""
    from pollster.stages.fetch2026 import fetch_2026
    fetch_2026(pathlib.Path(config.DATA_DIR_NAME), force=force)


@cli.command("fetch-markets")
@click.option("--as-of", "as_of", type=click.DateTime(formats=["%Y-%m-%d"]), default=None,
              help="Snapshot date used for the raw JSON folder (default: today).")
def fetch_markets_cmd(as_of):
    """Store Kalshi and Polymarket markets on the Brazilian election (raw JSON + tables)."""
    from pollster.stages.fetch_markets import fetch_markets
    fetch_markets(pathlib.Path(config.DATA_DIR_NAME), as_of=as_of.date() if as_of else None)


@cli.command()
def assemble():
    """Build unified polls-vs-actual dataset."""
    from pollster.stages.assemble import assemble_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    assemble_data(con, data_dir=data_dir)
    con.close()


@cli.command()
@click.option("--since", default=config.DEFAULT_SINCE_YEAR, type=int,
              help="Start year for analysis window.")
def analyze(since):
    """Compute accuracy metrics and pollster rankings."""
    from pollster.stages.analyze import analyze_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    analyze_data(con, since=since, data_dir=data_dir)
    con.close()


@cli.command()
@click.option("--since", default=config.DEFAULT_SINCE_YEAR, type=int,
              help="Start year for analysis window.")
def report(since):
    """Generate HTML accuracy report."""
    from pollster.stages.report import generate_report
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    output_path = data_dir / "reports" / "pollster_accuracy_report.html"
    generate_report(con, output_path)
    con.close()


@cli.command()
@click.option("--since", default=config.DEFAULT_SINCE_YEAR, type=int,
              help="Start year for analysis window.")
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def run(since, force):
    """Run full pipeline: fetch -> assemble -> analyze -> report."""
    from pollster.stages.fetch import fetch_data
    from pollster.stages.assemble import assemble_data
    from pollster.stages.analyze import analyze_data
    from pollster.stages.report import generate_report

    data_dir = pathlib.Path(config.DATA_DIR_NAME)

    fetch_data(data_dir, force=force)

    con = db_module.get_connection(data_dir)
    assemble_data(con, data_dir=data_dir)
    analyze_data(con, since=since, data_dir=data_dir)

    output_path = data_dir / "reports" / "pollster_accuracy_report.html"
    generate_report(con, output_path)
    con.close()

    click.echo("Full pipeline complete.")


@cli.command()
@click.option("--as-of", "as_of", type=click.DateTime(formats=["%Y-%m-%d"]), default=None,
              help="Reference date (default: today).")
@click.option("--window-days", default=config.PROJECTION_WINDOW_DAYS, type=int, show_default=True,
              help="Use polls from the last N days.")
@click.option("--sims", default=config.PROJECTION_N_SIMS, type=int, show_default=True,
              help="Number of Monte Carlo simulations.")
def project(as_of, window_days, sims):
    """Project the 2026 presidential election (1st and 2nd round) from recent polls."""
    from pollster.stages.project import project_election
    from pollster.stages.project_report import generate_projection_report
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    result = project_election(con, as_of=as_of.date() if as_of else None,
                              window_days=window_days, n_sims=sims, data_dir=data_dir)
    all_polls = con.execute("SELECT * FROM polls_2026").fetchdf()
    output_path = data_dir / "reports" / "projecao_2026.html"
    generate_projection_report(result, all_polls, output_path)
    con.close()
    click.echo(f"Projection report written to {output_path}")


@cli.command()
@click.argument("sql", required=False)
@click.option("--sql-file", type=click.Path(exists=True), help="Read SQL from a file.")
@click.option("--format", "fmt", default="table",
              type=click.Choice(["table", "csv", "json", "parquet"]))
@click.option("--output", "-o", type=click.Path(), help="Output file path (required for parquet).")
def query(sql, sql_file, fmt, output):
    """Run ad-hoc SQL against the local DuckDB database."""
    if sql_file:
        sql = pathlib.Path(sql_file).read_text()
    if not sql:
        raise click.ClickException("Provide SQL as an argument or via --sql-file.")

    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    try:
        df = db_module.query_to_df(con, sql)
    except Exception as e:
        raise click.ClickException(str(e))
    finally:
        con.close()

    if fmt == "parquet":
        if not output:
            raise click.ClickException("--output is required for parquet format.")
        df.to_parquet(output, index=False)
        click.echo(f"Written {len(df)} rows to {output}")
    elif fmt == "csv":
        click.echo(df.to_csv(index=False))
    elif fmt == "json":
        click.echo(df.to_json(orient="records", indent=2))
    else:
        click.echo(df.to_string(index=False))
