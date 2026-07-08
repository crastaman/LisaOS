"""LisaOS Dependency Graph Engine (Phase 2).

Turns a flat set of WorkPackages (each optionally declaring `depends_on` ids)
into a graph that can be queried for its READY FRONTIER -- the set of
packages whose dependencies are all satisfied and that are not yet
completed, failed, blocked, or already in progress.

Design guarantees:
  * FAIL CLOSED on construction. An unknown dependency id or a dependency
    cycle raises GraphError immediately -- an unschedulable graph is never
    silently accepted.
  * The frontier is CONTINUOUSLY MAINTAINED: calling ready_frontier() after
    any mark_complete()/mark_failed() call reflects the new state; nothing
    is cached staleley.
  * A package that transitively depends on a FAILED package becomes BLOCKED
    (a distinct, permanent terminal state) rather than being silently
    dropped or endlessly retried.

This module has no third-party dependencies and performs no I/O, so it is
safe and free to unit test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from core.workforce_resolver import WorkPackage


class GraphError(Exception):
    """Raised when a set of work packages cannot form a valid schedule."""


@dataclass
class DependencyGraph:
    """A dependency graph over WorkPackages with ready-frontier tracking."""

    packages: dict[str, WorkPackage]
    completed: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    in_progress: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._validate_references()
        self._detect_cycles()

    # ---- construction ------------------------------------------------------

    @classmethod
    def from_packages(cls, packages: Iterable[WorkPackage]) -> "DependencyGraph":
        by_id: dict[str, WorkPackage] = {}
        for p in packages:
            if p.id in by_id:
                raise GraphError(f"duplicate work package id: {p.id!r}")
            by_id[p.id] = p
        return cls(packages=by_id)

    def _validate_references(self) -> None:
        for pkg in self.packages.values():
            if pkg.id in pkg.depends_on:
                raise GraphError(f"{pkg.id!r} depends on itself")
            for dep in pkg.depends_on:
                if dep not in self.packages:
                    raise GraphError(
                        f"{pkg.id!r} depends on unknown package {dep!r}"
                    )

    def _detect_cycles(self) -> None:
        WHITE, GREY, BLACK = 0, 1, 2
        color: dict[str, int] = {pid: WHITE for pid in self.packages}

        def visit(pid: str, path: list[str]) -> None:
            color[pid] = GREY
            for dep in self.packages[pid].depends_on:
                if color[dep] == GREY:
                    cycle = " -> ".join(path + [dep])
                    raise GraphError(f"dependency cycle detected: {cycle}")
                if color[dep] == WHITE:
                    visit(dep, path + [dep])
            color[pid] = BLACK

        for pid in self.packages:
            if color[pid] == WHITE:
                visit(pid, [pid])

    # ---- state transitions --------------------------------------------------

    def mark_in_progress(self, package_id: str) -> None:
        self._require_known(package_id)
        self.in_progress.add(package_id)

    def mark_complete(self, package_id: str) -> None:
        self._require_known(package_id)
        self.in_progress.discard(package_id)
        self.completed.add(package_id)

    def mark_failed(self, package_id: str) -> None:
        self._require_known(package_id)
        self.in_progress.discard(package_id)
        self.failed.add(package_id)

    def _require_known(self, package_id: str) -> None:
        if package_id not in self.packages:
            raise GraphError(f"unknown package id: {package_id!r}")

    # ---- queries -------------------------------------------------------------

    def blocked(self) -> set[str]:
        """Packages that can never run because a transitive dependency failed.

        Computed fresh each call so it always reflects current failed/blocked
        state (no staleness).
        """
        blocked: set[str] = set()
        changed = True
        terminal_bad = set(self.failed)
        while changed:
            changed = False
            for pid, pkg in self.packages.items():
                if pid in self.completed or pid in terminal_bad or pid in blocked:
                    continue
                if any(dep in terminal_bad or dep in blocked for dep in pkg.depends_on):
                    blocked.add(pid)
                    changed = True
        return blocked

    def ready_frontier(self) -> list[WorkPackage]:
        """Packages whose dependencies are all satisfied and are runnable now.

        Excludes completed, failed, blocked, and in-progress packages.
        Returned in stable (insertion) order; callers may reorder for
        scheduling policy (e.g. subscription-priority) without affecting
        correctness.
        """
        blocked = self.blocked()
        frontier: list[WorkPackage] = []
        for pid, pkg in self.packages.items():
            if pid in self.completed or pid in self.failed or pid in blocked:
                continue
            if pid in self.in_progress:
                continue
            if all(dep in self.completed for dep in pkg.depends_on):
                frontier.append(pkg)
        return frontier

    def is_done(self) -> bool:
        """True once every package is completed, failed, or blocked."""
        terminal = self.completed | self.failed | self.blocked()
        return len(terminal) == len(self.packages)

    def remaining(self) -> list[WorkPackage]:
        """Packages not yet completed, failed, or blocked (may include in-progress)."""
        terminal = self.completed | self.failed | self.blocked()
        return [p for pid, p in self.packages.items() if pid not in terminal]

    def summary(self) -> dict[str, int]:
        blocked = self.blocked()
        return {
            "total": len(self.packages),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "blocked": len(blocked),
            "in_progress": len(self.in_progress),
            "ready": len(self.ready_frontier()),
        }
