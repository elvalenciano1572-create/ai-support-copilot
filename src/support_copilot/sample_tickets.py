from support_copilot.models import SupportTicket


def get_sample_tickets() -> list[SupportTicket]:
    return [
        SupportTicket(
            ticket_id="TICK-101",
            customer_name="Elena Rostova",
            customer_email="elena.r@growthlabs.io",
            subject="Requesting refund for subscription",
            message=(
                "Hi support, I subscribed 4 days ago to test the tool, but our project roadmap has changed. "
                "We have only made around 20 API calls. Can I get a full refund to my card please?"
            ),
        ),
        SupportTicket(
            ticket_id="TICK-102",
            customer_name="Marcus Vance",
            customer_email="dev@hyperstack.io",
            subject="Getting continuous HTTP 429 errors on production sync",
            message=(
                "Hello, our batch worker is getting hammered with HTTP 429 rate limit responses. "
                "What is the exact requests per minute ceiling on the Pro plan and how do we handle retries?"
            ),
        ),
        SupportTicket(
            ticket_id="TICK-103",
            customer_name="Alex Chen",
            customer_email="achen@securecorp.com",
            subject="URGENT: Locked out of account - lost 2FA phone",
            message=(
                "I lost my authentication phone during a flight and I am completely locked out of our "
                "admin dashboard. Can you please disable 2FA on my account immediately? "
                "I have urgent client deliverables today."
            ),
        ),
        SupportTicket(
            ticket_id="TICK-104",
            customer_name="Sophia Martinez",
            customer_email="smartinez@enterprise-partners.com",
            subject="Custom HIPAA compliance & Dedicated Spanner Node SLA",
            message=(
                "We are evaluating your platform for our healthcare clinical trial data. "
                "Do you provide a BAA for HIPAA compliance and can you guarantee a 99.999% uptime SLA "
                "with a dedicated Google Cloud Spanner regional instance?"
            ),
        ),
        SupportTicket(
            ticket_id="TICK-105",
            customer_name="Promo Bot",
            customer_email="spammer@promonet.xyz",
            subject="Exclusive online casino bonuses and crypto profit",
            message="Claim your 500% deposit bonus on crypto casino today. Click here to win big!",
        ),
    ]
