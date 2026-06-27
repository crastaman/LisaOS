from dataclasses import dataclass
from datetime import datetime

@dataclass
class TaskResult:
    skill: str
    engine: str
    status: str
    started: datetime
    finished: datetime
    duration: float
    output: str
