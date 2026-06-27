import subprocess
import threading
import time
import signal
from core.engine import Engine

class ClaudeEngine(Engine):
    name = "claude"

    def run(self, prompt: str, cwd: str | None = None) -> int:
        stop = threading.Event()
        start = time.time()
        process = None

        def heartbeat():
            while not stop.is_set():
                elapsed = int(time.time() - start)
                mins = elapsed // 60
                secs = elapsed % 60
                print(f"⏳ Claude Code working... {mins:02d}:{secs:02d} elapsed", flush=True)
                stop.wait(15)

        print("────────────────────────────────────────")
        print("Lisa Engine: Claude Code")
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
                        print(f"Claude: {clean}", flush=True)

            return_code = process.wait()
            elapsed = int(time.time() - start)
            mins = elapsed // 60
            secs = elapsed % 60

            if return_code == 0:
                print(f"✅ Claude Code completed in {mins:02d}:{secs:02d}.", flush=True)
            else:
                print(f"❌ Claude Code exited with code {return_code} after {mins:02d}:{secs:02d}.", flush=True)

            return return_code

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

            return 130

        finally:
            stop.set()
            thread.join(timeout=1)
