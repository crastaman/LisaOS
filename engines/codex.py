from core.engine import Engine

class CodexEngine(Engine):
    name = "codex"

    def run(self, prompt: str, cwd: str | None = None) -> int:
        print("CodexEngine is a stub for now. VS Code Codex integration will be added later.")
        return 0
