CREATE TABLE IF NOT EXISTS live_segment (
    code text PRIMARY KEY,
    program text NOT NULL,
    segment_title text NOT NULL,
    rundown_start time NOT NULL,
    duration_ms integer NOT NULL CHECK (duration_ms BETWEEN 1000 AND 3600000),
    expected_anchors integer NOT NULL CHECK (expected_anchors BETWEEN 5 AND 100),
    sla_ms integer NOT NULL CHECK (sla_ms BETWEEN 250 AND 8000),
    recording_ref text,
    anchor_revision integer NOT NULL DEFAULT 0,
    diagnosis_revision integer,
    diagnosis jsonb,
    CHECK ((diagnosis_revision IS NULL) = (diagnosis IS NULL))
);

CREATE TABLE IF NOT EXISTS cue_anchor (
    segment_code text NOT NULL REFERENCES live_segment(code),
    cue_no integer NOT NULL CHECK (cue_no > 0),
    spoken_ms integer NOT NULL CHECK (spoken_ms >= 0),
    on_air_ms integer NOT NULL CHECK (on_air_ms >= 0),
    excerpt text NOT NULL CHECK (char_length(excerpt) BETWEEN 1 AND 100),
    PRIMARY KEY (segment_code, cue_no),
    UNIQUE (segment_code, spoken_ms)
);

CREATE TABLE IF NOT EXISTS caption_repair (
    segment_code text PRIMARY KEY REFERENCES live_segment(code),
    start_ms integer NOT NULL CHECK (start_ms >= 0),
    end_ms integer NOT NULL CHECK (end_ms >= start_ms),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'editing', 'submitted', 'accepted')),
    corrected_ref text,
    review_note text,
    reviewed_by text,
    submitted_at timestamptz,
    accepted_at timestamptz,
    CHECK (status NOT IN ('submitted', 'accepted') OR (corrected_ref IS NOT NULL AND submitted_at IS NOT NULL)),
    CHECK (status <> 'accepted' OR (reviewed_by IS NOT NULL AND accepted_at IS NOT NULL))
);
