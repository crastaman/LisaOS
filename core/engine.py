from abc import ABC, abstractmethod
from core.result import TaskResult

class Engine(ABC):
    name = "base"

    @abstractmethod
    def run(self, prompt: str, cwd: str | None = None, skill: str = "unknown") -> TaskResult:
        pass
