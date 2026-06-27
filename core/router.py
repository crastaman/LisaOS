from engines.claude import ClaudeEngine
from engines.codex import CodexEngine
from engines.gpt import GPTEngine
from engines.openclaw import OpenClawEngine

ENGINES = {
    "claude": ClaudeEngine(),
    "codex": CodexEngine(),
    "gpt": GPTEngine(),
    "openclaw": OpenClawEngine(),
}

def choose_engine(skill):
    preferred = skill.get("preferred_engine", "claude")
    if preferred == "auto":
        return ENGINES["claude"]
    return ENGINES.get(preferred, ENGINES["claude"])
