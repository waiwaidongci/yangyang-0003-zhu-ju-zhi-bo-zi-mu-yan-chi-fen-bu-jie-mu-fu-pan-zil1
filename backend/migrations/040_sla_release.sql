CREATE TABLE IF NOT EXISTS sla_release (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    program text NOT NULL,
    sla_ms integer NOT NULL CHECK (sla_ms BETWEEN 250 AND 8000),
    status text NOT NULL DEFAULT 'computing' CHECK (status IN ('computing','published','failed')),
    request_key text NOT NULL,
    requested_by text NOT NULL,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    UNIQUE (program, request_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS sla_release_active
    ON sla_release (program) WHERE status='computing';

CREATE TABLE IF NOT EXISTS sla_release_segment (
    release_id bigint NOT NULL REFERENCES sla_release(id),
    segment_code text NOT NULL REFERENCES live_segment(code),
    anchor_revision integer NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','done','failed')),
    diagnosis jsonb,
    error text,
    PRIMARY KEY (release_id, segment_code)
);

ALTER TABLE caption_repair ADD COLUMN IF NOT EXISTS sla_ms integer;
UPDATE caption_repair r SET sla_ms=s.sla_ms FROM live_segment s
WHERE s.code=r.segment_code AND r.sla_ms IS NULL;
