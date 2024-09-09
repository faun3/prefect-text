from prefect import task, flow
from prefect.logging import get_logger, get_run_logger

run_logger = get_run_logger()
logger = get_logger()

@task
def log_something(something: str) -> None:
    print(something)
    run_logger.info(something)
    logger.info(something)


@flow(log_prints=True)
def log_repo_info():
    log_something("Hello, world!")
