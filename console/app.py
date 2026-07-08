"""Lisa Console v1 Flask app (Phase C4).

Server-side rendered only -- no SPA framework, no websocket, no client
state beyond a plain HTML form. Every route is read-only except one:
POST /approvals/<bundle_id>/decide, which calls console.actions
.record_decision() and nothing else. There is no "run", "execute",
"retry", or "force" route anywhere in this file.

No imports of core.dispatcher, core.workforce_resolver, or any
engines/* module (verified by grep, same standard as advisors/ and the
rest of console/). The dispatcher remains the sole execution authority;
this app cannot reach it even if a route handler wanted to.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, url_for

from console import actions, data
from console.auth import init_app as init_auth

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))


def create_app(*, config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(config or {})

    audit_path = app.config.get("AUDIT_PATH")
    init_auth(app, audit_path=audit_path)

    def _dirs() -> dict[str, Path | None]:
        return {
            "bundles_dir": app.config.get("BUNDLES_DIR"),
            "briefs_dir": app.config.get("BRIEFS_DIR"),
            "notifications_dir": app.config.get("NOTIFICATIONS_DIR"),
            "audit_path": app.config.get("AUDIT_PATH"),
            "registry_path": app.config.get("REGISTRY_PATH"),
            "evidence_path": app.config.get("EVIDENCE_PATH"),
        }

    # ----------------------------------------------------------------- #
    # Dashboard
    # ----------------------------------------------------------------- #

    @app.route("/")
    def dashboard():
        dirs = _dirs()
        summary = data.dashboard_summary(
            bundles_dir=dirs["bundles_dir"], briefs_dir=dirs["briefs_dir"],
            audit_path=dirs["audit_path"], registry_path=dirs["registry_path"],
            evidence_path=dirs["evidence_path"],
        )
        return render_template("dashboard.html", summary=summary, identity=g.get("identity"))

    # ----------------------------------------------------------------- #
    # Decision Bundles
    # ----------------------------------------------------------------- #

    @app.route("/bundles")
    def bundles_list():
        bundles = data.list_bundles(_dirs()["bundles_dir"])
        return render_template("bundles_list.html", bundles=bundles)

    @app.route("/bundles/<bundle_id>")
    def bundle_detail(bundle_id: str):
        dirs = _dirs()
        bundle = data.load_bundle(bundle_id, bundles_dir=dirs["bundles_dir"])
        if bundle is None:
            abort(404)
        brief = data.latest_brief_for_bundle(bundle_id, dirs["briefs_dir"])
        return render_template(
            "bundle_detail.html", bundle=bundle, brief=brief,
            bundle_json=json.dumps(bundle, indent=2),
        )

    # ----------------------------------------------------------------- #
    # Executive Briefs
    # ----------------------------------------------------------------- #

    @app.route("/briefs")
    def briefs_list():
        briefs = data.list_briefs(_dirs()["briefs_dir"])
        return render_template("briefs_list.html", briefs=briefs)

    @app.route("/brief/<brief_id>")
    def brief_detail(brief_id: str):
        # Singular route -- matches the console_deep_link format
        # advisors.notify.build_payload() already constructs
        # (f"{base_url}/brief/{brief_id}"), so an ntfy notification's
        # deep link resolves correctly against this app.
        dirs = _dirs()
        brief = data.load_brief(brief_id, briefs_dir=dirs["briefs_dir"])
        if brief is None:
            abort(404)
        bundle = data.load_bundle(brief.get("bundle_id", ""), bundles_dir=dirs["bundles_dir"])
        notification = data.notification_status_for_brief(brief_id, dirs["notifications_dir"])
        return render_template(
            "brief_detail.html", brief=brief, bundle=bundle, notification=notification
        )

    # ----------------------------------------------------------------- #
    # Approvals -- the only screens with a real action
    # ----------------------------------------------------------------- #

    @app.route("/approvals")
    def approvals_list():
        pending = data.list_pending_approvals(_dirs()["bundles_dir"])
        return render_template("approvals_list.html", bundles=pending)

    @app.route("/approvals/<bundle_id>")
    def approval_detail(bundle_id: str):
        dirs = _dirs()
        bundle = data.load_bundle(bundle_id, bundles_dir=dirs["bundles_dir"])
        if bundle is None:
            abort(404)
        brief = data.latest_brief_for_bundle(bundle_id, dirs["briefs_dir"])
        return render_template(
            "approval_detail.html", bundle=bundle, brief=brief, error=None,
            bundle_json=json.dumps(bundle, indent=2),
        )

    @app.route("/approvals/<bundle_id>/decide", methods=["POST"])
    def approval_decide(bundle_id: str):
        dirs = _dirs()
        choice = request.form.get("choice", "")
        note = request.form.get("note", "")
        actor = g.get("identity") or "unknown"

        try:
            actions.record_decision(
                bundle_id, choice=choice, actor=actor, note=note,
                bundles_dir=dirs["bundles_dir"], audit_path=dirs["audit_path"],
            )
        except actions.BundleNotFoundError:
            abort(404)
        except (actions.InvalidDecisionError, actions.AlreadyDecidedError) as exc:
            bundle = data.load_bundle(bundle_id, bundles_dir=dirs["bundles_dir"])
            brief = data.latest_brief_for_bundle(bundle_id, dirs["briefs_dir"])
            return render_template(
                "approval_detail.html", bundle=bundle, brief=brief, error=str(exc),
                bundle_json=json.dumps(bundle, indent=2) if bundle else "{}",
            ), 400

        return redirect(url_for("bundle_detail", bundle_id=bundle_id))

    # ----------------------------------------------------------------- #
    # Workers -- read-only, no control actions
    # ----------------------------------------------------------------- #

    @app.route("/workers")
    def workers():
        dirs = _dirs()
        worker_list = data.list_workers(
            registry_path=dirs["registry_path"], evidence_path=dirs["evidence_path"]
        )
        return render_template("workers.html", workers=worker_list)

    # ----------------------------------------------------------------- #
    # Audit
    # ----------------------------------------------------------------- #

    @app.route("/audit")
    def audit():
        entries = data.tail_audit(audit_path=_dirs()["audit_path"], limit=200)
        return render_template("audit.html", entries=entries)

    # ----------------------------------------------------------------- #
    # Error handlers
    # ----------------------------------------------------------------- #

    @app.errorhandler(403)
    def forbidden(_exc):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_exc):
        return render_template("404.html"), 404

    return app
