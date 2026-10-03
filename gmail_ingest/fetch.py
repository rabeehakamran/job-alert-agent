"""
Fetches job-alert emails from Gmail from the last day.

Starting simple: a 'newer_than' query filter, run once daily by cron.
This is deliberately not using Gmail's historyId incremental-sync API --
that's more robust but adds state-management overhead (tracking last
processed id, handling the ~7 day history retention window). For a daily
digest where a missed email just means "shows up a day late", the failure
mode of the simple approach is harmless. Swap to historyId later only if
duplicates/misses actually show up in practice.
"""

from gmail_ingest.auth import get_gmail_service
from gmail_ingest.parser import extract_email_text, get_header

# Add/remove senders here as you find new job-alert platforms in your inbox.
JOB_ALERT_SENDERS = [
    "linkedin.com",
    "indeed.com",
    "jobright.ai",
]


def build_query(senders: list[str] = None, newer_than: str = "1d") -> str:
    senders = senders or JOB_ALERT_SENDERS
    sender_filter = " OR ".join(f"from:{s}" for s in senders)
    return f"({sender_filter}) newer_than:{newer_than}"


def fetch_job_emails(service=None, newer_than: str = "1d") -> list[dict]:
    """Returns a list of {id, sender, subject, text} dicts for recent job-alert emails."""
    service = service or get_gmail_service()
    query = build_query(newer_than=newer_than)

    results = service.users().messages().list(userId="me", q=query).execute()
    message_refs = results.get("messages", [])

    emails = []
    for ref in message_refs:
        msg = service.users().messages().get(
            userId="me", id=ref["id"], format="full"
        ).execute()
        payload = msg["payload"]

        emails.append({
            "id": ref["id"],
            "sender": get_header(payload, "From"),
            "subject": get_header(payload, "Subject"),
            "text": extract_email_text(payload),
        })

    return emails


if __name__ == "__main__":
    # Quick manual check: fetch and print what would go to the extraction stage.
    for email in fetch_job_emails():
        print(f"--- {email['subject']} (from {email['sender']}) ---")
        print(email["text"][:300], "...\n")
