"""
One-time (or whenever your resume changes) setup: builds profile chunks from
your resume PDF and saves them to Supabase. The daily pipeline reads from
Supabase afterward instead of re-embedding the resume on every run.

Usage:
    python setup_profile.py [path/to/resume.pdf]
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from scoring.profile import build_profile_chunks
from storage.db import save_profile_chunks, get_profile_chunks


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "resume.pdf"

    print(f"Building profile chunks from {pdf_path}...")
    chunks = build_profile_chunks(pdf_path)
    print(f"Built {len(chunks)} chunks. Saving to Supabase...")

    save_profile_chunks(chunks)

    stored = get_profile_chunks()
    print(f"Done -- {len(stored)} chunks now stored in Supabase.")


if __name__ == "__main__":
    main()