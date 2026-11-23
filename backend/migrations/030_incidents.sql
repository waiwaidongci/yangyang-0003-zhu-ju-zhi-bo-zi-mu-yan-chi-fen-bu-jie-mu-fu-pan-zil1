CREATE TABLE IF NOT EXISTS delay_incident (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    segment_code text NOT NULL REFERENCES live_segment(code),
    source_revision integer NOT NULL,
    track_version integer NOT NULL,
    sla_ms integer NOT NULL CHECK (sla_ms > 0),
    impacted_cues integer[] NOT NULL CHECK (cardinality(impacted_cues) > 0),
    cause text NOT NULL CHECK (cause IN ('monitoring','latency_queue','missing_context','handoff')),
    countermeasure text NOT NULL,
    closed_by text,
    closed_at timestamptz,
    UNIQUE(segment_code,source_revision,track_version),
    FOREIGN KEY(segment_code,track_version) REFERENCES caption_track(segment_code,version)
);
CREATE TABLE IF NOT EXISTS delay_retest (
    incident_id bigint NOT NULL REFERENCES delay_incident(id),
    cue_no integer NOT NULL CHECK (cue_no > 0),
    replay_delay_ms integer NOT NULL CHECK (replay_delay_ms BETWEEN 0 AND 30000),
    checked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(incident_id,cue_no)
);
