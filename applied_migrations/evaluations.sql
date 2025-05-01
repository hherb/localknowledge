-- ============================================
-- Table: evaluations
-- ============================================

CREATE TABLE IF NOT EXISTS evaluations (
    research_question_id INTEGER NOT NULL REFERENCES research_questions(id),
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    evaluator_id INTEGER NOT NULL REFERENCES evaluators(id),
    document_id INTEGER NOT NULL,  -- denormalized for performance
    is_human_evaluator BOOLEAN NOT NULL DEFAULT FALSE,
    rating INTEGER NOT NULL,  -- 0-5
    rating_reason TEXT,
    confidence_level FLOAT NOT NULL CHECK (confidence_level >= 0.0 AND confidence_level <= 1.0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evaluation_version INTEGER DEFAULT 1,
    PRIMARY KEY (research_question_id, chunk_id, evaluator_id)
);

-- ============================================
-- Trigger Function: update version + timestamp
-- ============================================

CREATE OR REPLACE FUNCTION trg_bump_version_and_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW IS DISTINCT FROM OLD THEN
        NEW.updated_at := CURRENT_TIMESTAMP;
        NEW.evaluation_version := OLD.evaluation_version + 1;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Trigger: auto-update on change
-- ============================================

DROP TRIGGER IF EXISTS trg_update_eval_version ON evaluations;

CREATE TRIGGER trg_update_eval_version
BEFORE UPDATE ON evaluations
FOR EACH ROW
EXECUTE FUNCTION trg_bump_version_and_timestamp();

-- ============================================
-- Recommended Indexes
-- ============================================

-- Queries per question
CREATE INDEX idx_eval_question ON evaluations(research_question_id);

-- Queries per chunk/document
CREATE INDEX idx_eval_chunk ON evaluations(chunk_id);
CREATE INDEX idx_eval_document ON evaluations(document_id);

-- Queries per evaluator (e.g., per LLM or human)
CREATE INDEX idx_eval_evaluator ON evaluations(evaluator_id);

-- Efficient filtering by LLM
CREATE INDEX idx_eval_llm ON evaluations(is_human_evaluator)
WHERE is_human_evaluator = FALSE;

-- Composite for analytics: question × document
CREATE INDEX idx_eval_question_doc ON evaluations(research_question_id, document_id);



