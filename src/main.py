"""AI Procurement OS — local CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from src.agency import Agency
from src.core.brain import Brain
from src.core.llm import LLMClient
from src.core.logger import PlatformLogger
from src.core.orchestrator import Orchestrator
from src.core.storage import Storage
from src.core.pipeline_engine import PipelineEngine
from src.saas import SaaSPlatform
from src.saas.demo_seed import collect_credentials, seed_demo_data
from src.saas.credentials_doc import generate_credentials_doc, generate_credentials_markdown
from src.saas.client_presentation import generate_client_presentation
from src.saas.marketing_pdf import generate_marketing_pdf
from src.saas.marketing_images import generate_marketing_images, generate_story_images


def get_platform():
    brain = Brain(PROJECT_ROOT)
    brain.load()
    logger = PlatformLogger(PROJECT_ROOT, brain.config)
    storage = Storage(brain.db_path(), brain.data_dir(), logger)
    storage.initialize(brain.config.get("agency", {}))
    llm = LLMClient(brain.config)
    orchestrator = Orchestrator(brain, llm, storage, logger)
    agency = Agency(brain.config.get("agency", {}))
    saas = SaaSPlatform(brain.config.get("saas", {}))
    return brain, logger, storage, llm, orchestrator, agency, saas


def cmd_status(_args: argparse.Namespace) -> None:
    brain, logger, storage, llm, _, agency, saas = get_platform()
    tenant_id = agency.tenant_id
    health = llm.health_check()

    print("\n=== AI Procurement OS ===\n")
    print(json.dumps(brain.summary(), indent=2))
    print("\n--- Agency ---")
    print(json.dumps(agency.summary(), indent=2))
    print("\n--- SaaS ---")
    print(json.dumps(saas.summary(), indent=2))
    print("\n--- LLM Health ---")
    print(json.dumps(health, indent=2))
    print("\n--- Data Stats ---")
    print(json.dumps(storage.stats(tenant_id), indent=2))
    print("\n--- Agents ---")
    for aid, agent in sorted(brain.agents.items(), key=lambda x: (0 if isinstance(x[1].stage, int) else 1, str(x[1].stage))):
        print(f"  [{agent.stage}] {aid}: {agent.name}")
    logger.info("Status check completed")


def cmd_pipeline(_args: argparse.Namespace) -> None:
    _, _, _, _, orchestrator, _, _ = get_platform()
    stages = orchestrator.list_pipeline()
    print("\n=== Pipeline: buyer_to_delivery ===\n")
    for i, s in enumerate(stages, 1):
        gate = f" [HUMAN: {s['human_gate']}]" if s.get("human_gate") else ""
        print(f"  {i:2}. {s['stage']} -> {s['agent']}{gate}")


def cmd_agents(_args: argparse.Namespace) -> None:
    brain, _, _, _, _, _, _ = get_platform()
    print("\n=== Registered Agents ===\n")
    for aid, agent in sorted(brain.agents.items(), key=lambda x: (0 if isinstance(x[1].stage, int) else 1, str(x[1].stage))):
        print(f"{aid}")
        print(f"  Name: {agent.name}")
        print(f"  Stage: {agent.stage}")
        print(f"  Prompt loaded: {'yes' if agent.prompt_text else 'no'}")
        print()


def cmd_run(args: argparse.Namespace) -> None:
    _, logger, _, _, orchestrator, _, _ = get_platform()
    user_input = args.input
    if args.input_file:
        user_input = Path(args.input_file).read_text(encoding="utf-8")
    if not user_input:
        print("Error: provide --input or --input-file")
        sys.exit(1)

    print(f"\nRunning agent: {args.agent}\n")
    result = orchestrator.run_agent(args.agent, user_input)
    print(json.dumps(result, indent=2, default=str))
    if result.get("status") == "error":
        logger.error("Agent run failed", agent=args.agent)
        sys.exit(1)


def cmd_gate(args: argparse.Namespace) -> None:
    _, _, _, _, orchestrator, _, _ = get_platform()
    info = orchestrator.check_human_gate(args.name)
    print(json.dumps(info, indent=2))


def cmd_execute(args: argparse.Namespace) -> None:
    brain, logger, storage, llm, orchestrator, agency, _ = get_platform()
    engine = PipelineEngine(
        brain, orchestrator, storage, logger, agency, llm, PROJECT_ROOT
    )
    print("\n=== FAST PIPELINE (live web data) ===\n")
    auto = not args.require_human_gates
    run_id = engine.start(auto_approve=auto)
    print(f"Run ID: {run_id}")
    if auto:
        import time
        while True:
            status = engine.get_status(run_id)
            if status.get("status") in ("completed", "failed"):
                break
            time.sleep(1)
        print("\n=== SUMMARY ===\n")
        print(json.dumps(status.get("summary") or status, indent=2, default=str))
        if status.get("status") == "failed":
            sys.exit(1)
    else:
        print("Pipeline paused at human gates. Open dashboard: python -m src.main dashboard")


def cmd_seed_demo(_args: argparse.Namespace) -> None:
    brain, _, storage, _, _, agency, saas = get_platform()
    saas.bind(storage, brain.config.get("agency", {}))
    result = seed_demo_data(storage, saas.tenants, brain.config.get("agency", {}), force_orders=_args.force)
    print("\n=== Demo data seeded ===\n")
    print(json.dumps(result, indent=2))


def cmd_credentials(args: argparse.Namespace) -> None:
    brain, _, storage, _, _, agency, _ = get_platform()
    cfg = brain.config
    dash = cfg.get("dashboard", {})
    creds = collect_credentials(
        storage,
        cfg.get("agency", {}),
        cfg,
        host=args.host or dash.get("host", "127.0.0.1"),
        port=args.port or dash.get("port", 8765),
    )
    out = PROJECT_ROOT / "docs" / "PLATFORM_CREDENTIALS.docx"
    md_out = PROJECT_ROOT / "docs" / "PLATFORM_CREDENTIALS.md"
    generate_credentials_doc(creds, out)
    generate_credentials_markdown(creds, md_out)
    print(f"\nCredentials documents written to:")
    print(f"  {out}")
    print(f"  {md_out}\n")
    print("Super admin:", creds["platform_admin"]["email"], "/", creds["platform_admin"]["password"])
    print("Landing:", creds["platform"].get("landing_url", ""))
    print("CRM:", creds["platform"].get("dashboard_url", ""))


def cmd_presentation(args: argparse.Namespace) -> None:
    brain, _, storage, _, _, _, _ = get_platform()
    cfg = brain.config
    dash = cfg.get("dashboard", {})
    creds = collect_credentials(
        storage,
        cfg.get("agency", {}),
        cfg,
        host=args.host or dash.get("host", "127.0.0.1"),
        port=args.port or dash.get("port", 8765),
    )
    out = PROJECT_ROOT / "docs" / "CLIENT_PRESENTATION.pdf"
    generate_client_presentation(creds, out)
    print(f"\nClient presentation written to:\n  {out}\n")


def cmd_marketing_kit(args: argparse.Namespace) -> None:
    marketing_dir = PROJECT_ROOT / "docs" / "marketing"
    pdf_out = marketing_dir / "TEAM-GUIDE.pdf"
    images_dir = marketing_dir / "images"
    old_pdf = marketing_dir / "MARKETING-KIT.pdf"

    generate_marketing_pdf(marketing_dir, pdf_out)
    if old_pdf.exists():
        old_pdf.unlink()
    print(f"\nTeam guide PDF:\n  {pdf_out}\n")

    if not args.pdf_only:
        posts = generate_marketing_images(images_dir)
        stories = generate_story_images(images_dir)
        for p in posts + stories:
            print(f"  {p}")
        print()


def cmd_test_email(_args: argparse.Namespace) -> None:
    """Send a test pilot-form notification to CONTACT_EMAIL."""
    import os
    from datetime import datetime, timezone

    from src.core.email import EmailService
    from src.core.notifications import admin_email, notify_demo_request

    svc = EmailService()
    to = admin_email()
    print("\n=== Email test ===\n")
    print(f"  To:      {to}")
    print(f"  SMTP:    {svc.smtp_host or '(not set)'}")
    print(f"  User:    {svc.smtp_user or '(not set)'}")
    print(f"  Pass:    {'SET' if svc.smtp_pass else 'MISSING — add SMTP_PASS to .env'}")
    print(f"  Resend:  {'SET' if os.getenv('RESEND_API_KEY') else '(not set)'}")
    print(f"  Dry run: {svc.dry_run}\n")

    if not svc.smtp_pass and not os.getenv("RESEND_API_KEY"):
        print("Cannot send — add SMTP_PASS to .env (Gmail App Password) or RESEND_API_KEY")
        print("  https://myaccount.google.com/apppasswords\n")
        sys.exit(1)

    result = notify_demo_request({
        "name": "Local Test User",
        "email": "test@example.com",
        "company": "Local Test Co",
        "message": "Test pilot form — drinkware",
        "source": "test-email-cli",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    print(json.dumps(result, indent=2))
    if result.get("status") == "sent":
        print(f"\nSuccess — check inbox: {to}\n")
        return
    err = result.get("error", "")
    if "Application-specific password" in str(err) or "5.7.9" in str(err):
        print("\nGmail rejected the password — use an App Password, NOT your regular Gmail password:")
        print("  1. Enable 2-Step Verification on the Google account")
        print("  2. Create App Password: https://myaccount.google.com/apppasswords")
        print("  3. Put the 16-character code in .env as SMTP_PASS (no spaces)")
        print("  4. Set EMAIL_DRY_RUN=false\n")
    elif result.get("status") != "sent":
        print("\nEmail was NOT delivered. Check SMTP_PASS and Gmail app password settings.\n")
    sys.exit(1)


def cmd_dashboard(args: argparse.Namespace) -> None:
    import os
    import uvicorn

    brain = Brain(PROJECT_ROOT)
    brain.load()
    cfg = brain.config.get("dashboard", {})
    host = args.host or os.getenv("DASHBOARD_HOST") or os.getenv("HOST") or cfg.get("host", "127.0.0.1")
    port = args.port
    if port is None:
        port = int(os.getenv("PORT") or os.getenv("DASHBOARD_PORT") or cfg.get("port", 8765))
    print(f"\n  Dashboard: http://{host}:{port}\n")
    uvicorn.run("src.api.server:app", host=host, port=port, reload=False)


def cmd_reset(args: argparse.Namespace) -> None:
    _, _, storage, _, _, agency, _ = get_platform()
    result = storage.reset_workspace(agency.tenant_id, include_suppliers=args.include_suppliers)
    print("\n=== Workspace reset ===\n")
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Procurement OS — local platform")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Platform health and stats")
    sub.add_parser("pipeline", help="Show sourcing pipeline stages")
    sub.add_parser("agents", help="List all agents")

    run_p = sub.add_parser("run", help="Run a single agent")
    run_p.add_argument("agent", help="Agent ID (e.g. qualification)")
    run_p.add_argument("--input", "-i", help="Input text for the agent")
    run_p.add_argument("--input-file", "-f", help="Input file path")

    gate_p = sub.add_parser("gate", help="Check human approval gate")
    gate_p.add_argument("name", help="Gate name (e.g. proposal_send)")

    exec_p = sub.add_parser("execute", help="Run full pipeline with live web search (real data)")
    exec_p.add_argument(
        "--require-human-gates",
        action="store_true",
        help="Pause at human approval gates (use dashboard to approve)",
    )

    dash_p = sub.add_parser("dashboard", help="Launch web dashboard")
    dash_p.add_argument("--host", default=None)
    dash_p.add_argument("--port", type=int, default=None)

    reset_p = sub.add_parser("reset", help="Delete all leads and deals for a fresh start")
    reset_p.add_argument(
        "--include-suppliers",
        action="store_true",
        help="Also delete all suppliers",
    )

    seed_p = sub.add_parser("seed-demo", help="Seed demo tenants, users, and sample store orders")
    seed_p.add_argument("--force", action="store_true", help="Re-create demo store orders")

    cred_p = sub.add_parser("credentials", help="Generate PLATFORM_CREDENTIALS.docx")
    cred_p.add_argument("--host", default=None)
    cred_p.add_argument("--port", type=int, default=None)

    pres_p = sub.add_parser("presentation", help="Generate CLIENT_PRESENTATION.pdf")
    pres_p.add_argument("--host", default=None)
    pres_p.add_argument("--port", type=int, default=None)

    mkt_p = sub.add_parser("marketing-kit", help="Generate TEAM-GUIDE.pdf and social post images")
    mkt_p.add_argument("--pdf-only", action="store_true", help="Skip image generation")

    sub.add_parser("test-email", help="Send test pilot-form notification to CONTACT_EMAIL")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "status": cmd_status,
        "pipeline": cmd_pipeline,
        "agents": cmd_agents,
        "run": cmd_run,
        "gate": cmd_gate,
        "execute": cmd_execute,
        "dashboard": cmd_dashboard,
        "reset": cmd_reset,
        "seed-demo": cmd_seed_demo,
        "credentials": cmd_credentials,
        "presentation": cmd_presentation,
        "marketing-kit": cmd_marketing_kit,
        "test-email": cmd_test_email,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
