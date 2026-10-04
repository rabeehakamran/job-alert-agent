"""
Runs the pipeline end to end, as far as it's built: Gmail -> extraction ->
embedding filter -> Supabase storage. (The LLM judge and WhatsApp digest
stages come next -- this is the coarse-filtering half of the pipeline.)

This is what the daily cron job will eventually call.

Usage:
    python run_pipeline.py
"""

from dotenv import load_dotenv

load_dotenv()

from gmail_ingest.fetch import fetch_job_emails
from extraction.extract import extract_jobs_from_email
from scoring.embed_filter import score_job_against_profile
from storage.db import get_profile_chunks, save_job_listing, get_client


def main():
    client = get_client()

    profile_chunks = get_profile_chunks(client)
    if not profile_chunks:
        print("No profile chunks found in Supabase -- run setup_profile.py first.")
        return
    print(f"Loaded {len(profile_chunks)} profile chunks.\n")

    print("Fetching job-alert emails from the last day...")
    emails = fetch_job_emails()
    print(f"Found {len(emails)} email(s).\n")

    stats = {"extracted": 0, "passed_filter": 0, "rejected_filter": 0, "duplicates": 0}

    for email in emails:
        jobs = extract_jobs_from_email(email["text"], sender=email["sender"])
        if not jobs:
            continue

        for job in jobs:
            stats["extracted"] += 1
            result = score_job_against_profile(job, profile_chunks, client=None)

            status = "new" if result["passed"] else "embedding_rejected"
            saved = save_job_listing(job, result["score"], status=status, client=client)

            if not saved:
                stats["duplicates"] += 1
                continue

            if result["passed"]:
                stats["passed_filter"] += 1
                print(f"  [PASS {result['score']:.2f}] {job['title']} @ {job['company']}")
            else:
                stats["rejected_filter"] += 1

    print(f"\n--- Summary ---")
    print(f"Jobs extracted:     {stats['extracted']}")
    print(f"Passed filter:      {stats['passed_filter']}")
    print(f"Rejected by filter: {stats['rejected_filter']}")
    print(f"Duplicates skipped: {stats['duplicates']}")


if __name__ == "__main__":
    main()