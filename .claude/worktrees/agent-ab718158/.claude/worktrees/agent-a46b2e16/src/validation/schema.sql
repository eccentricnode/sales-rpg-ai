-- Call recordings/transcripts
CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,                    -- "John Discovery Call"
    transcript TEXT,              -- Full transcript
    duration_seconds INTEGER,
    recording_url TEXT,           -- Optional: link to audio
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ground truth for testing
CREATE TABLE IF NOT EXISTS expected_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    segment_start INTEGER,        -- Start position (for partial tests)
    segment_end INTEGER,          -- End position
    tie_downs JSONB,              -- ["9/10", "ready now"]
    script_position TEXT,         -- "financial_qualification"
    should_flag TEXT[],           -- ["skipped_rapport", "qualify_budget"]
    suggested_response TEXT,      -- What AI should suggest
    notes TEXT
);

-- Test runs
CREATE TABLE IF NOT EXISTS test_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    expected_id UUID REFERENCES expected_outputs(id),
    model TEXT,                   -- "phi-3.5" / "llama-70b"
    script_version TEXT,          -- Track script changes
    raw_output TEXT,              -- Full AI response
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Evaluation results
CREATE TABLE IF NOT EXISTS test_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_run_id UUID REFERENCES test_runs(id),
    caught_tie_downs BOOLEAN,
    correct_position BOOLEAN,
    correct_flags BOOLEAN,
    good_suggestion BOOLEAN,
    overall_pass BOOLEAN,
    notes TEXT
);
