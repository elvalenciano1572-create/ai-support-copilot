import json

from support_copilot.kb import search_knowledge_base
from support_copilot.llm import LLMClient, clean_json_response
from support_copilot.models import (
    ResolutionAction,
    ResolutionResult,
    TicketCategory,
    TriagedTicket,
)


class SupportCopilotEngine:
    def __init__(self, llm: LLMClient, copilot_mode: bool = True):
        self.llm = llm
        self.copilot_mode = copilot_mode

    def resolve(self, triaged: TriagedTicket) -> ResolutionResult:
        ticket = triaged.ticket

        # 1. Spam drop
        if triaged.category == TicketCategory.SPAM:
            return ResolutionResult(
                ticket_id=ticket.ticket_id,
                action=ResolutionAction.SPAM_DROP,
                confidence_score=1.0,
                grounded_articles=[],
                drafted_response=None,
                internal_agent_notes="Automated spam filter triggered; inquiry dropped without escalation.",
                reason_for_escalation=None,
            )

        # 2. Knowledge Base Search
        query = f"{ticket.subject} {ticket.message}"
        matches = search_knowledge_base(query)

        best_article = matches[0][0] if matches else None
        confidence = matches[0][1] if matches else 0.0
        grounded_ids = [m[0].article_id for m in matches]

        # 3. Decision threshold logic
        if confidence < 0.40 or not best_article:
            return ResolutionResult(
                ticket_id=ticket.ticket_id,
                action=ResolutionAction.HUMAN_ESCALATION,
                confidence_score=round(confidence, 3),
                grounded_articles=grounded_ids,
                drafted_response=None,
                internal_agent_notes=(
                    f"Low confidence ({confidence:.1%}). No authoritative policy covers this request. "
                    "Escalating to human agent to prevent hallucination."
                ),
                reason_for_escalation="Zero matching knowledge base articles with sufficient confidence.",
            )

        # 4. Generate grounded response using LLM
        system_prompt = (
            "You are an expert AI Customer Support Copilot. Your job is to draft a polite, helpful, "
            "and accurate response strictly based on the provided Knowledge Base context. "
            "If the answer is not supported by the context, refuse to guess. "
            "Always return strictly valid JSON matching this schema:\n"
            "{\n"
            '  "response_text": "string customer response",\n'
            '  "internal_notes": "string agent reasoning"\n'
            "}"
        )
        user_prompt = (
            f"Customer Name: {ticket.customer_name}\n"
            f"Customer Subject: {ticket.subject}\n"
            f"Customer Message: {ticket.message}\n"
            f"Knowledge Base Context ({best_article.article_id}: {best_article.title}):\n"
            f"{best_article.content}\n"
            f"Policy URL: {best_article.policy_url}\n"
        )

        raw = self.llm.complete(system_prompt, user_prompt)
        cleaned = clean_json_response(raw)

        try:
            parsed = json.loads(cleaned)
            draft_text = parsed.get("response_text", "")
            notes = parsed.get("internal_notes", f"Grounded in {best_article.article_id}.")
        except json.JSONDecodeError:
            draft_text = best_article.content
            notes = f"Fallback text from {best_article.article_id}."

        # 5. Copilot Mode vs Autonomous Resolution
        if confidence >= 0.85 and not self.copilot_mode:
            action = ResolutionAction.AUTONOMOUS_RESOLVE
        else:
            action = ResolutionAction.COPILOT_DRAFT

        return ResolutionResult(
            ticket_id=ticket.ticket_id,
            action=action,
            confidence_score=round(confidence, 3),
            grounded_articles=grounded_ids,
            drafted_response=draft_text,
            internal_agent_notes=notes,
            reason_for_escalation=None,
        )
