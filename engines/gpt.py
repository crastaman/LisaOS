from core.engine import Engine

class GPTEngine(Engine):
    name = "gpt"

    def run(self, prompt: str, cwd: str | None = None) -> int:
        print("GPTEngine is a stub for now.")
        return 0
