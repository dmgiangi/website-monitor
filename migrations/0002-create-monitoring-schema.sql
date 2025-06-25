SET search_path TO website_monitor;

CREATE TABLE failure_log
(
    id                 SERIAL PRIMARY KEY,
    original_target_id INTEGER,
    worker_id          VARCHAR(255) NOT NULL,
    check_start_time   TIMESTAMPTZ  NOT NULL,
    check_end_time     TIMESTAMPTZ  NOT NULL,
    failure_type       VARCHAR(255) NOT NULL,
    detail             TEXT,
    http_status_code   INTEGER,
    target_snapshot    JSONB
);

-- Recommended index for efficient querying
CREATE INDEX idx_failure_log_target_id_start_time ON failure_log (original_target_id, check_start_time DESC);