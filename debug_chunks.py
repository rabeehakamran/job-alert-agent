"""
Debug helper: fetches today's job-alert emails and prints each one's chunks
(subject, chunk index, length, and full content) without running extraction.
Use this to inspect exactly what text is going into a chunk that's failing
extraction, instead of guessing which email/section it is.

Usage:
    python debug_chunks.py
"""

from dotenv import load_dotenv

load_dotenv()

from gmail_ingest.fetch import fetch_job_emails
from extraction.extract import chunk_email_text


def main():
    emails = fetch_job_emails()
    print(f"Found {len(emails)} email(s).\n")

    for email_idx, email in enumerate(emails):
        chunks = chunk_email_text(email["text"])
        print(f"=== Email {email_idx + 1}: {email['subject']} ({len(chunks)} chunk(s)) ===\n")

        for chunk_idx, chunk in enumerate(chunks):
            print(f"--- chunk {chunk_idx + 1}/{len(chunks)} (length {len(chunk)}) ---")
            print(chunk)
            print()

        print("=" * 80, "\n")


if __name__ == "__main__":
    main()