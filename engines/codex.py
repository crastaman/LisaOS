import subprocess
import time
from datetime import datetime
from core.engine import Engine
from core.result import TaskResult

class CodexEngine(Engine):
    name = "codex"

    def run(self, prompt: str, cwd: str | None = None, skill: str = "unknown") -> TaskResult:
        started = datetime.now()
        start_time = time.time()
        output_lines = []

        print("────────────────────────────────────────")
        print("Lisa Engine: Codex")
        print(f"Skill: {skill}")
        print(f"Working directory: {cwd}")
        print("Status: Starting task")
        print("────────────────────────────────────────")

        process = subprocess.Popen(
            ["codex", "exec", "--sandbox", "read-only", prompt],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if process.stdout:
            for line in process.stdout:
                clean = line.rstrip()
                if clean:
                    output_lines.append(clean)
                    print(f"Codex: {clean}", flush=True)

        return_code = process.wait()
        finished = datetime.now()
        duration = time.time() - start_time

        return TaskResult(
            skill=skill,
            engine=self.name,
            status="success" if return_code == 0 else f"failed:{return_code}",
            started=started,
            finished=finished,
            duration=duration,
            output="\n".join(output_lines),
        )
