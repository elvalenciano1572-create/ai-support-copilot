from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TicketUrgency(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketCategory(str, Enum):
    BILLING_REFUND = "Billing & Refund"
    TECHNICAL_INTEGRATION = "Technical & API Integration"
    ACCOUNT_SECURITY = "Account & Security"
    PRODUCT_INQUIRY = "Product & Features"
    SPAM = "Spam / Promotional"


class CustomerSentiment(str, Enum):
    SATISFIED = "Satisfied / Positive"
    NEUTRAL = "Neutral"
    FRUSTRATED = "Frustrated"
    ANGRY = "Angry / Churn Risk"


class ResolutionAction(str, Enum):
    AUTONOMOUS_RESOLVE = "AUTONOMOUS_RESOLVE"
    COPILOT_DRAFT = "COPILOT_DRAFT"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    SPAM_DROP = "SPAM_DROP"


class SupportTicket(BaseModel):
    ticket_id: str
    customer_name: str
    customer_email: str
    subject: str
    message: str
    created_at: datetime = Field(default_factory=datetime.now)


class KnowledgeArticle(BaseModel):
    article_id: str
    title: str
    category: TicketCategory
    keywords: list[str]
    content: str
    policy_url: str


class TriagedTicket(BaseModel):
    ticket: SupportTicket
    category: TicketCategory
    urgency: TicketUrgency
    sentiment: CustomerSentiment
    is_vip: bool = False
    key_entities: list[str] = Field(default_factory=list)


class ResolutionResult(BaseModel):
    ticket_id: str
    action: ResolutionAction
    confidence_score: float = Field(ge=0.0, le=1.0)
    grounded_articles: list[str] = Field(default_factory=list)
    drafted_response: str | None = None
    internal_agent_notes: str
    reason_for_escalation: str | None = None
