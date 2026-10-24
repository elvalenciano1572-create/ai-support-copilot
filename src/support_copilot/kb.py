import math
import re

from support_copilot.models import KnowledgeArticle, TicketCategory

STOPWORDS = frozenset(
    {
        "the", "and", "for", "what", "are", "with", "that", "this", "from", "have",
        "has", "must", "how", "does", "can", "you", "your", "our", "all", "any",
        "per", "within", "after", "which", "about", "could", "would", "should",
    }
)


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", text.lower())) - STOPWORDS


def get_default_knowledge_base() -> list[KnowledgeArticle]:
    return [
        KnowledgeArticle(
            article_id="KB-001",
            title="Standard Refund Policy & 14-Day Window",
            category=TicketCategory.BILLING_REFUND,
            keywords=["refund", "money", "back", "cancel", "chargeback", "billing", "return"],
            content=(
                "Customers are eligible for a full refund within 14 calendar days of purchase if account "
                "API usage has not exceeded 100 requests. Refunds are automatically processed back to the "
                "original payment method (Stripe/Card) within 3-5 business days. Enterprise annual contracts "
                "are governed by individual master service agreement terms."
            ),
            policy_url="https://help.acme.io/policies/refunds",
        ),
        KnowledgeArticle(
            article_id="KB-002",
            title="API Rate Limits & HTTP 429 Backoff Strategies",
            category=TicketCategory.TECHNICAL_INTEGRATION,
            keywords=["rate", "limit", "429", "throttled", "quota", "concurrency", "http", "api"],
            content=(
                "The Basic tier permits up to 60 requests/minute. The Pro tier allows 600 req/min. "
                "If your application receives HTTP 429 Too Many Requests, inspect the 'Retry-After' "
                "response header and apply exponential backoff with jitter. Contact sales to request "
                "custom enterprise burst quotas."
            ),
            policy_url="https://docs.acme.io/api/rate-limits",
        ),
        KnowledgeArticle(
            article_id="KB-003",
            title="Two-Factor Authentication (2FA) Reset Protocol",
            category=TicketCategory.ACCOUNT_SECURITY,
            keywords=["2fa", "two-factor", "authenticator", "lost", "phone", "reset", "login", "locked"],
            content=(
                "For customer security, support agents cannot manually disable Two-Factor "
                "Authentication over email or chat. Users must use their emergency 16-character backup "
                "recovery codes generated during setup. If backup codes are lost, the user must initiate "
                "the automated Identity Verification link at https://app.acme.io/auth/recovery."
            ),
            policy_url="https://help.acme.io/security/2fa-recovery",
        ),
        KnowledgeArticle(
            article_id="KB-004",
            title="Subscription Upgrades & Prorated Billing",
            category=TicketCategory.BILLING_REFUND,
            keywords=["upgrade", "downgrade", "subscription", "plan", "prorated", "invoice", "tier"],
            content=(
                "Upgrading your subscription tier takes effect immediately. The remaining unused days on "
                "your current billing cycle are credited toward the new tier, resulting in a prorated "
                "charge on your next monthly invoice. Downgrades take effect at the conclusion of the "
                "current prepaid billing period."
            ),
            policy_url="https://help.acme.io/billing/tier-changes",
        ),
    ]


def search_knowledge_base(
    query: str, kb: list[KnowledgeArticle] | None = None, top_k: int = 3
) -> list[tuple[KnowledgeArticle, float]]:
    articles = kb if kb is not None else get_default_knowledge_base()
    q_tokens = tokenize(query)
    if not q_tokens:
        return []

    scored: list[tuple[KnowledgeArticle, float]] = []
    for art in articles:
        content_tokens = tokenize(f"{art.title} {art.content}")
        keyword_tokens = {k.lower() for k in art.keywords}

        direct_matches = q_tokens.intersection(content_tokens)
        kw_matches = q_tokens.intersection(keyword_tokens)

        # Base token overlap (cosine similarity of sets)
        token_sim = len(direct_matches) / (math.sqrt(len(q_tokens)) * math.sqrt(max(1, len(content_tokens))))

        # Keyword boost
        kw_boost = min(0.5, len(kw_matches) * 0.20)

        final_score = min(1.0, (token_sim * 1.8) + kw_boost)
        if final_score > 0.05:
            scored.append((art, round(final_score, 3)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
