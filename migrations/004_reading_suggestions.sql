-- Migration 004: Add reading suggestions and evaluators tables

-- Create evaluators table
CREATE TABLE IF NOT EXISTS evaluators (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id),
    model_id TEXT,
    parameters JSONB,
    prompt TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Create reading_suggestions table
CREATE TABLE IF NOT EXISTS reading_suggestions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES document(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    evaluator_id INTEGER NOT NULL REFERENCES evaluators(id),
    recommendation_strength INTEGER CHECK (recommendation_strength >= 0 AND recommendation_strength <= 5),
    confidence_level FLOAT,
    comment TEXT,
    user_agreement BOOLEAN,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_reading_suggestions_document_id ON reading_suggestions(document_id);
CREATE INDEX IF NOT EXISTS idx_reading_suggestions_user_id ON reading_suggestions(user_id);
CREATE INDEX IF NOT EXISTS idx_reading_suggestions_evaluator_id ON reading_suggestions(evaluator_id);
CREATE INDEX IF NOT EXISTS idx_reading_suggestions_recommendation_strength ON reading_suggestions(recommendation_strength);

-- Add a unique constraint to prevent duplicate suggestions
CREATE UNIQUE INDEX IF NOT EXISTS idx_reading_suggestions_unique 
ON reading_suggestions(document_id, user_id, evaluator_id);
