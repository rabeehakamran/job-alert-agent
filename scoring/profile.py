"""
Builds an embedded representation of the candidate's profile from a resume PDF.

Rather than forcing the resume into three rigid categories (skills/projects/
experience), this does simple paragraph-level chunking -- the same approach
used for RAG over any document. Each chunk gets its own embedding, and a job
listing is compared against all of them, taking the best (max) match. This
mirrors chunking a paper for retrieval rather than hand-curating fixed buckets.

Uses Gemini's gemini-embedding-001 with task_type=RETRIEVAL_DOCUMENT for
profile chunks, paired with RETRIEVAL_QUERY on the job-listing side in
embed_filter.py -- this asymmetric setup is what the model expects for
retrieval-style comparison (query vs. document), rather than using the same
task type on both sides.
"""

import os

from google import genai
from google.genai import types
from pypdf import PdfReader

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768  # reduced from the 3072 default -- plenty for this use case
MIN_CHUNK_LENGTH = 40  # skip stray short lines (headers, page numbers, etc.)


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set in the environment.")
    return genai.Client(api_key=api_key)


def extract_resume_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


CHUNK_SIZE_CHARS = 400  # roughly a short paragraph's worth


def chunk_resume_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS) -> list[str]:
    """Splits resume text into fixed-size chunks.

    PDFs exported from design tools (Canva, Figma, etc.) often encode text
    position-by-position rather than by logical paragraph, so pypdf extracts
    them with a newline after nearly every word -- there's no reliable blank
    line to split paragraphs on. Normalizing all whitespace first and
    chunking by word count sidesteps that, regardless of how the source PDF
    was laid out.
    """
    normalized = " ".join(text.split())  # collapses all whitespace/newlines to single spaces
    words = normalized.split(" ")

    chunks = []
    current_words = []
    current_len = 0

    for word in words:
        current_words.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunks.append(" ".join(current_words))
            current_words = []
            current_len = 0

    if current_words:
        chunks.append(" ".join(current_words))

    return [c for c in chunks if len(c) >= MIN_CHUNK_LENGTH]


def embed_chunk(text: str, client: genai.Client = None) -> list[float]:
    client = client or _get_client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    return result.embeddings[0].values


def build_profile_chunks(pdf_path: str) -> list[dict]:
    """Returns [{text, embedding}, ...] for every usable chunk in the resume."""
    client = _get_client()
    text = extract_resume_text(pdf_path)
    chunks = chunk_resume_text(text)

    if not chunks:
        raise ValueError(
            f"No usable text chunks found in {pdf_path} -- check the PDF isn't "
            "image-based/scanned (which pypdf can't read without OCR)."
        )

    return [{"text": chunk, "embedding": embed_chunk(chunk, client)} for chunk in chunks]


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv
    load_dotenv()

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "resume.pdf"
    profile_chunks = build_profile_chunks(pdf_path)
    print(f"Built {len(profile_chunks)} profile chunks from {pdf_path}")
    for c in profile_chunks[:3]:
        print(f"  - {c['text'][:80]}...")