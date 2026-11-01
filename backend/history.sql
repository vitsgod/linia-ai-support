CREATE TABLE IF NOT EXISTS assistant_runs (
    id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('diagnostics','outage','outage_assistant','ticket_draft')),
    status text NOT NULL CHECK (status IN ('started','completed','failed')),
    request_data jsonb NOT NULL CHECK (jsonb_typeof(request_data) = 'object'),
    response_data jsonb CHECK (response_data IS NULL OR jsonb_typeof(response_data) = 'object'),
    error_message text,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    CHECK (
        (status = 'started' AND finished_at IS NULL AND response_data IS NULL AND error_message IS NULL)
        OR (status = 'completed' AND finished_at IS NOT NULL AND response_data IS NOT NULL AND error_message IS NULL)
        OR (status = 'failed' AND finished_at IS NOT NULL AND response_data IS NULL AND error_message IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS assistant_runs_started_idx ON assistant_runs (started_at DESC, id DESC);
