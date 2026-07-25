"""CLI for Cognisphere Learning Plugins (DT-P1…P6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
import typer

console = Console()


def register(app: typer.Typer) -> None:
    @app.command("list")
    def cognisphere_list(
        root: Optional[Path] = typer.Option(
            None,
            "--root",
            help="Override COGNISPHERE_LEARNING_PLUGINS_ROOT",
        ),
    ) -> None:
        """Discover domain learning plugins from the Cognisphere plugins monorepo."""
        from cognispheretutor.integrations.cognisphere import list_plugins

        result = list_plugins(root)
        table = Table(title="Cognisphere Learning Plugins")
        table.add_column("Domain", style="bold")
        table.add_column("Plugin ID")
        table.add_column("Lifecycle")
        table.add_column("Capabilities")
        table.add_column("Valid")

        for item in result.get("plugins") or []:
            manifest = item.get("manifest") or {}
            caps = ", ".join(manifest.get("capabilities") or [])
            table.add_row(
                str(item.get("domain")),
                str(manifest.get("plugin_id") or ""),
                str(item.get("lifecycle") or ""),
                caps[:60],
                "yes" if (item.get("validation") or {}).get("ok") else "no",
            )

        console.print(table)
        console.print(f"plugins_root: {result.get('plugins_root')}")
        if result.get("issues"):
            console.print(f"[yellow]issues:[/] {result['issues']}")
        if not result.get("ok"):
            raise typer.Exit(code=1)

    @app.command("negotiate")
    def cognisphere_negotiate(
        domain: str = typer.Argument(..., help="Domain id, e.g. leetcode"),
        capability: list[str] = typer.Option(
            ["deeptutor_export"],
            "--capability",
            "-c",
            help="Required capability (repeatable).",
        ),
        goal: str = typer.Option("", "--goal", help="Optional negotiation goal."),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Negotiate capabilities against a domain plugin."""
        from cognispheretutor.integrations.cognisphere import negotiate

        result = negotiate(
            domain,
            {"required_capabilities": list(capability), "goal": goal or None},
            root=root,
        )
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("matched"):
            raise typer.Exit(code=1)

    @app.command("validate")
    def cognisphere_validate(
        domain: str = typer.Argument(..., help="Domain id, e.g. leetcode"),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Run plugin validate_adapter and print structured issues."""
        from cognispheretutor.integrations.cognisphere import validate_adapter

        result = validate_adapter(domain, root=root)
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise typer.Exit(code=1)

    @app.command("import")
    def cognisphere_import(
        domain: str = typer.Argument(..., help="Domain id, e.g. leetcode"),
        root: Optional[Path] = typer.Option(None, "--root"),
        cache_dir: Optional[Path] = typer.Option(
            None,
            "--cache-dir",
            help="Override COGNISPHERE_IMPORT_CACHE_DIR / workspace cache",
        ),
        no_persist: bool = typer.Option(
            False,
            "--no-persist",
            help="Validate and map without writing import artifacts",
        ),
    ) -> None:
        """Export domain package via plugin entrypoint and import into learning loop."""
        from cognispheretutor.integrations.cognisphere import export_and_import
        from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

        options: dict = {"persist": not no_persist}
        if cache_dir is not None:
            options["cache_dir"] = cache_dir
        try:
            result = export_and_import(domain, options, root=root)
        except CognisphereIntegrationError as exc:
            console.print_json(json.dumps(exc.to_dict(), indent=2, ensure_ascii=False))
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise typer.Exit(code=1)

    @app.command("import-bundle")
    def cognisphere_import_bundle(
        path: Path = typer.Argument(..., help="Path to a handoff bundle JSON file"),
        cache_dir: Optional[Path] = typer.Option(None, "--cache-dir"),
        no_persist: bool = typer.Option(False, "--no-persist"),
    ) -> None:
        """Import an on-disk cognisphereTutor handoff bundle JSON."""
        from cognispheretutor.integrations.cognisphere import import_bundle_json
        from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

        bundle = json.loads(path.read_text(encoding="utf-8"))
        try:
            result = import_bundle_json(
                bundle,
                persist=not no_persist,
                cache_dir=cache_dir,
            )
        except CognisphereIntegrationError as exc:
            console.print_json(json.dumps(exc.to_dict(), indent=2, ensure_ascii=False))
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))

    @app.command("compose")
    def cognisphere_compose(
        domain: list[str] = typer.Option([], "--domain", "-d", help="Domain to include"),
        capability: list[str] = typer.Option(
            [],
            "--capability",
            "-c",
            help="Required capability filter",
        ),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Compose cross-domain learning contexts (DT-P6)."""
        from cognispheretutor.integrations.cognisphere import compose_contexts

        result = compose_contexts(
            list(domain) or None,
            required_capabilities=list(capability) or None,
            root=root,
        )
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise typer.Exit(code=1)

    @app.command("cross-domain")
    def cognisphere_cross_domain(
        capability: list[str] = typer.Option(
            [],
            "--capability",
            "-c",
            help="Required capability (repeatable)",
        ),
        goal: str = typer.Option("", "--goal"),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Query plugins matching required capabilities across domains."""
        from cognispheretutor.integrations.cognisphere import query_cross_domain

        result = query_cross_domain(
            {"required_capabilities": list(capability), "goal": goal or None},
            root=root,
        )
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("match_count", 0) == 0 and capability:
            raise typer.Exit(code=1)

    @app.command("tutor-start")
    def cognisphere_tutor_start(
        domain: str = typer.Option(
            ...,
            "--domain",
            "-d",
            help="Domain id from plugin discovery (required; no default)",
        ),
        slug: str = typer.Argument(
            ...,
            help="Problem / item slug (example for leetcode fixture: two-sum)",
        ),
        hint_level: int = typer.Option(0, "--hint-level", min=0, max=4),
        root: Optional[Path] = typer.Option(None, "--root"),
        no_persist: bool = typer.Option(False, "--no-persist"),
    ) -> None:
        """Start offline Socratic tutor session (DT-P4 → plugin P2)."""
        from cognispheretutor.integrations.cognisphere import start_tutor_session
        from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

        try:
            result = start_tutor_session(
                slug,
                domain=domain,
                hint_level=hint_level,
                root=root,
                persist=not no_persist,
            )
        except CognisphereIntegrationError as exc:
            console.print_json(json.dumps(exc.to_dict(), indent=2, ensure_ascii=False))
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise typer.Exit(code=1)

    @app.command("tutor-advance")
    def cognisphere_tutor_advance(
        session_file: Path = typer.Argument(..., help="Path to a saved Socratic session JSON"),
        domain: Optional[str] = typer.Option(
            None,
            "--domain",
            "-d",
            help="Domain id (required if session JSON has no domain field)",
        ),
        event: str = typer.Option("advance", "--event"),
        checkpoint: Optional[str] = typer.Option(None, "--checkpoint"),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Advance an offline Socratic tutor session (DT-P4)."""
        from cognispheretutor.integrations.cognisphere import advance_tutor_session
        from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

        session = json.loads(session_file.read_text(encoding="utf-8"))
        try:
            result = advance_tutor_session(
                session,
                domain=domain or session.get("domain"),
                event=event,
                checkpoint=checkpoint,
                root=root,
            )
        except CognisphereIntegrationError as exc:
            console.print_json(json.dumps(exc.to_dict(), indent=2, ensure_ascii=False))
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))

    @app.command("sandbox-verify")
    def cognisphere_sandbox_verify(
        domain: str = typer.Option(
            ...,
            "--domain",
            "-d",
            help="Domain id from plugin discovery (required; no default)",
        ),
        outcome: str = typer.Option(
            "WA",
            "--outcome",
            help="Offline simulated sandbox outcome (AC/WA/RE/TLE/CE)",
        ),
        slug: str = typer.Option(
            ...,
            "--slug",
            help="Problem / item slug (example for leetcode fixture: two-sum)",
        ),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Analyze an offline sandbox outcome and ingest (DT-P4/P5)."""
        from cognispheretutor.integrations.cognisphere import verify_submission
        from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

        try:
            result = verify_submission(
                domain=domain,
                slug=slug,
                offline_simulated=True,
                outcome={"outcome": outcome, "problem_slug": slug},
                root=root,
            )
        except CognisphereIntegrationError as exc:
            console.print_json(json.dumps(exc.to_dict(), indent=2, ensure_ascii=False))
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))

    @app.command("suggest-focus")
    def cognisphere_suggest_focus(
        domain: str = typer.Option(
            ...,
            "--domain",
            "-d",
            help="Domain id from plugin discovery (required; no default)",
        ),
        slug: Optional[str] = typer.Option(None, "--slug"),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Suggest next tutor focus from mistake memory (DT-P5)."""
        from cognispheretutor.integrations.cognisphere import suggest_tutor_focus
        from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

        try:
            result = suggest_tutor_focus(domain=domain, problem_slug=slug, root=root)
        except CognisphereIntegrationError as exc:
            console.print_json(json.dumps(exc.to_dict(), indent=2, ensure_ascii=False))
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))

    @app.command("plan-path")
    def cognisphere_plan_path(
        domain: str = typer.Option(
            ...,
            "--domain",
            "-d",
            help="Domain id from plugin discovery (required; no default)",
        ),
        learner_id: str = typer.Option("offline-learner", "--learner-id"),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Plan next skill-graph learning path (DT-P5)."""
        from cognispheretutor.integrations.cognisphere import plan_skill_path
        from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

        try:
            result = plan_skill_path(domain=domain, learner_id=learner_id, root=root)
        except CognisphereIntegrationError as exc:
            console.print_json(json.dumps(exc.to_dict(), indent=2, ensure_ascii=False))
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))

    @app.command("interview")
    def cognisphere_interview(
        domain: str = typer.Option(
            ...,
            "--domain",
            "-d",
            help="Domain id from plugin discovery (required; no default)",
        ),
        case_id: Optional[str] = typer.Option(None, "--case-id"),
        learner_id: str = typer.Option("offline-learner", "--learner-id"),
        run_flow: bool = typer.Option(
            False,
            "--run-flow",
            help="Drive a full offline interview with default stage responses",
        ),
        root: Optional[Path] = typer.Option(None, "--root"),
    ) -> None:
        """Start or run offline interview/benchmark session (DT-P6)."""
        from cognispheretutor.integrations.cognisphere import run_interview_session
        from cognispheretutor.integrations.cognisphere.error_codes import CognisphereIntegrationError

        responses = (
            {
                "problem_presentation": {"text": "problem received"},
                "clarifying_questions": {"text": "clarify constraints"},
                "approach_discussion": {"text": "approach discussion"},
                "coding": {"text": "implemented solution"},
                "testing": {"text": "tests passed"},
                "complexity_analysis": {"text": "complexity analysis"},
                "final_review": {"summary": "done", "text": "tradeoff explain alternative"},
            }
            if run_flow
            else None
        )
        try:
            result = run_interview_session(
                domain=domain,
                case_id=case_id,
                learner_id=learner_id,
                responses=responses,
                root=root,
                persist=False,
            )
        except CognisphereIntegrationError as exc:
            console.print_json(json.dumps(exc.to_dict(), indent=2, ensure_ascii=False))
            raise typer.Exit(code=1) from exc
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise typer.Exit(code=1)
