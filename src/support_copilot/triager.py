import re

from support_copilot.models import (
    CustomerSentiment,
    SupportTicket,
    TicketCategory,
    TicketUrgency,
    TriagedTicket,
)


def triage_ticket(ticket: SupportTicket) -> TriagedTicket:
    text = f"{ticket.subject} {ticket.message}".lower()

    # 1. Spam detection
    spam_markers = ["casino", "crypto profit", "viagra", "backlinks", "seo ranking", "dear friend"]
    if any(m in text for m in spam_markers):
        return TriagedTicket(
            ticket=ticket,
            category=TicketCategory.SPAM,
            urgency=TicketUrgency.LOW,
            sentiment=CustomerSentiment.NEUTRAL,
            is_vip=False,
            key_entities=[],
        )

    # 2. Sentiment analysis
    angry_markers = ["sue", "lawyer", "unacceptable", "scam", "fraud", "furious", "cancel immediately"]
    frustrated_markers = ["broken", "stuck", "waiting", "annoying", "disappointed", "failed again", "blocked"]
    satisfied_markers = ["thank you", "great service", "appreciate", "love your product", "kudos"]

    if any(m in text for m in angry_markers):
        sentiment = CustomerSentiment.ANGRY
    elif any(m in text for m in frustrated_markers):
        sentiment = CustomerSentiment.FRUSTRATED
    elif any(m in text for m in satisfied_markers):
        sentiment = CustomerSentiment.SATISFIED
    else:
        sentiment = CustomerSentiment.NEUTRAL

    # 3. Category classification
    billing_kw = ["refund", "charge", "invoice", "payment", "billing", "subscription", "upgrade"]
    tech_kw = ["api", "429", "rate limit", "webhook", "endpoint", "sdk", "timeout", "json"]
    security_kw = ["2fa", "two-factor", "password", "locked out", "login", "authenticator", "hack"]

    if any(k in text for k in billing_kw):
        category = TicketCategory.BILLING_REFUND
    elif any(k in text for k in tech_kw):
        category = TicketCategory.TECHNICAL_INTEGRATION
    elif any(k in text for k in security_kw):
        category = TicketCategory.ACCOUNT_SECURITY
    else:
        category = TicketCategory.PRODUCT_INQUIRY

    # 4. Urgency evaluation
    critical_markers = ["production down", "system down", "locked out", "emergency", "urgent", "immediately"]
    if any(m in text for m in critical_markers) or sentiment == CustomerSentiment.ANGRY:
        urgency = TicketUrgency.CRITICAL
    elif category in {TicketCategory.ACCOUNT_SECURITY, TicketCategory.TECHNICAL_INTEGRATION}:
        urgency = TicketUrgency.HIGH
    elif sentiment == CustomerSentiment.FRUSTRATED:
        urgency = TicketUrgency.MEDIUM
    else:
        urgency = TicketUrgency.LOW

    # 5. VIP flag
    vip_domains = ["@enterprise.com", "@fintech-corp.io", "@acme-partner.com"]
    is_vip = any(ticket.customer_email.lower().endswith(d) for d in vip_domains)

    # 6. Entity extraction (error codes, HTTP status, IDs)
    entities = []
    codes = re.findall(r"\b(?:http\s*)?(?:4\d{2}|5\d{2})\b", text)
    if codes:
        entities.extend([f"HTTP_{c.strip()}" for c in codes])
    kb_refs = re.findall(r"\bkb-\d{3}\b", text)
    if kb_refs:
        entities.extend([k.upper() for k in kb_refs])

    return TriagedTicket(
        ticket=ticket,
        category=category,
        urgency=urgency,
        sentiment=sentiment,
        is_vip=is_vip,
        key_entities=entities,
    )
