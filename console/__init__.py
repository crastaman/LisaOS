# Lisa Console v1 (Phase C4) -- Flask web UI. Observational and advisory
# only: this package can write a bundle's `decision` field and its own
# audit log, and nothing else. No import of core.dispatcher,
# core.workforce_resolver, or any engines/* module anywhere in this
# package -- verified by grep, same standard as advisors/.
# See docs/LISAOS/CONSOLE/00_ARCHITECTURE.md and 05_UI_SCREENS_SPEC.md.
