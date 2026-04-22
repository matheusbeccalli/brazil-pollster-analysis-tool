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


@cli.command()
def assemble():
    """Build unified polls-vs-actual dataset."""
    from pollster.stages.assemble import assemble_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    assemble_data(con)
    con.close()


@cli.command()
@click.option("--since", default=2014, type=int, help="Start year for analysis window.")
def analyze(since):
    """Compute accuracy metrics and pollster rankings."""
    click.echo("Analyze not yet implemented.")


@cli.command()
@click.option("--since", default=2014, type=int, help="Start year for analysis window.")
def report(since):
    """Generate HTML accuracy report."""
    click.echo("Report not yet implemented.")


@cli.command()
@click.option("--since", default=2014, type=int, help="Start year for analysis window.")
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def run(since, force):
    """Run full pipeline: fetch -> assemble -> analyze -> report."""
    click.echo("Run not yet implemented.")


@cli.command()
@click.argument("sql")
@click.option("--format", "fmt", default="table", type=click.Choice(["table", "csv", "json"]))
def query(sql, fmt):
    """Run ad-hoc SQL against the local DuckDB database."""
    click.echo("Query not yet implemented.")
