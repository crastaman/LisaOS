from abc import ABC, abstractmethod

class Engine(ABC):
    name = "base"

    @abstractmethod
    def run(self, prompt: str, cwd: str | None = None) -> int:
        pass
