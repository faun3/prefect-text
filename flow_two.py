from prefect import flow, task
from prefect_sqlalchemy import SqlAlchemyConnector


@task
def fetch_data(block_name: str, table_name: str, order_by_col: str) -> list:
    rows = []
    with SqlAlchemyConnector.load(block_name) as connector:
        rows = connector.fetch_many("SELECT * FROM {} ORDER BY {}".format(table_name, order_by_col), size=10)
    return rows


@flow(log_prints=True)
def alchemy(block_name: str, table_name: str, order_by_col: str):
    rows = fetch_data(block_name, table_name, order_by_col)
    for row in rows:
        print(row)


if __name__ == "__main__":
    alchemy("etl-sqlalchemy-connector", "qualifiedjob", "processed_date")
