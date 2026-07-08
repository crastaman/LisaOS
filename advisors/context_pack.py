"""GPT Context Pack loader (Lisa Console v1, Phase C2).

Loads docs/GPT_CONTEXT/NN_*.md (01 through 09, sorted numerically) into one
concatenated text block. README.md and CHANGELOG.md are meta-documents (an
index and a revision log, not context content) and are intentionally
excluded -- only files matching the NN_*.md numbered-file convention are
part of the pack. See docs/GPT_CONTEXT/README.md.

Cached in memory, invalidated whenever any numbered file's mtime or size
changes, so a running Console/Advisor process picks up edits to the pack
without a restart, without re-reading file contents on every call.

Read-only. No LisaOS runtime imports (core/, engines/) -- this module only
ever opens files under docs/GPT_CONTEXT/.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
CONTEXT_PACK_DIR = LISA_BASE / "docs" / "GPT_CONTEXT"

_NUMBERED_FILE_RE = re.compile(r"^(\d{2})_.*\.md$")


class ContextPackError(Exception):
    """Raised when the GPT Context Pack cannot be loaded."""


@dataclass(frozen=True)
class ContextPackFile:
    path: Path
    order: int
    mtime: float
    size: int


@dataclass(frozen=True)
class ContextPack:
    text: str
    files: tuple[ContextPackFile, ...]

    @property
    def signature(self) -> tuple:
        return tuple((str(f.path), f.mtime, f.size) for f in self.files)


_cache: dict[Path, ContextPack] = {}


def _discover_files(context_dir: Path) -> list[Path]:
    if not context_dir.is_dir():
        raise ContextPackError(f"GPT Context Pack directory not found: {context_dir}")
    matches: list[tuple[int, Path]] = []
    for p in context_dir.iterdir():
        m = _NUMBERED_FILE_RE.match(p.name)
        if m:
            matches.append((int(m.group(1)), p))
    if not matches:
        raise ContextPackError(f"No numbered context files (NN_*.md) found in {context_dir}")
    matches.sort(key=lambda t: t[0])
    return [p for _, p in matches]


def _current_signature(files: list[Path]) -> tuple:
    return tuple((str(p), p.stat().st_mtime, p.stat().st_size) for p in files)


def _build(files: list[Path]) -> ContextPack:
    parts: list[str] = []
    file_meta: list[ContextPackFile] = []
    for i, p in enumerate(files, start=1):
        stat = p.stat()
        content = p.read_text(encoding="utf-8")
        parts.append(f"--- {p.name} ---\n{content}")
        file_meta.append(ContextPackFile(path=p, order=i, mtime=stat.st_mtime, size=stat.st_size))
    return ContextPack(text="\n\n".join(parts), files=tuple(file_meta))


def load_context_pack(context_dir: Path | None = None, *, force_reload: bool = False) -> ContextPack:
    """Load the GPT Context Pack, using the in-memory cache unless a file changed.

    Raises ContextPackError if the directory is missing or contains no
    numbered files -- callers (advisors.gpt_advisor) should let this
    propagate as a configuration error, not silently proceed with an empty
    pack (an Advisor with no context pack is not a degraded Advisor, it's a
    misconfigured one).
    """
    context_dir = context_dir or CONTEXT_PACK_DIR
    files = _discover_files(context_dir)
    sig = _current_signature(files)

    if not force_reload:
        cached = _cache.get(context_dir)
        if cached is not None and cached.signature == sig:
            return cached

    pack = _build(files)
    _cache[context_dir] = pack
    return pack
