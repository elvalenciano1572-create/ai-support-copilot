import io
import json
import urllib.error

import pytest

from support_copilot.cli import main
from support_copilot.kb import get_default_knowledge_base, search_knowledge_base, tokenize
from support_copilot.llm import (
    GeminiLLM,
    LLMError,
    MockLLM,
    OpenAILLM,
    clean_json_response,
    get_llm_client,
)
from support_copilot.models import (
    CustomerSentiment,
    ResolutionAction,
    SupportTicket,
    TicketCategory,
    TicketUrgency,
)
from support_copilot.resolver import SupportCopilotEngine
from support_copilot.triager import triage_ticket


def test_models_validation():
    ticket = SupportTicket(
        ticket_id="T-1",
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        subject="Help needed",
        message="Cannot access my dashboard",
    )
    assert ticket.ticket_id == "T-1"
    assert ticket.customer_email == "jane@example.com"


def test_kb_search_ranking():
    kb = get_default_knowledge_base()
    assert len(kb) >= 4

    # Refund query should rank KB-001 at the top
    results = search_knowledge_base("I would like a refund for my billing charge", kb=kb)
    assert len(results) > 0
    assert results[0][0].article_id == "KB-001"
    assert results[0][1] > 0.50

    # Rate limit query should rank KB-002
    rate_results = search_knowledge_base("receiving http 429 rate limit exceeded", kb=kb)
    assert rate_results[0][0].article_id == "KB-002"

    # Stopwords filter works
    tokens = tokenize("What is the refund policy for our account?")
    assert "the" not in tokens
    assert "refund" in tokens


def test_triager_classifications():
    # 1. Spam
    spam_ticket = SupportTicket(
        ticket_id="S-1",
        customer_name="Spam Bot",
        customer_email="bot@casino.xyz",
        subject="Earn crypto profit at our casino",
        message="Claim bonus now",
    )
    triaged_spam = triage_ticket(spam_ticket)
    assert triaged_spam.category == TicketCategory.SPAM

    # 2. Angry / Critical
    angry_ticket = SupportTicket(
        ticket_id="A-1",
        customer_name="Angry User",
        customer_email="vip@fintech-corp.io",
        subject="Production down! Unacceptable service, calling my lawyer",
        message="Your API broke our trading system. Fix this immediately or we cancel.",
    )
    triaged_angry = triage_ticket(angry_ticket)
    assert triaged_angry.sentiment == CustomerSentiment.ANGRY
    assert triaged_angry.urgency == TicketUrgency.CRITICAL
    assert triaged_angry.is_vip is True
    assert triaged_angry.category == TicketCategory.TECHNICAL_INTEGRATION


def test_resolver_copilot_mode():
    llm = MockLLM()
    engine = SupportCopilotEngine(llm, copilot_mode=True)

    ticket = SupportTicket(
        ticket_id="T-REFUND",
        customer_name="John Smith",
        customer_email="john@example.com",
        subject="Refund inquiry for annual billing",
        message="Can I cancel and request a refund within 14 days?",
    )
    triaged = triage_ticket(ticket)
    result = engine.resolve(triaged)

    assert result.action == ResolutionAction.COPILOT_DRAFT
    assert result.confidence_score > 0.60
    assert "KB-001" in result.grounded_articles
    assert "14 calendar days" in (result.drafted_response or "")
    assert result.reason_for_escalation is None


def test_resolver_autonomous_mode():
    llm = MockLLM()
    engine = SupportCopilotEngine(llm, copilot_mode=False)

    ticket = SupportTicket(
        ticket_id="T-429",
        customer_name="Developer",
        customer_email="dev@acme.com",
        subject="HTTP 429 rate limit backoff header",
        message="How to handle 429 rate limit errors with exponential backoff on Pro tier?",
    )
    triaged = triage_ticket(ticket)
    result = engine.resolve(triaged)

    # High confidence (>=0.85) in non-copilot mode resolves autonomously
    assert result.action == ResolutionAction.AUTONOMOUS_RESOLVE
    assert result.confidence_score >= 0.85
    assert "KB-002" in result.grounded_articles


def test_resolver_human_escalation_for_uncovered_inquiry():
    llm = MockLLM()
    engine = SupportCopilotEngine(llm, copilot_mode=True)

    # Obscure inquiry completely outside KB
    ticket = SupportTicket(
        ticket_id="T-UNKNOWN",
        customer_name="Hospital Director",
        customer_email="director@medclinic.org",
        subject="HIPAA Business Associate Agreement and on-premise Kubernetes deployment",
        message=(
            "We need a signed BAA and a self-hosted on-prem air-gapped installation of your core cluster."
        ),
    )
    triaged = triage_ticket(ticket)
    result = engine.resolve(triaged)

    assert result.action == ResolutionAction.HUMAN_ESCALATION
    assert result.drafted_response is None
    assert result.reason_for_escalation is not None
    assert "Escalating to human agent to prevent hallucination" in result.internal_agent_notes


def test_clean_json_response():
    assert clean_json_response('{"status": "ok"}') == '{"status": "ok"}'
    assert clean_json_response('```json\n{"status": "ok"}\n```') == '{"status": "ok"}'


def test_gemini_client_mock(monkeypatch):
    canned = {
        "candidates": [
            {"content": {"parts": [{"text": '{"response_text": "hello", "internal_notes": "ok"}'}]}}
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps(canned).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: FakeResponse())

    client = GeminiLLM(api_key="dummy")
    resp = json.loads(client.complete("sys", "user"))
    assert resp["response_text"] == "hello"


def test_gemini_client_http_error(monkeypatch):
    def fake_error(req, timeout):
        fp = io.BytesIO(b'{"error": "Unauthorized"}')
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, fp)

    monkeypatch.setattr("urllib.request.urlopen", fake_error)
    client = GeminiLLM(api_key="bad")
    with pytest.raises(LLMError, match="Gemini API HTTP 401"):
        client.complete("sys", "user")


def test_openai_client_mock(monkeypatch):
    canned = {"choices": [{"message": {"content": '{"response_text": "hi"}'}}]}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps(canned).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: FakeResponse())

    client = OpenAILLM(api_key="dummy")
    resp = json.loads(client.complete("sys", "user"))
    assert resp["response_text"] == "hi"


def test_get_llm_client_resolution(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Defaults to MockLLM
    assert isinstance(get_llm_client(), MockLLM)

    # Gemini with key
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert isinstance(get_llm_client(), GeminiLLM)

    # Missing key raises clean error
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(LLMError, match="GEMINI_API_KEY is required"):
        get_llm_client()


def test_cli_execution(capsys):
    exit_code = main(["--copilot-mode"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "AI CUSTOMER SUPPORT COPILOT" in captured.out
    assert "TICK-101" in captured.out
    assert "RESOLUTION SUMMARY" in captured.out


def test_cli_missing_key_clean_exit(capsys, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    exit_code = main(["--provider", "gemini"])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "GEMINI_API_KEY is required" in captured.err
