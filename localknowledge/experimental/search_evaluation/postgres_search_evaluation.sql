-- Search strategies table
CREATE TABLE search_strategies (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    strategy_description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Search parameters table (flexible schema for different strategy parameters)
CREATE TABLE search_parameters (
    parameter_id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES search_strategies(strategy_id),
    parameter_name VARCHAR(100) NOT NULL,
    parameter_type VARCHAR(50) NOT NULL, -- e.g., 'float', 'boolean', 'int', 'string'
    default_value TEXT,
    description TEXT
);

-- Search instances (each execution of a search with specific parameters)
CREATE TABLE search_instances (
    search_instance_id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES search_strategies(strategy_id),
    user_id INTEGER,  -- Reference to your users table if needed
    query_text TEXT NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER, -- How long the search took
    total_results INTEGER -- Total number of results returned
);

-- Parameter values for each search instance
CREATE TABLE search_instance_parameters (
    instance_parameter_id SERIAL PRIMARY KEY,
    search_instance_id INTEGER REFERENCES search_instances(search_instance_id),
    parameter_id INTEGER REFERENCES search_parameters(parameter_id),
    parameter_value TEXT NOT NULL
);

-- Search results
CREATE TABLE search_results (
    result_id SERIAL PRIMARY KEY,
    search_instance_id INTEGER REFERENCES search_instances(search_instance_id),
    document_id INTEGER NOT NULL,  -- References your documents table
    rank_position INTEGER NOT NULL, -- Position in search results (1-based)
    score FLOAT -- Raw score if applicable
);

CREATE TABLE evaluator_types(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

INSERT INTO evaluator_types(description) VALUES ('human'), ('LLM'), ('Agent');

CREATE TABLE evaluators(
    id SERIAL PRIMARY KEY,
    evaluator_type_id INTEGER REFERENCES evaluator_types(id),
    user_id INTEGER,  -- Reference to your users table if needed
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
)

-- Relevancy ratings (from users or LLM judges)
CREATE TABLE relevancy_ratings (
    id SERIAL PRIMARY KEY,
    result_id INTEGER REFERENCES search_results(id),
    evaluator_id INTEGER REFERENCES evaluators(id), -- User or LLM that provided the rating
    relevancy_score INTEGER CHECK (relevancy_score BETWEEN 0 AND 4),
    rating_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    comments TEXT
);

-- Create indexes for performance
CREATE INDEX idx_search_instances_strategy ON search_instances(strategy_id);
CREATE INDEX idx_search_results_instance ON search_results(search_instance_id);
CREATE INDEX idx_relevancy_ratings_result ON relevancy_ratings(result_id);
CREATE INDEX idx_search_results_document ON search_results(document_id);
CREATE INDEX idx_search_instance_params ON search_instance_parameters(search_instance_id);

-- Create a materialized view for performance analysis
CREATE MATERIALIZED VIEW search_strategy_performance AS
SELECT 
    ss.strategy_id,
    ss.strategy_name,
    jsonb_object_agg(sp.parameter_name, sip.parameter_value) AS parameters,
    si.search_instance_id,
    si.query_text,
    COUNT(DISTINCT sr.result_id) AS total_results_rated,
    COUNT(DISTINCT CASE WHEN rr.relevancy_score >= 2 THEN sr.result_id END) AS relevant_results_count,
    AVG(rr.relevancy_score) AS avg_relevancy_score,
    SUM(CASE 
        WHEN rr.relevancy_score = 0 THEN 1 ELSE 0 
    END) AS irrelevant_count,
    SUM(CASE 
        WHEN rr.relevancy_score = 1 THEN 1 ELSE 0 
    END) AS somewhat_relevant_count,
    SUM(CASE 
        WHEN rr.relevancy_score = 2 THEN 1 ELSE 0 
    END) AS relevant_count,
    SUM(CASE 
        WHEN rr.relevancy_score = 3 THEN 1 ELSE 0 
    END) AS highly_relevant_count,
    SUM(CASE 
        WHEN rr.relevancy_score = 4 THEN 1 ELSE 0 
    END) AS essential_count,
    -- Normalized Discounted Cumulative Gain (NDCG)
    -- This is a simplified placeholder - actual NDCG calculation would be more complex
    SUM(rr.relevancy_score / (LN(sr.rank_position + 1) / LN(2))) AS dcg_score
FROM 
    search_strategies ss
JOIN 
    search_instances si ON ss.strategy_id = si.strategy_id
JOIN 
    search_results sr ON si.search_instance_id = sr.search_instance_id
JOIN 
    relevancy_ratings rr ON sr.result_id = rr.result_id
JOIN 
    search_instance_parameters sip ON si.search_instance_id = sip.search_instance_id
JOIN 
    search_parameters sp ON sip.parameter_id = sp.parameter_id
GROUP BY 
    ss.strategy_id, ss.strategy_name, si.search_instance_id, si.query_text;

-- Refresh the materialized view
REFRESH MATERIALIZED VIEW search_strategy_performance;

-- Create an index on the materialized view
CREATE INDEX idx_search_strategy_performance ON search_strategy_performance(strategy_id, search_instance_id);

-- Example query to find the best-performing strategy for a similar query
CREATE OR REPLACE FUNCTION find_best_strategy_for_query(query_text TEXT) 
RETURNS TABLE (
    strategy_id INTEGER,
    strategy_name VARCHAR(100),
    parameters JSONB,
    avg_relevancy_score NUMERIC,
    relevant_results_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ssp.strategy_id,
        ssp.strategy_name,
        ssp.parameters,
        ssp.avg_relevancy_score,
        ssp.relevant_results_count
    FROM 
        search_strategy_performance ssp
    WHERE 
        similarity(ssp.query_text, query_text) > 0.5
    ORDER BY 
        ssp.avg_relevancy_score DESC, 
        ssp.relevant_results_count DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;
