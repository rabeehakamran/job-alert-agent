"""
Coarse relevance filter: embeds a job listing and compares it against the
candidate's profile chunks via cosine similarity, taking the best match.

This is the first of the two-stage scoring approach -- a cheap, fast pass
that filters out clearly irrelevant jobs before the more expensive LLM judge
runs. The threshold is intentionally loose (favoring false positives over
false negatives): a wrong job reaching the judge just costs one extra LLM
call, while a good job getting filtered out here is lost for good.
"""

import math

from scoring.profile import EMBEDDING_DIM, EMBEDDING_MODEL, _get_client
from google.genai import types

COARSE_MATCH_THRESHOLD = 0.65


def job_to_embedding_text(job: dict) -> str:
    parts = [
        f"Job title: {job['title']}",
        f"Company: {job['company']}",
    ]
    if job.get("location"):
        parts.append(f"Location: {job['location']}")
    if job.get("stack_mentioned"):
        parts.append(f"Technologies: {', '.join(job['stack_mentioned'])}")
    return " | ".join(parts)


def embed_job(job: dict, client=None) -> list[float]:
    client = client or _get_client()
    text = job_to_embedding_text(job)
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    return result.embeddings[0].values


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def score_job_against_profile(job: dict, profile_chunks: list[dict], client=None) -> dict:
    """Returns {passed, score, best_chunk} for one job against the full profile."""
    client = client or _get_client()
    job_embedding = embed_job(job, client)

    similarities = [
        cosine_similarity(job_embedding, chunk["embedding"]) for chunk in profile_chunks
    ]
    best_idx = similarities.index(max(similarities))

    return {
        "passed": similarities[best_idx] >= COARSE_MATCH_THRESHOLD,
        "score": similarities[best_idx],
        "best_chunk": profile_chunks[best_idx]["text"],
    }


if __name__ == "__main__":
    from scoring.profile import build_profile_chunks
    from dotenv import load_dotenv
    load_dotenv()
    sample_job = {
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "stack_mentioned": ["Python", "FastAPI", "PostgreSQL"],
    }

    chunks = build_profile_chunks("resume.pdf")
    result = score_job_against_profile(sample_job, chunks)
    print(f"Score: {result['score']:.3f} | Passed: {result['passed']}")
    print(f"Best matching chunk: {result['best_chunk'][:100]}...")