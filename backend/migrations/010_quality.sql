CREATE TABLE IF NOT EXISTS cue_channel_mark (
    segment_code text NOT NULL,
    cue_no integer NOT NULL,
    channel text NOT NULL CHECK (channel IN ('host','guest','remote')),
    speaker text NOT NULL CHECK (char_length(speaker) BETWEEN 1 AND 40),
    display_ms integer NOT NULL CHECK (display_ms BETWEEN 250 AND 15000),
    PRIMARY KEY (segment_code,cue_no),
    FOREIGN KEY (segment_code,cue_no) REFERENCES cue_anchor(segment_code,cue_no)
);
CREATE TABLE IF NOT EXISTS caption_quality_review (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    segment_code text NOT NULL REFERENCES live_segment(code),
    max_chars_per_second integer NOT NULL CHECK (max_chars_per_second BETWEEN 8 AND 30),
    input_hash text NOT NULL,
    result jsonb NOT NULL,
    reviewed_by text,
    scanned_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz
);
