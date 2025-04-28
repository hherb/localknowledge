-- First, create the plpython3u extension if not already available
CREATE EXTENSION IF NOT EXISTS plpython3u;
-- Enable trigram extension for text similarity searches (idempotent)
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- FUNCTION: public.ollama_embedding(text)

-- DROP FUNCTION IF EXISTS public.ollama_embedding(text);

CREATE OR REPLACE FUNCTION public.ollama_embedding(
	text_content text)
    RETURNS vector
    LANGUAGE 'plpython3u'
    COST 100
    VOLATILE PARALLEL RESTRICTED
AS $BODY$
    if 'ollama' not in SD:
        import ollama
        SD['ollama'] = ollama

    ollama = SD['ollama']
    
    try:
        response = ollama.embeddings(
            model="snowflake-arctic-embed2:latest",
            prompt=text_content
        )
        return response.get("embedding")
    except Exception as e:
        plpy.warning(f"Embedding generation error: {str(e)}")
        return None
$BODY$;



-- AI providers table
CREATE TABLE IF NOT EXISTS provider(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    base_url TEXT,
    requires_api_key BOOLEAN DEFAULT FALSE,
    api_key TEXT,
    is_local BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Only insert providers if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM provider WHERE name = 'ollama') THEN
        INSERT INTO provider(name, description, base_url, requires_api_key, api_key, is_local)
        VALUES ('ollama', 'local ollama server', 'http://localhost:11434', FALSE, NULL, TRUE);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM provider WHERE name = 'huggingface') THEN
        INSERT INTO provider(name, description, base_url, requires_api_key, api_key, is_local)
        VALUES ('huggingface', 'huggingface api', 'https://api-inference.huggingface.co', TRUE, '', FALSE);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM provider WHERE name = 'torch') THEN
        INSERT INTO provider(name, description, base_url, requires_api_key, is_local)
        VALUES ('torch', 'auto downloaded and cached models via the torch library', FALSE, TRUE);
    END IF;
END $$;

-- Model capabilities (as a separate lookup table)
CREATE TABLE IF NOT EXISTS model_capabilities(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create unique index if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_model_capabilities_name_unique'
    ) THEN
        CREATE UNIQUE INDEX idx_model_capabilities_name_unique ON model_capabilities(name);
    END IF;
END $$;

-- Insert common model capabilities if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM model_capabilities WHERE name = 'chat') THEN
        INSERT INTO model_capabilities(name, description)
        VALUES
            ('chat', 'Model can be used for chat-style interactions'),
            ('reasoning', 'Model has reasoning capabilities'),
            ('instruct', 'Model follows instructions well'),
            ('visual', 'Model can process visual inputs'),
            ('embedding', 'Model can create embeddings'),
            ('reranker', 'Model can rerank search results'),
            ('stt', 'Speech-to-text capability'),
            ('tts', 'Text-to-speech capability'),
            ('tool_use', 'Model can use tools/functions');
    END IF;
END $$;

-- AI models table
CREATE TABLE IF NOT EXISTS models(
    id SERIAL PRIMARY KEY,
    provider_id INTEGER REFERENCES provider(id),
    name TEXT NOT NULL,
    description TEXT,
    params BIGINT,
    quantization TEXT,
    context_length INTEGER,
    embedding_length INTEGER,
    is_free BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create unique index on model name if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_models_name_unique'
    ) THEN
        CREATE UNIQUE INDEX idx_models_name_unique ON models(name);
    END IF;
END $$;

-- Junction table for model capabilities (many-to-many)
CREATE TABLE IF NOT EXISTS model_capability_junction(
    model_id INTEGER REFERENCES models(id),
    capability_id INTEGER REFERENCES model_capabilities(id),
    PRIMARY KEY (model_id, capability_id)
);

-- Insert sample models with provider lookup by name
DO $$
DECLARE
    ollama_id INTEGER;
    torch_id INTEGER;
    snowflake_model_id INTEGER;
    gemma_model_id INTEGER;
    bge_model_id INTEGER;
    cogito_model_id INTEGER;
    embedding_cap_id INTEGER;
    chat_cap_id INTEGER;
    instruct_cap_id INTEGER;
    visual_cap_id INTEGER;
    reranker_cap_id INTEGER;
    tool_use_cap_id INTEGER;
BEGIN
    -- Get provider IDs by name
    SELECT id INTO ollama_id FROM provider WHERE name = 'ollama';
    SELECT id INTO torch_id FROM provider WHERE name = 'torch';
    
    -- Insert models if they don't exist
    IF NOT EXISTS (SELECT 1 FROM models WHERE name = 'snowflake-arctic-embed2:latest') THEN
        INSERT INTO models(provider_id, name, description, params, quantization, context_length, embedding_length, is_free)
        VALUES (ollama_id, 'snowflake-arctic-embed2:latest', 'Snowflake Arctic Embedding Model', 1024, 'F16', 8192, 1024, TRUE)
        RETURNING id INTO snowflake_model_id;
    ELSE
        SELECT id INTO snowflake_model_id FROM models WHERE name = 'snowflake-arctic-embed2:latest';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM models WHERE name = 'gemma3:4b:latest') THEN
        INSERT INTO models(provider_id, name, description, params, quantization, context_length, embedding_length, is_free)
        VALUES (ollama_id, 'gemma3:4b:latest', 'Gemma 3 Model', 4300000000, 'Q4_K_M', 131072, 2560, TRUE)
        RETURNING id INTO gemma_model_id;
    ELSE
        SELECT id INTO gemma_model_id FROM models WHERE name = 'gemma3:4b:latest';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM models WHERE name = 'BAAI/bge-reranker-base') THEN
        INSERT INTO models(provider_id, name, description, params, quantization, context_length, embedding_length, is_free)
        VALUES (torch_id, 'BAAI/bge-reranker-base', 'BAAI BGE Reranker Model', 1000000000, 'int8', 2048, 1024, TRUE)
        RETURNING id INTO bge_model_id;
    ELSE
        SELECT id INTO bge_model_id FROM models WHERE name = 'BAAI/bge-reranker-base';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM models WHERE name = 'cogito:8b') THEN
        INSERT INTO models(provider_id, name, description, params, quantization, context_length, embedding_length, is_free)
        VALUES (ollama_id, 'cogito:8b', 'Cogito Model', 8000000000, 'Q4_K_M', 131072, 4096, TRUE)
        RETURNING id INTO cogito_model_id;
    ELSE
        SELECT id INTO cogito_model_id FROM models WHERE name = 'cogito:8b';
    END IF;
    
    -- Get capability IDs
    SELECT id INTO embedding_cap_id FROM model_capabilities WHERE name = 'embedding';
    SELECT id INTO chat_cap_id FROM model_capabilities WHERE name = 'chat';
    SELECT id INTO instruct_cap_id FROM model_capabilities WHERE name = 'instruct';
    SELECT id INTO visual_cap_id FROM model_capabilities WHERE name = 'visual';
    SELECT id INTO reranker_cap_id FROM model_capabilities WHERE name = 'reranker';
    SELECT id INTO tool_use_cap_id FROM model_capabilities WHERE name = 'tool_use';
    
    -- Add capabilities for models if they don't exist
    IF NOT EXISTS (
        SELECT 1 FROM model_capability_junction 
        WHERE model_id = snowflake_model_id AND capability_id = embedding_cap_id
    ) THEN
        INSERT INTO model_capability_junction(model_id, capability_id)
        VALUES (snowflake_model_id, embedding_cap_id);
    END IF;
    
    -- For gemma3:4b
    IF NOT EXISTS (
        SELECT 1 FROM model_capability_junction 
        WHERE model_id = gemma_model_id AND capability_id = chat_cap_id
    ) THEN
        INSERT INTO model_capability_junction(model_id, capability_id)
        VALUES (gemma_model_id, chat_cap_id);
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM model_capability_junction 
        WHERE model_id = gemma_model_id AND capability_id = instruct_cap_id
    ) THEN
        INSERT INTO model_capability_junction(model_id, capability_id)
        VALUES (gemma_model_id, instruct_cap_id);
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM model_capability_junction 
        WHERE model_id = gemma_model_id AND capability_id = visual_cap_id
    ) THEN
        INSERT INTO model_capability_junction(model_id, capability_id)
        VALUES (gemma_model_id, visual_cap_id);
    END IF;
    
    -- For BGE reranker
    IF NOT EXISTS (
        SELECT 1 FROM model_capability_junction 
        WHERE model_id = bge_model_id AND capability_id = reranker_cap_id
    ) THEN
        INSERT INTO model_capability_junction(model_id, capability_id)
        VALUES (bge_model_id, reranker_cap_id);
    END IF;
    
    -- For cogito
    IF NOT EXISTS (
        SELECT 1 FROM model_capability_junction 
        WHERE model_id = cogito_model_id AND capability_id = tool_use_cap_id
    ) THEN
        INSERT INTO model_capability_junction(model_id, capability_id)
        VALUES (cogito_model_id, tool_use_cap_id);
    END IF;
END $$;

-- Document collections table (for organizing documents into searchable collections)
CREATE TABLE IF NOT EXISTS document_collections (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Search strategies table
CREATE TABLE IF NOT EXISTS search_strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Search parameters table with improved type handling
CREATE TABLE IF NOT EXISTS search_parameters (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES search_strategies(id),
    name VARCHAR(100) NOT NULL,
    parameter_type VARCHAR(50) NOT NULL, -- e.g., 'float', 'boolean', 'int', 'string'
    default_value TEXT,
    description TEXT,
    validation_rule TEXT -- Optional JSON schema or regex for validation
);

-- Search instances (each execution of a search with specific parameters)
CREATE TABLE IF NOT EXISTS search_instances (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES search_strategies(id),
    user_id INTEGER REFERENCES users(id),  -- Reference to existing users table
    collection_id INTEGER REFERENCES document_collections(id),
    query_text TEXT NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER, -- How long the search took
    total_results INTEGER, -- Total number of results returned
    embedding_model_id INTEGER REFERENCES models(id),
    reranker_model_id INTEGER REFERENCES models(id)
);

-- Parameter values for each search instance
CREATE TABLE IF NOT EXISTS search_instance_parameters (
    id SERIAL PRIMARY KEY,
    search_instance_id INTEGER REFERENCES search_instances(id) ON DELETE CASCADE,
    parameter_id INTEGER REFERENCES search_parameters(id),
    parameter_value TEXT NOT NULL,
    UNIQUE (search_instance_id, parameter_id)
);

-- Search results with improved score precision
CREATE TABLE IF NOT EXISTS search_results (
    id SERIAL PRIMARY KEY,
    search_instance_id INTEGER REFERENCES search_instances(id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents(id), -- Reference to existing documents table
    rank_position INTEGER NOT NULL, -- Position in search results (1-based)
    score DECIMAL(10, 6), -- Raw score with higher precision
    similarity_score DECIMAL(10, 6), -- Vector similarity score
    reranker_score DECIMAL(10, 6) -- Reranker score if applicable
);

-- Evaluation domains
CREATE TABLE IF NOT EXISTS evaluation_domains(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create unique index on domain name if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_evaluation_domains_name_unique'
    ) THEN
        CREATE UNIQUE INDEX idx_evaluation_domains_name_unique ON evaluation_domains(name);
    END IF;
END $$;

-- Insert evaluation domains if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM evaluation_domains WHERE name = 'general') THEN
        INSERT INTO evaluation_domains(name, description) 
        VALUES 
            ('general', 'any domain'),
            ('medicine', 'any medical domain'),
            ('engineering', 'any engineering domain'),
            ('computer_science', 'any computer science domain'),
            ('physics', 'any physics domain'),
            ('mathematics', 'any mathematics domain'),
            ('chemistry', 'any chemistry domain'),
            ('biology', 'any biology domain'),
            ('geology', 'any geology domain'),
            ('astronomy', 'any astronomy domain'),
            ('psychology', 'any psychology domain'),
            ('sociology', 'any sociology domain'),
            ('political_science', 'any political science domain'),
            ('history', 'any history domain'),
            ('philosophy', 'any philosophy domain'),
            ('linguistics', 'any linguistics domain'),
            ('anthropology', 'any anthropology domain'),
            ('education', 'any education domain'),
            ('law', 'any law domain');
    END IF;
END $$;

-- Evaluator types
CREATE TABLE IF NOT EXISTS evaluator_types(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create unique index on evaluator type name if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_evaluator_types_name_unique'
    ) THEN
        CREATE UNIQUE INDEX idx_evaluator_types_name_unique ON evaluator_types(name);
    END IF;
END $$;

-- Insert evaluator types if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM evaluator_types WHERE name = 'human') THEN
        INSERT INTO evaluator_types(name, description) 
        VALUES 
            ('human', 'any human person'),
            ('professional', 'any professional person working in that domain e.g doctor, engineer, ....'),
            ('domain_expert', 'any domain expert for that domain'),
            ('LLM', 'any LLM'),
            ('Agent', 'any agent');
    END IF;
END $$;

-- Evaluators
CREATE TABLE IF NOT EXISTS evaluators(
    id SERIAL PRIMARY KEY,
    evaluator_type_id INTEGER REFERENCES evaluator_types(id),
    user_id INTEGER REFERENCES users(id),  -- Reference to existing users table
    evaluation_domain_id INTEGER REFERENCES evaluation_domains(id) DEFAULT 1,
    name VARCHAR(100) NOT NULL,
    model_id INTEGER REFERENCES models(id), -- If this is an LLM evaluator
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Relevancy ratings with comments as JSONB for structured feedback
CREATE TABLE IF NOT EXISTS relevancy_ratings (
    id SERIAL PRIMARY KEY,
    result_id INTEGER REFERENCES search_results(id) ON DELETE CASCADE,
    evaluator_id INTEGER REFERENCES evaluators(id),
    relevancy_score INTEGER CHECK (relevancy_score BETWEEN 0 AND 4),
    rating_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    comments TEXT,
    structured_feedback JSONB DEFAULT '{}'::jsonb -- For structured evaluation criteria
);

-- Create indexes for performance if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_search_instances_strategy') THEN
        CREATE INDEX idx_search_instances_strategy ON search_instances(strategy_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_search_results_instance') THEN
        CREATE INDEX idx_search_results_instance ON search_results(search_instance_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_search_results_document') THEN
        CREATE INDEX idx_search_results_document ON search_results(document_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_relevancy_ratings_result') THEN
        CREATE INDEX idx_relevancy_ratings_result ON relevancy_ratings(result_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_relevancy_ratings_evaluator') THEN
        CREATE INDEX idx_relevancy_ratings_evaluator ON relevancy_ratings(evaluator_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_search_instance_params') THEN
        CREATE INDEX idx_search_instance_params ON search_instance_parameters(search_instance_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_collection') THEN
        CREATE INDEX idx_documents_collection ON documents(collection_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_search_instances_query_trgm') THEN
        CREATE INDEX idx_search_instances_query_trgm ON search_instances USING gin(query_text gin_trgm_ops);
    END IF;
END $$;

-- Create function to calculate NDCG if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'calculate_ndcg') THEN
        CREATE FUNCTION calculate_ndcg(
            result_scores INTEGER[], 
            ideal_scores INTEGER[]
        ) RETURNS DECIMAL AS $$
        DECLARE
            dcg DECIMAL := 0;
            idcg DECIMAL := 0;
            i INTEGER;
        BEGIN
            -- Calculate DCG
            FOR i IN 1..array_length(result_scores, 1) LOOP
                dcg := dcg + (result_scores[i]::DECIMAL / (LOG(2, i + 1)));
            END LOOP;
            
            -- Calculate IDCG from ideal scores
            FOR i IN 1..array_length(ideal_scores, 1) LOOP
                idcg := idcg + (ideal_scores[i]::DECIMAL / (LOG(2, i + 1)));
            END LOOP;
            
            -- Return NDCG
            IF idcg = 0 THEN
                RETURN 0;
            ELSE
                RETURN dcg / idcg;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
    END IF;
END $$;

-- Drop the materialized view if it exists to recreate it with the updated schema
DROP MATERIALIZED VIEW IF EXISTS search_strategy_performance;

-- Create a better materialized view for performance analysis
CREATE MATERIALIZED VIEW search_strategy_performance AS
WITH ranked_ratings AS (
    SELECT 
        si.id AS search_instance_id,
        si.strategy_id,
        sr.rank_position,
        rr.relevancy_score,
        ROW_NUMBER() OVER (PARTITION BY si.id ORDER BY rr.relevancy_score DESC) AS ideal_rank
    FROM 
        search_instances si
    JOIN 
        search_results sr ON si.id = sr.search_instance_id
    JOIN 
        relevancy_ratings rr ON sr.id = rr.result_id
),
instance_metrics AS (
    SELECT
        search_instance_id,
        strategy_id,
        -- Create arrays of scores in result order and ideal order for NDCG calculation
        ARRAY_AGG(relevancy_score ORDER BY rank_position) AS result_scores,
        ARRAY_AGG(relevancy_score ORDER BY ideal_rank) AS ideal_scores,
        COUNT(*) AS total_rated,
        SUM(CASE WHEN relevancy_score >= 2 THEN 1 ELSE 0 END) AS relevant_count,
        AVG(relevancy_score) AS avg_relevancy
    FROM 
        ranked_ratings
    GROUP BY 
        search_instance_id, strategy_id
)
SELECT 
    ss.id AS strategy_id,
    ss.name AS strategy_name,
    si.id AS search_instance_id,
    si.query_text,
    jsonb_object_agg(sp.name, sip.parameter_value) AS parameters,
    im.total_rated,
    im.relevant_count,
    im.avg_relevancy,
    calculate_ndcg(im.result_scores, im.ideal_scores) AS ndcg_score,
    -- Precision at k metrics
    (SUM(CASE WHEN rr.relevancy_score >= 2 AND sr.rank_position <= 5 THEN 1 ELSE 0 END)::DECIMAL / 
        LEAST(COUNT(DISTINCT CASE WHEN sr.rank_position <= 5 THEN sr.id END), 5)) AS precision_at_5,
    (SUM(CASE WHEN rr.relevancy_score >= 2 AND sr.rank_position <= 10 THEN 1 ELSE 0 END)::DECIMAL / 
        LEAST(COUNT(DISTINCT CASE WHEN sr.rank_position <= 10 THEN sr.id END), 10)) AS precision_at_10
FROM 
    search_strategies ss
JOIN 
    search_instances si ON ss.id = si.strategy_id
JOIN 
    search_results sr ON si.id = sr.search_instance_id
JOIN 
    relevancy_ratings rr ON sr.id = rr.result_id
JOIN 
    search_instance_parameters sip ON si.id = sip.search_instance_id
JOIN 
    search_parameters sp ON sip.parameter_id = sp.id
JOIN
    instance_metrics im ON si.id = im.search_instance_id
GROUP BY 
    ss.id, ss.name, si.id, si.query_text, im.total_rated, im.relevant_count, im.avg_relevancy, im.ndcg_score;

-- Create an index on the materialized view if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_search_strategy_performance') THEN
        CREATE INDEX idx_search_strategy_performance ON search_strategy_performance(strategy_id, search_instance_id);
    END IF;
END $$;

-- Drop the function if it exists to recreate it with improvements
DROP FUNCTION IF EXISTS find_best_strategy_for_query(TEXT, DECIMAL, TEXT);

-- Improved function to find best strategy for similar queries
CREATE OR REPLACE FUNCTION find_best_strategy_for_query(
    query_text TEXT,
    similarity_threshold DECIMAL DEFAULT 0.5,
    priority_metric TEXT DEFAULT 'ndcg_score'
) 
RETURNS TABLE (
    strategy_id INTEGER,
    strategy_name VARCHAR(100),
    parameters JSONB,
    ndcg_score DECIMAL,
    precision_at_5 DECIMAL,
    precision_at_10 DECIMAL,
    avg_relevancy DECIMAL,
    relevant_results_count BIGINT,
    similarity_to_query DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ssp.strategy_id,
        ssp.strategy_name,
        ssp.parameters,
        ssp.ndcg_score,
        ssp.precision_at_5,
        ssp.precision_at_10,
        ssp.avg_relevancy,
        ssp.relevant_count,
        similarity(ssp.query_text, query_text) AS similarity_to_query
    FROM 
        search_strategy_performance ssp
    WHERE 
        similarity(ssp.query_text, query_text) > similarity_threshold
    ORDER BY 
        CASE 
            WHEN priority_metric = 'ndcg_score' THEN ssp.ndcg_score
            WHEN priority_metric = 'precision_at_5' THEN ssp.precision_at_5
            WHEN priority_metric = 'precision_at_10' THEN ssp.precision_at_10
            WHEN priority_metric = 'avg_relevancy' THEN ssp.avg_relevancy
            WHEN priority_metric = 'relevant_count' THEN ssp.relevant_count::DECIMAL
            ELSE ssp.ndcg_score
        END DESC,
        similarity(ssp.query_text, query_text) DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;