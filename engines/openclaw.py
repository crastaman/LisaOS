from core.engine import Engine

class OpenClawEngine(Engine):
    name = "openclaw"

    def run(self, prompt: str, cwd: str | None = None) -> int:
        print("OpenClawEngine is a stub for now.")
        return 0
