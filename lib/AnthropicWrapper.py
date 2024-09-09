from anthropic import Anthropic
from prefect.blocks.system import Secret

class AnthropicWrapper:
    API = Anthropic(api_key=Secret.load("anthropic-api-key").get())

    @staticmethod
    def prompt_and_answer() -> str:
        prompt = "What is the meaning of life?"

        message = AnthropicWrapper.API.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )

        print("Response from Claude was:", message.content[0].text)
        return message.content[0].text