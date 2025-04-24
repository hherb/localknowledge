-- Find the best performing search strategy overall
SELECT 
    strategy_id,
    strategy_name,
    parameters,
    AVG(avg_relevancy_score) AS average_relevancy,
    AVG(relevant_results_count) AS avg_relevant_results,
    COUNT(*) AS number_of_searches
FROM 
    search_strategy_performance
GROUP BY 
    strategy_id, strategy_name, parameters
ORDER BY 
    average_relevancy DESC, 
    avg_relevant_results DESC
LIMIT 10;

-- Find the best parameters for a specific strategy
SELECT 
    strategy_name,
    parameters,
    AVG(avg_relevancy_score) AS average_relevancy,
    AVG(relevant_results_count) AS avg_relevant_results,
    COUNT(*) AS number_of_searches
FROM 
    search_strategy_performance
WHERE 
    strategy_id = 3  -- Replace with your strategy ID
GROUP BY 
    strategy_name, parameters
ORDER BY 
    average_relevancy DESC, 
    avg_relevant_results DESC
LIMIT 10;

-- Analyze performance by parameter value (for a specific parameter)
WITH parameter_performance AS (
    SELECT 
        strategy_name,
        parameters->>'similarity_threshold' AS similarity_threshold,
        AVG(avg_relevancy_score) AS average_relevancy,
        AVG(relevant_results_count) AS avg_relevant_results,
        COUNT(*) AS number_of_searches
    FROM 
        search_strategy_performance
    WHERE 
        parameters ? 'similarity_threshold'
    GROUP BY 
        strategy_name, parameters->>'similarity_threshold'
)
SELECT 
    *
FROM 
    parameter_performance
ORDER BY 
    strategy_name,
    similarity_threshold::float;

-- Compare search strategies for a particular type of query
SELECT 
    strategy_name,
    parameters,
    AVG(avg_relevancy_score) AS average_relevancy,
    AVG(relevant_results_count) AS avg_relevant_results,
    COUNT(*) AS number_of_searches
FROM 
    search_strategy_performance
WHERE 
    query_text ILIKE '%medical imaging%'  -- Replace with your query pattern
GROUP BY 
    strategy_name, parameters
ORDER BY 
    average_relevancy DESC, 
    avg_relevant_results DESC
LIMIT 10;

-- Track performance improvement over time (by month)
SELECT 
    DATE_TRUNC('month', si.executed_at) AS month,
    ss.strategy_name,
    jsonb_object_agg(sp.parameter_name, sip.parameter_value) AS parameters,
    AVG(rr.relevancy_score) AS avg_relevancy,
    COUNT(CASE WHEN rr.relevancy_score >= 2 THEN 1 END)::FLOAT / COUNT(*) AS relevant_ratio
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
    DATE_TRUNC('month', si.executed_at), ss.strategy_name, parameters
ORDER BY 
    month DESC, 
    avg_relevancy DESC;
