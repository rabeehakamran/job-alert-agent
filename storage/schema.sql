-- Run this in Supabase's SQL Editor once, after enabling the pgvector extension
-- (Database -> Extensions -> search "vector" -> enable).

create extension if not exists vector;

-- Resume chunks, embedded and stored once. Re-populated only when the resume
-- changes (see storage/db.py: save_profile_chunks replaces the whole set).
create table if not exists profile_chunks (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  embedding vector(768) not null,
  created_at timestamptz default now()
);

-- One row per extracted job listing.
create table if not exists job_listings (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  company text not null,
  location text,
  apply_link text,
  source text,
  stack_mentioned text[],
  dedup_hash text unique not null,   -- normalized company+title, catches the same job from multiple platforms
  embedding_score float,              -- coarse filter's cosine similarity
  llm_score int,                      -- judge stage's 0-100 score (null until judged)
  llm_reasoning text,                 -- judge stage's one-line reasoning (null until judged)
  seniority_mismatch boolean,
  status text not null default 'new', -- new -> qualified/archived -> sent
  sent_at timestamptz,
  created_at timestamptz default now()
);

create index if not exists idx_job_listings_status on job_listings (status);