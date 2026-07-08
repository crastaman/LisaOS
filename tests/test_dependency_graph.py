"""Proof-of-work tests for the LisaOS Dependency Graph Engine (Phase 2).

Validates core/dependency_graph.py: fail-closed construction (cycles, unknown
deps, self-deps, duplicate ids), continuous ready-frontier maintenance, and
failure propagation to dependents (blocked state).

Fully hermetic: pure data structure, no I/O, no provider calls.

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_dependency_graph -v
"""

import unittest

from core.workforce_resolver import WorkPackage
from core.dependency_graph import DependencyGraph, GraphError


def _pkg(id_, deps=None):
    return WorkPackage(id=id_, description="x", required_capabilities=["x"],
                       depends_on=deps or [])


# --------------------------------------------------------------------------- #
# Construction / fail-closed validation
# --------------------------------------------------------------------------- #

class TestConstructionValidation(unittest.TestCase):
    def test_valid_graph_constructs(self):
        g = DependencyGraph.from_packages([_pkg("a"), _pkg("b", ["a"])])
        self.assertEqual(len(g.packages), 2)

    def test_duplicate_id_raises(self):
        with self.assertRaises(GraphError):
            DependencyGraph.from_packages([_pkg("a"), _pkg("a")])

    def test_unknown_dependency_raises(self):
        with self.assertRaises(GraphError) as ctx:
            DependencyGraph.from_packages([_pkg("a", ["ghost"])])
        self.assertIn("ghost", str(ctx.exception))

    def test_self_dependency_raises(self):
        with self.assertRaises(GraphError):
            DependencyGraph.from_packages([_pkg("a", ["a"])])

    def test_two_node_cycle_raises(self):
        with self.assertRaises(GraphError) as ctx:
            DependencyGraph.from_packages([_pkg("x", ["y"]), _pkg("y", ["x"])])
        self.assertIn("cycle", str(ctx.exception).lower())

    def test_longer_cycle_raises(self):
        with self.assertRaises(GraphError):
            DependencyGraph.from_packages([
                _pkg("a", ["b"]), _pkg("b", ["c"]), _pkg("c", ["a"]),
            ])

    def test_diamond_shaped_graph_is_valid(self):
        # a -> b,c -> d (b and c both depend on a; d depends on both)
        g = DependencyGraph.from_packages([
            _pkg("a"), _pkg("b", ["a"]), _pkg("c", ["a"]), _pkg("d", ["b", "c"]),
        ])
        self.assertEqual(len(g.packages), 4)


# --------------------------------------------------------------------------- #
# Ready frontier maintenance
# --------------------------------------------------------------------------- #

class TestReadyFrontier(unittest.TestCase):
    def test_independent_packages_all_ready_immediately(self):
        g = DependencyGraph.from_packages([_pkg("a"), _pkg("b"), _pkg("c")])
        self.assertEqual({p.id for p in g.ready_frontier()}, {"a", "b", "c"})

    def test_dependent_package_not_ready_until_deps_complete(self):
        g = DependencyGraph.from_packages([_pkg("a"), _pkg("b"), _pkg("c", ["a", "b"])])
        self.assertEqual({p.id for p in g.ready_frontier()}, {"a", "b"})
        g.mark_complete("a")
        self.assertEqual({p.id for p in g.ready_frontier()}, {"b"})
        g.mark_complete("b")
        self.assertEqual({p.id for p in g.ready_frontier()}, {"c"})
        g.mark_complete("c")
        self.assertEqual(g.ready_frontier(), [])
        self.assertTrue(g.is_done())

    def test_in_progress_package_excluded_from_frontier(self):
        g = DependencyGraph.from_packages([_pkg("a")])
        g.mark_in_progress("a")
        self.assertEqual(g.ready_frontier(), [])

    def test_diamond_frontier_evolution(self):
        g = DependencyGraph.from_packages([
            _pkg("a"), _pkg("b", ["a"]), _pkg("c", ["a"]), _pkg("d", ["b", "c"]),
        ])
        self.assertEqual({p.id for p in g.ready_frontier()}, {"a"})
        g.mark_complete("a")
        self.assertEqual({p.id for p in g.ready_frontier()}, {"b", "c"})
        g.mark_complete("b")
        self.assertEqual({p.id for p in g.ready_frontier()}, {"c"})  # d still waits on c
        g.mark_complete("c")
        self.assertEqual({p.id for p in g.ready_frontier()}, {"d"})


# --------------------------------------------------------------------------- #
# Failure propagation (blocked state)
# --------------------------------------------------------------------------- #

class TestFailurePropagation(unittest.TestCase):
    def test_failed_package_blocks_direct_dependent(self):
        g = DependencyGraph.from_packages([_pkg("a"), _pkg("b", ["a"])])
        g.mark_failed("a")
        self.assertIn("b", g.blocked())
        self.assertEqual(g.ready_frontier(), [])

    def test_failure_propagates_transitively(self):
        g = DependencyGraph.from_packages([
            _pkg("a"), _pkg("b", ["a"]), _pkg("c", ["b"]), _pkg("d", ["c"]),
        ])
        g.mark_failed("a")
        self.assertEqual(g.blocked(), {"b", "c", "d"})

    def test_is_done_true_once_failed_and_blocked_cover_all(self):
        g = DependencyGraph.from_packages([_pkg("a"), _pkg("b", ["a"])])
        g.mark_failed("a")
        self.assertTrue(g.is_done())  # a=failed, b=blocked -> nothing left runnable

    def test_independent_sibling_unaffected_by_unrelated_failure(self):
        g = DependencyGraph.from_packages([_pkg("a"), _pkg("b"), _pkg("c", ["a"])])
        g.mark_failed("a")
        # b is independent of a -- must remain ready, not blocked.
        self.assertIn("b", {p.id for p in g.ready_frontier()})
        self.assertIn("c", g.blocked())
        self.assertNotIn("b", g.blocked())


# --------------------------------------------------------------------------- #
# Summary / remaining
# --------------------------------------------------------------------------- #

class TestSummary(unittest.TestCase):
    def test_summary_counts(self):
        g = DependencyGraph.from_packages([_pkg("a"), _pkg("b"), _pkg("c", ["a"])])
        g.mark_complete("a")
        g.mark_in_progress("b")
        s = g.summary()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["completed"], 1)
        self.assertEqual(s["in_progress"], 1)
        self.assertEqual(s["ready"], 1)  # c, now that a is complete

    def test_remaining_excludes_terminal_states(self):
        g = DependencyGraph.from_packages([_pkg("a"), _pkg("b", ["a"])])
        g.mark_failed("a")
        self.assertEqual(g.remaining(), [])  # a failed, b blocked -- nothing remains


if __name__ == "__main__":
    unittest.main(verbosity=2)
