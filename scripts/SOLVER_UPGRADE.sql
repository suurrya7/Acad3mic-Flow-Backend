-- ACAD3MIC FLOW - ASSIGNMENT SOLVER UPGRADE (v1)
-- Adds: awaiting_info status, missing_info_details column, assignment_chunks table

-- 1. Add 'awaiting_info' to the assignments status check constraint
--    First, drop the old constraint and recreate it with the new value.
ALTER TABLE public.assignments
    DROP CONSTRAINT IF EXISTS assignments_status_check;

ALTER TABLE public.assignments
    ADD CONSTRAINT assignments_status_check
    CHECK (status IN ('pending', 'processing', 'awaiting_info', 'completed', 'failed'));

-- 2. Add columns to assignments table for the interactive loop
ALTER TABLE public.assignments
    ADD COLUMN IF NOT EXISTS missing_info_details JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS error_message TEXT;

-- 3. Create checkpoint table to persist generated chunks
CREATE TABLE IF NOT EXISTS public.assignment_chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID NOT NULL REFERENCES public.assignments(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    heading     TEXT NOT NULL,
    content     TEXT NOT NULL,          -- Raw (pre-humanized) section content
    is_humanized BOOLEAN DEFAULT FALSE, -- True once humanized
    target_words INTEGER,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unique constraint: one row per (assignment, section index)
ALTER TABLE public.assignment_chunks
    DROP CONSTRAINT IF EXISTS uq_assignment_chunk;
ALTER TABLE public.assignment_chunks
    ADD CONSTRAINT uq_assignment_chunk UNIQUE (assignment_id, chunk_index);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_chunks_assignment_id ON public.assignment_chunks(assignment_id, chunk_index);

-- 4. RLS: only owner can view their chunks (using the assignments table as the lookup)
ALTER TABLE public.assignment_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own assignment chunks" ON public.assignment_chunks;
CREATE POLICY "Users can view own assignment chunks" ON public.assignment_chunks
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.assignments a
            WHERE a.id = assignment_chunks.assignment_id
            AND a.user_id = auth.uid()
        )
    );

-- 5. Grant service role full access (backend bypasses RLS)
GRANT ALL ON public.assignment_chunks TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
