"""
Extracts structured job-listing data from raw email text using Groq.

One email can contain zero jobs (a newsletter with no listings), one job,
or several (digest-style emails from LinkedIn/Indeed often bundle 5-10).
The model returns {"jobs": [...]} -- wrapped in an object rather than a
bare array, because Groq's JSON mode (like OpenAI's) requires the
top-level response to be a JSON object, not an array.

Uses openai/gpt-oss-20b: this stage runs on every fetched email, so it
needs to be cheap and fast. It's the lighter of the two models actually
available on Groq's free developer tier (the Llama models require a
sales-approved plan) -- 250K tokens/min and 1K requests/min, which
comfortably covers a personal inbox's volume.
"""

import json
import os

from groq import Groq

MODEL = "openai/gpt-oss-20b"

EXTRACTION_SYSTEM_PROMPT = """You extract structured job listing data from an email.

The email may contain zero, one, or multiple job postings (digest-style emails
often bundle several). Return ONLY a JSON object of this exact shape, no other text:

{
  "jobs": [
    {
      "title": "<job title as written>",
      "company": "<company name>",
      "location": "<location if mentioned, else null>",
      "apply_link": "<direct URL to apply if present, else null>",
      "source": "<platform inferred from sender, e.g. linkedin, indeed, jobright>",
      "stack_mentioned": ["<technologies/skills explicitly mentioned>"]
    }
  ]
}

Rules:
- If the email contains no actual job postings (e.g. it's a newsletter, article
  digest, or generic update), return {"jobs": []}.
- Do not infer or guess missing fields -- use null for anything not explicitly stated.
- Do not summarize or paraphrase the title or company name.
- stack_mentioned should be an empty array if no technologies are explicitly named.
"""


def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set in the environment.")
    return Groq(api_key=api_key)


def extract_jobs(email_text: str, sender: str, client: Groq = None, max_retries: int = 2) -> list[dict]:
    """Returns a list of job dicts extracted from one email's text. Empty list if none found."""
    if not email_text.strip():
        return []

    client = client or _get_client()
    user_prompt = f"Sender: {sender}\n\nEmail content:\n{email_text[:8000]}"

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            return parsed.get("jobs", [])

        except (json.JSONDecodeError, KeyError) as e:
            last_error = e
            continue

    # Both attempts failed to produce valid JSON -- fail loudly rather than
    # silently dropping emails. Caller decides whether to log and skip.
    raise ValueError(f"Extraction failed after {max_retries} attempts: {last_error}")


if __name__ == "__main__":
    sample_email = """
    New jobs for you:
    1. Backend Engineer at Acme Corp - Remote - Python, FastAPI, PostgreSQL
       Apply: https://acme.example.com/jobs/123
    2. Senior ML Engineer at DataCo - San Francisco - requires 7+ years experience
       Apply: https://dataco.example.com/careers/456
    """
    jobs = extract_jobs(sample_email, sender="jobs-noreply@linkedin.com")
    print(json.dumps(jobs, indent=2))