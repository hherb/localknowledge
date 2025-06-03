CREATE TABLE public.bookmarks (
    id integer NOT NULL,
    document_id integer NOT NULL,
    user_id integer NOT NULL,
    project_id integer,
    bookmark_type text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT bookmarks_bookmark_type_check CHECK ((bookmark_type = ANY (ARRAY['personal'::text, 'project'::text, 'both'::text])))
);
CREATE TABLE public.categories (
    id integer NOT NULL,
    name text NOT NULL,
    description text
);
CREATE TABLE public.chunking_strategies (
    id integer NOT NULL,
    strategy_name text NOT NULL,
    modelname text,
    parameters jsonb
);
CREATE TABLE public.chunks (
    id integer NOT NULL,
    document_id integer,
    chunking_strategy_id integer,
    chunktype_id integer,
    document_title text,
    text text,
    chunklength integer,
    chunk_no integer NOT NULL,
    page_start integer DEFAULT 0,
    page_end integer DEFAULT 0,
    metadata jsonb
);
CREATE TABLE public.chunktypes (
    id integer NOT NULL,
    chunktype text NOT NULL
);
CREATE TABLE public.document (
    id integer NOT NULL,
    source_id integer,
    external_id text NOT NULL,
    doi text,
    title text,
    abstract text,
    category_id integer,
    keywords text[],
    augmented_keywords text[],
    mesh_terms text[],
    authors text[],
    publication text,
    publication_date date,
    url text,
    pdf_url text,
    pdf_filename text,
    full_text text,
    added_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    withdrawn_date timestamp without time zone,
    withdrawn_reason text,
    all_keywords text[],
    abstract_length integer,
    missing_details boolean DEFAULT false,
    search_vector tsvector GENERATED ALWAYS AS ((setweight(to_tsvector('english'::regconfig, COALESCE(title, ''::text)), 'A'::"char") || setweight(to_tsvector('english'::regconfig, COALESCE(abstract, ''::text)), 'B'::"char"))) STORED
);
CREATE TABLE public.document_keywords (
    document_id integer NOT NULL,
    keyword text NOT NULL
);
CREATE TABLE public.embedding_base (
    id integer NOT NULL,
    chunk_id integer NOT NULL,
    model_id integer
);
CREATE TABLE public.emb_1024 (
    embedding public.vector(1024)
)
INHERITS (public.embedding_base);
CREATE TABLE public.emb_768 (
    embedding public.vector(768)
)
INHERITS (public.embedding_base);
CREATE TABLE public.embedding_models (
    id integer NOT NULL,
    provider_id integer,
    model_name text NOT NULL,
    model_description text,
    model_parameters jsonb
);
CREATE TABLE public.embedding_provider (
    id integer NOT NULL,
    provider_name text NOT NULL,
    base_url text
);
CREATE TABLE public.embedding_source (
    id integer NOT NULL,
    name text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.evaluations (
    research_question_id integer NOT NULL,
    chunk_id integer NOT NULL,
    evaluator_id integer NOT NULL,
    document_id integer NOT NULL,
    is_human_evaluator boolean DEFAULT false NOT NULL,
    rating integer NOT NULL,
    rating_reason text,
    confidence_level double precision NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    evaluation_version integer DEFAULT 1,
    CONSTRAINT evaluations_confidence_level_check CHECK (((confidence_level >= (0.0)::double precision) AND (confidence_level <= (1.0)::double precision)))
);
CREATE TABLE public.evaluators (
    id integer NOT NULL,
    name text NOT NULL,
    user_id integer,
    model_id text,
    parameters jsonb,
    prompt text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);
CREATE TABLE public.hypotheses (
    id integer NOT NULL,
    hypothesis text NOT NULL,
    counterhypothesis text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.hypotheses_projects (
    project_id integer NOT NULL,
    hypothesis_id integer NOT NULL
);
CREATE TABLE public.import_tracker (
    filename text NOT NULL,
    imported timestamp with time zone,
    chunked timestamp with time zone,
    embedded boolean DEFAULT false,
    md5checked boolean DEFAULT false
);
CREATE TABLE public.keywords (
    keyword text NOT NULL
);
CREATE TABLE public.model_capabilities (
    id integer NOT NULL,
    name text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.model_capability_junction (
    model_id integer NOT NULL,
    capability_id integer NOT NULL
);
CREATE TABLE public.model_providers (
    id integer NOT NULL,
    name text NOT NULL,
    description text,
    base_url text,
    requires_api_key boolean DEFAULT false,
    api_key text,
    is_local boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    is_active boolean DEFAULT true
);
CREATE TABLE public.models (
    id integer NOT NULL,
    provider_id integer NOT NULL,
    name text NOT NULL,
    description text,
    params bigint,
    quantization text,
    context_length integer,
    embedding_length integer,
    is_free boolean DEFAULT false,
    is_locally_available boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    is_active boolean DEFAULT true
);
CREATE TABLE public.processing_queue (
    id integer DEFAULT nextval('public.processing_queue_id_seq'::regclass) NOT NULL,
    document_id integer NOT NULL,
    task_id integer NOT NULL,
    status integer,
    error text,
    created timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated timestamp with time zone
);
CREATE TABLE public.project_contributors (
    project_id integer NOT NULL,
    user_id integer NOT NULL
);
CREATE TABLE public.project_research_questions (
    project_id integer NOT NULL,
    question_id integer NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.projects (
    id integer NOT NULL,
    title text NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_worked_on timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    manager_id integer
);
CREATE TABLE public.prompts (
    id integer NOT NULL,
    model_id integer,
    prompt text NOT NULL,
    purpose text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by integer
);
CREATE TABLE public.pubmed_download_log (
    id integer NOT NULL,
    file_name character varying(255) NOT NULL,
    file_type character varying(50) NOT NULL,
    download_date timestamp without time zone NOT NULL,
    processed boolean DEFAULT false,
    process_date timestamp without time zone,
    file_size bigint,
    checksum character varying(64),
    status character varying(20) DEFAULT 'downloaded'::character varying
);
CREATE TABLE public.reading_records (
    id integer NOT NULL,
    user_id integer,
    read_timestamp timestamp without time zone,
    rating integer,
    notes text,
    document_id integer
);
CREATE TABLE public.reading_records_tags (
    record_id integer NOT NULL,
    tag_id integer NOT NULL
);
CREATE TABLE public.reading_suggestions (
    id integer NOT NULL,
    document_id integer NOT NULL,
    user_id integer NOT NULL,
    evaluator_id integer NOT NULL,
    recommendation_strength integer,
    confidence_level double precision,
    comment text,
    user_agreement boolean,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT reading_suggestions_recommendation_strength_check CHECK (((recommendation_strength >= 0) AND (recommendation_strength <= 5)))
);
CREATE TABLE public.reading_tags (
    id integer NOT NULL,
    name text NOT NULL
);
CREATE TABLE public.research_questions (
    id integer NOT NULL,
    question text NOT NULL,
    details text
);
CREATE TABLE public.sources (
    id integer NOT NULL,
    name text NOT NULL,
    url text,
    is_reputable boolean DEFAULT false,
    is_free boolean DEFAULT true
);
CREATE TABLE public.summaries (
    id integer NOT NULL,
    summary text,
    evaluation boolean,
    reason text,
    interests text[],
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    document_id integer NOT NULL
);
CREATE TABLE public.tags (
    id integer NOT NULL,
    document_id integer,
    user_id integer,
    tag text NOT NULL
);
CREATE TABLE public.task (
    id integer NOT NULL,
    description text
);
CREATE TABLE public.tmpdocument (
    id integer DEFAULT nextval('public.document_id_seq'::regclass) NOT NULL,
    source_id integer,
    external_id text NOT NULL,
    doi text,
    title text,
    abstract text,
    category_id integer,
    keywords text[],
    augmented_keywords text[],
    mesh_terms text[],
    authors text[],
    publication text,
    publication_date date,
    url text,
    pdf_url text,
    pdf_filename text,
    full_text text,
    added_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    withdrawn_date timestamp without time zone,
    withdrawn_reason text,
    all_keywords text[],
    abstract_length integer,
    missing_details boolean DEFAULT false
);
CREATE TABLE public.unified_multiembeddings (
    id integer NOT NULL,
    document_id integer,
    embed_source_id integer,
    chunk_no integer,
    page_no integer,
    text text,
    keywords text[],
    embedding public.vector(1024),
    model_name text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE public.user_interests (
    id integer NOT NULL,
    user_id integer,
    interest text NOT NULL
);
CREATE TABLE public.users (
    id integer NOT NULL,
    username text NOT NULL,
    firstname text,
    surname text,
    email text NOT NULL,
    pwdhash text NOT NULL
);
CREATE TABLE public.version (
    version integer NOT NULL,
    migrated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    migration_success boolean NOT NULL
);
CREATE INDEX chunks_chunktype_id_idx ON public.chunks USING btree (chunktype_id);
CREATE INDEX chunks_document_id_idx ON public.chunks USING btree (document_id);
CREATE INDEX emb_1024_chunk_model_idx ON public.emb_1024 USING btree (chunk_id, model_id);
CREATE INDEX emb_768_chunk_model_idx ON public.emb_768 USING btree (chunk_id, model_id);
CREATE INDEX hypotheses_hypothesis_idx ON public.hypotheses USING gin (to_tsvector('english'::regconfig, hypothesis));
CREATE INDEX idx_bookmarks_document_id ON public.bookmarks USING btree (document_id);
CREATE INDEX idx_bookmarks_project_id ON public.bookmarks USING btree (project_id);
CREATE INDEX idx_bookmarks_type ON public.bookmarks USING btree (bookmark_type);
CREATE INDEX idx_bookmarks_user_id ON public.bookmarks USING btree (user_id);
CREATE INDEX idx_chunks_document_id_chunking_strategy_id ON public.chunks USING btree (document_id, chunking_strategy_id);
CREATE INDEX idx_document_added_date ON public.document USING btree (added_date);
CREATE INDEX idx_document_doi ON public.document USING btree (doi) WITH (deduplicate_items='true');
CREATE INDEX idx_document_external_id ON public.document USING btree (external_id);
CREATE INDEX idx_document_fts ON public.document USING gin (search_vector);
CREATE INDEX idx_document_publication_date ON public.document USING btree (publication_date);
CREATE INDEX idx_document_updated_date ON public.document USING btree (updated_date);
CREATE INDEX idx_eval_chunk ON public.evaluations USING btree (chunk_id);
CREATE INDEX idx_eval_document ON public.evaluations USING btree (document_id);
CREATE INDEX idx_eval_evaluator ON public.evaluations USING btree (evaluator_id);
CREATE INDEX idx_eval_llm ON public.evaluations USING btree (is_human_evaluator) WHERE (is_human_evaluator = false);
CREATE INDEX idx_eval_question ON public.evaluations USING btree (research_question_id);
CREATE INDEX idx_eval_question_doc ON public.evaluations USING btree (research_question_id, document_id);
CREATE INDEX idx_hypotheses_projects_hypothesis ON public.hypotheses_projects USING btree (hypothesis_id);
CREATE INDEX idx_hypotheses_projects_project ON public.hypotheses_projects USING btree (project_id);
CREATE INDEX idx_model_cap_junction_capability ON public.model_capability_junction USING btree (capability_id);
CREATE INDEX idx_model_cap_junction_model ON public.model_capability_junction USING btree (model_id);
CREATE INDEX idx_models_name ON public.models USING btree (name);
CREATE INDEX idx_models_provider_id ON public.models USING btree (provider_id);
CREATE INDEX idx_project_contributors_user_id ON public.project_contributors USING btree (user_id);
CREATE INDEX idx_projects_manager_id ON public.projects USING btree (manager_id);
CREATE INDEX idx_prompts_model_id ON public.prompts USING btree (model_id);
CREATE INDEX idx_prq_project_active ON public.project_research_questions USING btree (project_id) WHERE is_active;
CREATE INDEX idx_prq_question_active ON public.project_research_questions USING btree (question_id) WHERE is_active;
CREATE INDEX idx_reading_records_document_id ON public.reading_records USING btree (document_id);
CREATE INDEX idx_reading_records_read_timestamp ON public.reading_records USING btree (read_timestamp);
CREATE INDEX idx_reading_suggestions_document_id ON public.reading_suggestions USING btree (document_id);
CREATE INDEX idx_reading_suggestions_evaluator_id ON public.reading_suggestions USING btree (evaluator_id);
CREATE INDEX idx_reading_suggestions_recommendation_strength ON public.reading_suggestions USING btree (recommendation_strength);
CREATE INDEX idx_reading_suggestions_user_id ON public.reading_suggestions USING btree (user_id);
CREATE INDEX idx_summaries_document_id ON public.summaries USING btree (document_id);
CREATE INDEX idx_tmpdocument_external_id ON public.tmpdocument USING btree (external_id);
CREATE INDEX idx_unified_multiembeddings_created_at ON public.unified_multiembeddings USING btree (created_at);
CREATE INDEX idx_unified_multiembeddings_document_id ON public.unified_multiembeddings USING btree (document_id);
CREATE INDEX idx_unified_multiembeddings_embed_source_id ON public.unified_multiembeddings USING btree (embed_source_id);
CREATE INDEX idx_unified_multiembeddings_embedding ON public.unified_multiembeddings USING ivfflat (embedding public.vector_cosine_ops);
CREATE INDEX idx_unified_multiembeddings_model_name ON public.unified_multiembeddings USING btree (model_name);
CREATE INDEX idx_user_interests_user_id ON public.user_interests USING btree (user_id);
CREATE INDEX processing_queue_document_id_idx ON public.processing_queue USING btree (document_id);
CREATE INDEX tmpdocument_added_date_idx ON public.tmpdocument USING btree (added_date);
CREATE INDEX tmpdocument_doi_idx ON public.tmpdocument USING btree (doi) WITH (deduplicate_items='true');
CREATE INDEX tmpdocument_publication_date_idx ON public.tmpdocument USING btree (publication_date);
CREATE INDEX tmpdocument_updated_date_idx ON public.tmpdocument USING btree (updated_date);
    ADD CONSTRAINT bookmarks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;
    ADD CONSTRAINT bookmarks_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;
    ADD CONSTRAINT bookmarks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
    ADD CONSTRAINT document_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);
    ADD CONSTRAINT document_keywords_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;
    ADD CONSTRAINT document_keywords_keyword_fkey FOREIGN KEY (keyword) REFERENCES public.keywords(keyword) ON DELETE CASCADE;
    ADD CONSTRAINT document_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);
    ADD CONSTRAINT embedding_base_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.chunks(id) ON DELETE CASCADE;
    ADD CONSTRAINT evaluations_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.chunks(id);
    ADD CONSTRAINT evaluations_evaluator_id_fkey FOREIGN KEY (evaluator_id) REFERENCES public.evaluators(id);
    ADD CONSTRAINT evaluations_research_question_id_fkey FOREIGN KEY (research_question_id) REFERENCES public.research_questions(id);
    ADD CONSTRAINT evaluators_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);
    ADD CONSTRAINT hypotheses_projects_hypothesis_id_fkey FOREIGN KEY (hypothesis_id) REFERENCES public.hypotheses(id) ON DELETE CASCADE;
    ADD CONSTRAINT hypotheses_projects_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;
    ADD CONSTRAINT model_capability_junction_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.model_capabilities(id);
    ADD CONSTRAINT model_capability_junction_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id);
    ADD CONSTRAINT models_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.model_providers(id);
    ADD CONSTRAINT project_contributors_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;
    ADD CONSTRAINT project_contributors_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
    ADD CONSTRAINT project_research_questions_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;
    ADD CONSTRAINT project_research_questions_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.research_questions(id) ON DELETE CASCADE;
    ADD CONSTRAINT projects_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES public.users(id) ON DELETE SET NULL;
    ADD CONSTRAINT prompts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);
    ADD CONSTRAINT prompts_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id);
    ADD CONSTRAINT reading_records_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;
    ADD CONSTRAINT reading_records_tags_record_id_fkey FOREIGN KEY (record_id) REFERENCES public.reading_records(id) ON DELETE CASCADE;
    ADD CONSTRAINT reading_records_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.reading_tags(id) ON DELETE CASCADE;
    ADD CONSTRAINT reading_suggestions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id);
    ADD CONSTRAINT reading_suggestions_evaluator_id_fkey FOREIGN KEY (evaluator_id) REFERENCES public.evaluators(id);
    ADD CONSTRAINT reading_suggestions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);
    ADD CONSTRAINT summaries_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;
    ADD CONSTRAINT tags_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;
    ADD CONSTRAINT unified_multiembeddings_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;
    ADD CONSTRAINT unified_multiembeddings_embed_source_id_fkey FOREIGN KEY (embed_source_id) REFERENCES public.embedding_source(id) ON DELETE CASCADE;
    ADD CONSTRAINT user_interests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;