"""
Supabase storage layer: persists profile chunks (computed once from the
resume) and job listings (computed daily from the pipeline), so neither
has to be recomputed on every run.

Run storage/schema.sql in the Supabase SQL Editor once before using this.
"""

import os
import re

from supabase import create_client, Client


def get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and/or SUPABASE_KEY are not set in the environment.")
    return create_client(url, key)


# --- Profile chunks -----------------------------------------------------

def save_profile_chunks(chunks: list[dict], client: Client = None) -> None:
    """Replaces the entire stored profile with a fresh set of chunks.

    Called once (or whenever the resume changes) -- not on every pipeline run.
    """
    client = client or get_client()
    client.table("profile_chunks").delete().neq(
        "id", "00000000-0000-0000-0000-000000000000"
    ).execute()

    rows = [{"content": c["text"], "embedding": c["embedding"]} for c in chunks]
    client.table("profile_chunks").insert(rows).execute()


def _parse_embedding(raw) -> list[float]:
    """Supabase's REST API returns pgvector columns as a string like
    "[0.01,0.02,...]" rather than a JSON array, so this normalizes either
    form back into a plain list of floats.
    """
    if isinstance(raw, str):
        return [float(x) for x in raw.strip("[]").split(",")]
    return raw


def get_profile_chunks(client: Client = None) -> list[dict]:
    """Returns stored profile chunks as [{text, embedding}, ...] -- same shape
    build_profile_chunks() produces, so embed_filter.py can use either source
    interchangeably.
    """
    client = client or get_client()
    result = client.table("profile_chunks").select("content, embedding").execute()
    return [
        {"text": row["content"], "embedding": _parse_embedding(row["embedding"])}
        for row in result.data
    ]


# --- Job listings ---------------------------------------------------------

def make_dedup_hash(title: str, company: str) -> str:
    """Normalizes title+company so the same job from different platforms collides."""
    normalized = f"{title}|{company}".lower()
    normalized = re.sub(r"[^a-z0-9|]", "", normalized)
    return normalized


def save_job_listing(
    job: dict, embedding_score: float, status: str = "new", client: Client = None
) -> bool:
    """Inserts a new job listing. Returns False (no-op) if it's a duplicate.

    status defaults to "new" (ready for the judge stage), but the embedding
    filter also stores jobs that didn't pass as "embedding_rejected" rather
    than discarding them -- useful later for checking whether the coarse
    threshold is too strict or too loose.
    """
    client = client or get_client()
    dedup_hash = make_dedup_hash(job["title"], job["company"])

    row = {
        "title": job["title"],
        "company": job["company"],
        "location": job.get("location"),
        "apply_link": job.get("apply_link"),
        "source": job.get("source"),
        "stack_mentioned": job.get("stack_mentioned", []),
        "dedup_hash": dedup_hash,
        "embedding_score": embedding_score,
        "status": status,
    }

    try:
        client.table("job_listings").insert(row).execute()
        return True
    except Exception as e:
        # unique constraint violation on dedup_hash -- this job is already stored
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            return False
        raise


def get_jobs_by_status(status: str, client: Client = None) -> list[dict]:
    client = client or get_client()
    result = client.table("job_listings").select("*").eq("status", status).execute()
    return result.data


def update_judge_result(
    job_id: str,
    score: int,
    reasoning: str,
    seniority_mismatch: bool,
    status: str,
    client: Client = None,
) -> None:
    client = client or get_client()
    client.table("job_listings").update({
        "llm_score": score,
        "llm_reasoning": reasoning,
        "seniority_mismatch": seniority_mismatch,
        "status": status,
    }).eq("id", job_id).execute()


def mark_as_sent(job_ids: list[str], client: Client = None) -> None:
    client = client or get_client()
    client.table("job_listings").update({
        "status": "sent",
        "sent_at": "now()",
    }).in_("id", job_ids).execute()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    client = get_client()
    chunks = get_profile_chunks(client)
    print(f"Stored profile chunks: {len(chunks)}")

    new_jobs = get_jobs_by_status("new", client)
    print(f"Jobs with status 'new': {len(new_jobs)}")