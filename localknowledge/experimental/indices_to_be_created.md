CREATE INDEX idx_document_publication_date ON public.document (publication_date);
CREATE INDEX idx_document_added_date ON public.document (added_date);
CREATE INDEX idx_document_updated_date ON public.document (updated_date);

- GIN index for title ILIKE %pattern%
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_document_title_trgm ON public.document USING gin (title gin_trgm_ops);
CREATE INDEX idx_document_all_keywords ON public.document USING gin (all_keywords);