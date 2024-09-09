from prefect import task, flow
from prefect.logging import get_logger, get_run_logger


@task
def log_something(something: str) -> None:
    print(something)
    get_run_logger().info(something)
    # get_logger().info(something)


@flow
def logger_logs():
    log_something("Hello, world!")


if __name__ == "__main__":
    logger_logs()
