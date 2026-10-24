import argparse
import sys

from support_copilot.llm import LLMError, get_llm_client
from support_copilot.models import ResolutionAction
from support_copilot.resolver import SupportCopilotEngine
from support_copilot.sample_tickets import get_sample_tickets
from support_copilot.triager import triage_ticket


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Autonomous AI Customer Support Copilot & Ticket Triaging Engine."
    )
    parser.add_argument(
        "--copilot-mode",
        action="store_true",
        default=True,
        help="Run in Copilot mode (drafts responses for 1-click human approval instead of auto-sending)",
    )
    parser.add_argument(
        "--autonomous",
        dest="copilot_mode",
        action="store_false",
        help="Run in Autopilot mode (auto-resolves high-confidence inquiries >= 85%% directly)",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "gemini", "openai"],
        default=None,
        help="LLM provider (default: auto-detected from env or 'mock')",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for Gemini/OpenAI (or set GEMINI_API_KEY / OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model override (e.g. gemini-1.5-flash, gpt-4o-mini)",
    )
    return parser


def format_ticket_output(triaged, result) -> str:
    sources_str = ", ".join(result.grounded_articles) or "None"
    t = triaged.ticket
    lines = [
        f"[{result.action.value}] Ticket: {t.ticket_id} | Customer: {t.customer_name}",
        f"    Email:     {triaged.ticket.customer_email} {'[VIP]' if triaged.is_vip else ''}",
        f"    Category:  {triaged.category.value} | Urgency: [{triaged.urgency.value}]",
        f"    Sentiment: {triaged.sentiment.value}",
        f"    Subject:   \"{triaged.ticket.subject}\"",
        f"    Confidence: {result.confidence_score:.1%} | Sources: {sources_str}",
    ]

    if result.action == ResolutionAction.SPAM_DROP:
        lines.append("    Outcome:   Spam inquiry silently discarded.")
    elif result.action == ResolutionAction.HUMAN_ESCALATION:
        lines.append(f"    Escalation: {result.reason_for_escalation}")
        lines.append(f"    Internal Notes: {result.internal_agent_notes}")
    else:
        lines.append(f"    Internal Notes: {result.internal_agent_notes}")
        lines.append("    Drafted Response:")
        for r_line in (result.drafted_response or "").splitlines():
            lines.append(f"      | {r_line}")

    return "\n".join(lines)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        client = get_llm_client(provider=args.provider, api_key=args.api_key, model=args.model)
    except LLMError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    provider_name = getattr(client, "__class__", type(client)).__name__
    mode_label = (
        "COPILOT (Drafts for Human Approval)"
        if args.copilot_mode
        else "AUTOPILOT (Direct Resolve >=85%)"
    )

    print("=" * 72)
    print("   AI CUSTOMER SUPPORT COPILOT: INTAKE & RESOLUTION PIPELINE")
    print("=" * 72)
    print(f"[*] Engine Active: {provider_name} | Mode: {mode_label}\n")

    tickets = get_sample_tickets()
    engine = SupportCopilotEngine(client, copilot_mode=args.copilot_mode)

    stats = {action: 0 for action in ResolutionAction}

    for ticket in tickets:
        triaged = triage_ticket(ticket)
        result = engine.resolve(triaged)
        stats[result.action] += 1
        print(format_ticket_output(triaged, result))
        print("-" * 72)

    print("\n[RESOLUTION SUMMARY]")
    print(f"  * Autonomous Resolutions: {stats[ResolutionAction.AUTONOMOUS_RESOLVE]}")
    print(f"  * Copilot Approved Drafts: {stats[ResolutionAction.COPILOT_DRAFT]}")
    print(f"  * Escalated to Human:      {stats[ResolutionAction.HUMAN_ESCALATION]}")
    print(f"  * Discarded Spam:          {stats[ResolutionAction.SPAM_DROP]}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
