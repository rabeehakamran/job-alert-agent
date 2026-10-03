"""
Manual test runner for the first two pipeline stages: Gmail fetch -> extraction.

This does NOT touch Supabase or Twilio -- it just prints what the extraction
agent pulled out of today's job-alert emails, so you can sanity-check both
stages together before wiring in storage and scoring.

Usage:
    python run_ingest_and_extract.py
"""

from dotenv import load_dotenv

load_dotenv()

from gmail_ingest.fetch import fetch_job_emails
from extraction.extract import extract_jobs


def main():
    print("Fetching job-alert emails from the last day...")
    emails = fetch_job_emails()
    print(f"Found {len(emails)} email(s).\n")

    total_jobs = 0
    for email in emails:
        print(f"--- {email['subject']} (from {email['sender']}) ---")
        try:
            jobs = extract_jobs(email["text"], sender=email["sender"])
        except ValueError as e:
            print(f"  [extraction failed: {e}]\n")
            continue

        if not jobs:
            print("  No job listings found in this email.\n")
            continue

        for job in jobs:
            print(f"  - {job['title']} @ {job['company']} ({job.get('location') or 'location n/a'})")
        total_jobs += len(jobs)
        print()

    print(f"Total jobs extracted: {total_jobs}")


if __name__ == "__main__":
    main()