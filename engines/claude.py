import subprocess
import threading
import time
import signal
from datetime import datetime
from core.engine import Engine
from core.result import TaskResult

class ClaudeEngine(Engine):
    name = "claude"

    def run(self, prompt: str, cwd: str | None = None, skill: str = "unknown") -> TaskResult:
        stop = threading.Event()
        started = datetime.now()
        start_time = time.time()
        process = None
        output_lines = []

        def heartbeat():
            while not stop.is_set():
                elapsed = int(time.time() - start_time)
                mins = elapsed // 60
                secs = elapsed % 60
                print(f"⏳ Claude Code working... {mins:02d}:{secs:02d} elapsed", flush=True)
                stop.wait(15)

        print("────────────────────────────────────────")
        print("Lisa Engine: Claude Code")
        print(f"Skill: {skill}")
        print(f"Working directory: {cwd}")
        print("Status: Starting task")
        print("────────────────────────────────────────")

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()

        try:
            process = subprocess.Popen(
                ["claude", "-p", prompt],
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
                        print(f"Claude: {clean}", flush=True)

            return_code = process.wait()
            finished = datetime.now()
            duration = time.time() - start_time

            status = "success" if return_code == 0 else f"failed:{return_code}"

            if return_code == 0:
                print(f"✅ Claude Code completed in {int(duration)}s.", flush=True)
            else:
                print(f"❌ Claude Code exited with code {return_code} after {int(duration)}s.", flush=True)

            return TaskResult(
                skill=skill,
                engine=self.name,
                status=status,
                started=started,
                finished=finished,
                duration=duration,
                output="\n".join(output_lines),
            )

        except KeyboardInterrupt:
            print("\n🛑 Cancelled by user. Stopping Claude Code...", flush=True)

            if process and process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()

            finished = datetime.now()
            duration = time.time() - start_time

            return TaskResult(
                skill=skill,
                engine=self.name,
                status="cancelled",
                started=started,
                finished=finished,
                duration=duration,
                output="\n".join(output_lines),
            )

        finally:
            stop.set()
            thread.join(timeout=1)
