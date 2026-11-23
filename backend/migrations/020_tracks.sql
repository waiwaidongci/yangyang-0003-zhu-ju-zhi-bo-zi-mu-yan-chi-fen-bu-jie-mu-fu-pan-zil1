CREATE TABLE IF NOT EXISTS caption_track (
    segment_code text NOT NULL REFERENCES live_segment(code),
    version integer NOT NULL CHECK (version > 0),
    quality_id bigint NOT NULL REFERENCES caption_quality_review(id),
    file_name text NOT NULL,
    vtt_body text NOT NULL,
    track_hash text NOT NULL,
    prepared_by text NOT NULL,
    signed_by text,
    signed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (segment_code,version)
);
