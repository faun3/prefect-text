from prefect import flow, task
from sqlalchemy import Engine, create_engine, text
from prefect.tasks import task_input_hash
from prefect.blocks.system import Secret
from datetime import timedelta


def get_db_connection():
    conn_string = Secret.load("etl-staging-db-connection-string")
    engine = create_engine(conn_string)
    return engine


@task
def fetch_latest_10_rows_from_table(engine: Engine, table_name: str, order_by_col: str):
    with engine.connect() as connection:
        query = text(f"SELECT * FROM {table_name} ORDER BY {order_by_col} DESC LIMIT 10")
        res = connection.execute(query)
        return res.fetchall()


@flow(log_prints=True)
def print_first_10_rows(engine: Engine, table_name: str, order_by_col: str):
    rows = fetch_latest_10_rows_from_table(engine, table_name, order_by_col)

    print(f"First 10 rows from {table_name} ordered by {order_by_col}:")
    for row in rows:
        print(row)


if __name__ == "__main__":
    engine = get_db_connection()
    table_name = "qualifiedjob"
    order_by_col = "processed_date"

    print_first_10_rows(engine, table_name, order_by_col)
