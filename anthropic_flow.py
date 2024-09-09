from prefect import task, flow

from lib.AnthropicWrapper import AnthropicWrapper


@task
def get_meaning_of_life():
    meaning = AnthropicWrapper.prompt_and_answer()
    return meaning


@flow(log_prints=True)
def life_flow():
    meaning = get_meaning_of_life()
    print(f"The meaning of life is {meaning}.")


if __name__ == "__main__":
    life_flow()