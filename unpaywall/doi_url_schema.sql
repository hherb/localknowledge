-- PostgreSQL Schema for DOI-URL Mapping
-- Optimized for fast lookups and efficient storage

-- Main table for DOI to URL mappings
CREATE TABLE doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,
    url TEXT NOT NULL,
    openalex_id TEXT,
    title TEXT,
    publication_year INTEGER,
    location_type TEXT NOT NULL, -- primary, alternate, best_oa, etc.
    version TEXT,                -- publishedVersion, acceptedManuscript, etc.
    license TEXT,
    host_type TEXT,              -- journal, repository, preprint_server, etc.
    oa_status TEXT,              -- gold, green, bronze, closed
    is_oa BOOLEAN DEFAULT FALSE,
    url_quality_score INTEGER DEFAULT 50, -- For ranking URLs (0-100)
    last_verified TIMESTAMP,             -- For URL validation tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX idx_doi_urls_doi ON doi_urls(doi);
CREATE INDEX idx_doi_urls_url ON doi_urls(url);
CREATE INDEX idx_doi_urls_doi_location_type ON doi_urls(doi, location_type);
CREATE INDEX idx_doi_urls_oa_status ON doi_urls(oa_status) WHERE is_oa = TRUE;
CREATE INDEX idx_doi_urls_host_type ON doi_urls(host_type);
CREATE INDEX idx_doi_urls_publication_year ON doi_urls(publication_year);

-- Unique constraint to prevent duplicate DOI-URL pairs
ALTER TABLE doi_urls ADD CONSTRAINT unique_doi_url 
    UNIQUE(doi, url);

-- Optional: Separate table for DOI metadata (if you want normalization)
CREATE TABLE doi_metadata (
    doi TEXT PRIMARY KEY,
    openalex_id TEXT UNIQUE,
    title TEXT,
    publication_year INTEGER,
    work_type TEXT,
    is_retracted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_doi_metadata_year ON doi_metadata(publication_year);
CREATE INDEX idx_doi_metadata_type ON doi_metadata(work_type);

-- View for getting all URLs per DOI ranked by quality (for trying multiple URLs)
CREATE VIEW doi_urls_ranked AS
SELECT 
    doi,
    url,
    location_type,
    version,
    host_type,
    oa_status,
    is_oa,
    url_quality_score,
    ROW_NUMBER() OVER (
        PARTITION BY doi 
        ORDER BY 
            -- Prioritize open access first
            CASE WHEN is_oa = TRUE THEN 1 ELSE 2 END,
            -- Then by open access quality
            CASE oa_status
                WHEN 'gold' THEN 1
                WHEN 'green' THEN 2
                WHEN 'bronze' THEN 3
                WHEN 'closed' THEN 4
                ELSE 5
            END,
            -- Then by location type reliability
            CASE location_type 
                WHEN 'primary' THEN 1
                WHEN 'best_oa' THEN 2
                WHEN 'alternate' THEN 3
                ELSE 4
            END,
            -- Then by version quality
            CASE version
                WHEN 'publishedVersion' THEN 1
                WHEN 'acceptedManuscript' THEN 2
                WHEN 'submittedManuscript' THEN 3
                ELSE 4
            END,
            -- Finally by calculated quality score
            url_quality_score DESC
    ) as rank
FROM doi_urls;

-- View for getting ONLY open access URLs ranked by quality
CREATE VIEW doi_oa_urls_ranked AS
SELECT 
    doi,
    url,
    location_type,
    version,
    host_type,
    oa_status,
    url_quality_score,
    ROW_NUMBER() OVER (
        PARTITION BY doi 
        ORDER BY 
            -- Prioritize by OA quality
            CASE oa_status
                WHEN 'gold' THEN 1
                WHEN 'green' THEN 2
                WHEN 'bronze' THEN 3
                ELSE 4
            END,
            -- Then by reliability
            CASE location_type 
                WHEN 'best_oa' THEN 1
                WHEN 'primary' THEN 2
                WHEN 'alternate' THEN 3
                ELSE 4
            END,
            -- Version preference
            CASE version
                WHEN 'publishedVersion' THEN 1
                WHEN 'acceptedManuscript' THEN 2
                WHEN 'submittedManuscript' THEN 3
                ELSE 4
            END,
            url_quality_score DESC
    ) as rank
FROM doi_urls
WHERE is_oa = TRUE;

-- View for getting best single URL per DOI (fallback option)
CREATE VIEW doi_best_urls AS
SELECT 
    doi,
    url,
    location_type,
    version,
    host_type,
    oa_status,
    is_oa,
    url_quality_score
FROM doi_urls_ranked 
WHERE rank = 1;

-- Function to get ALL URLs for a DOI, ordered by quality (for trying multiple)
CREATE OR REPLACE FUNCTION get_all_urls_for_doi(input_doi TEXT)
RETURNS TABLE(
    url TEXT,
    location_type TEXT,
    version TEXT,
    host_type TEXT,
    oa_status TEXT,
    is_oa BOOLEAN,
    quality_score INTEGER,
    rank INTEGER
)
AS $$
    SELECT 
        dur.url,
        dur.location_type,
        dur.version,
        dur.host_type,
        dur.oa_status,
        dur.is_oa,
        dur.url_quality_score,
        dur.rank::INTEGER
    FROM doi_urls_ranked dur
    WHERE dur.doi = input_doi
    ORDER BY dur.rank;
$$ LANGUAGE sql;

-- Function to get ONLY open access URLs for a DOI, ordered by quality
CREATE OR REPLACE FUNCTION get_oa_urls_for_doi(input_doi TEXT)
RETURNS TABLE(
    url TEXT,
    location_type TEXT,
    version TEXT,
    host_type TEXT,
    oa_status TEXT,
    quality_score INTEGER,
    rank INTEGER
)
AS $$
    SELECT 
        doar.url,
        doar.location_type,
        doar.version,
        doar.host_type,
        doar.oa_status,
        doar.url_quality_score,
        doar.rank::INTEGER
    FROM doi_oa_urls_ranked doar
    WHERE doar.doi = input_doi
    ORDER BY doar.rank;
$$ LANGUAGE sql;

-- Function to get URLs by quality threshold
CREATE OR REPLACE FUNCTION get_quality_urls_for_doi(
    input_doi TEXT,
    min_quality INTEGER DEFAULT 60
)
RETURNS TABLE(
    url TEXT,
    location_type TEXT,
    oa_status TEXT,
    quality_score INTEGER,
    is_oa BOOLEAN
)
AS $$
    SELECT 
        dur.url,
        dur.location_type,
        dur.oa_status,
        dur.url_quality_score,
        dur.is_oa
    FROM doi_urls_ranked dur
    WHERE dur.doi = input_doi 
      AND dur.url_quality_score >= min_quality
    ORDER BY dur.rank;
$$ LANGUAGE sql;



-- Example queries for your workflow:

-- 1. Get ALL open access URLs for a DOI, ranked by quality (for trying multiple)
-- SELECT * FROM get_oa_urls_for_doi('10.1038/nature12373');

-- 2. Get all URLs (including closed access) for a DOI, ranked
-- SELECT * FROM get_all_urls_for_doi('10.1038/nature12373');

-- 3. Get only high-quality URLs (score >= 70) for a DOI
-- SELECT * FROM get_quality_urls_for_doi('10.1038/nature12373', 70);

-- 4. Batch query: Get top 3 URLs for multiple DOIs
-- WITH top_urls AS (
--     SELECT doi, url, oa_status, rank
--     FROM doi_oa_urls_ranked 
--     WHERE doi IN ('10.1038/nature12373', '10.1126/science.1234567')
--       AND rank <= 3
-- )
-- SELECT * FROM top_urls ORDER BY doi, rank;

-- 5. Find papers with multiple open access options
-- SELECT doi, COUNT(*) as oa_url_count
-- FROM doi_urls 
-- WHERE is_oa = TRUE 
-- GROUP BY doi 
-- HAVING COUNT(*) > 1 
-- ORDER BY oa_url_count DESC;

-- 6. Integration with your biomedical database (example)
-- SELECT 
--     p.paper_id,
--     p.title,
--     p.doi,
--     oa.url,
--     oa.oa_status,
--     oa.quality_score,
--     oa.rank
-- FROM your_papers p
-- JOIN doi_oa_urls_ranked oa ON p.doi = oa.doi
-- WHERE p.specialty = 'emergency_medicine'
--   AND oa.rank <= 3  -- Top 3 URLs per paper
-- ORDER BY p.paper_id, oa.rank;

-- 7. Python-friendly query for URL iteration
-- SELECT doi, 
--        array_agg(url ORDER BY rank) as urls,
--        array_agg(oa_status ORDER BY rank) as oa_statuses,
--        array_agg(quality_score ORDER BY rank) as quality_scores
-- FROM doi_oa_urls_ranked 
-- WHERE doi = %s
-- GROUP BY doi;
