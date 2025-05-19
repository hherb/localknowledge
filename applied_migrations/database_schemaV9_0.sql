--
-- PostgreSQL database dump
--

-- Dumped from database version 16.8 (Postgres.app)
-- Dumped by pg_dump version 17.0

-- Started on 2025-05-19 23:18:50 AEST

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_table_access_method = heap;

--
-- TOC entry 318 (class 1259 OID 13027502)
-- Name: bookmarks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bookmarks (
    id integer NOT NULL,
    document_id integer NOT NULL,
    user_id integer NOT NULL,
    project_id integer,
    bookmark_type text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT bookmarks_bookmark_type_check CHECK ((bookmark_type = ANY (ARRAY['personal'::text, 'project'::text, 'both'::text])))
);


--
-- TOC entry 317 (class 1259 OID 13027501)
-- Name: bookmarks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bookmarks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4204 (class 0 OID 0)
-- Dependencies: 317
-- Name: bookmarks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bookmarks_id_seq OWNED BY public.bookmarks.id;


--
-- TOC entry 298 (class 1259 OID 3050038)
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    name text NOT NULL,
    description text
);


--
-- TOC entry 297 (class 1259 OID 3050037)
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4205 (class 0 OID 0)
-- Dependencies: 297
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- TOC entry 320 (class 1259 OID 32047232)
-- Name: chunking_strategies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunking_strategies (
    id integer NOT NULL,
    strategy_name text NOT NULL,
    modelname text,
    parameters jsonb
);


--
-- TOC entry 319 (class 1259 OID 32047231)
-- Name: chunking_strategies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chunking_strategies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4206 (class 0 OID 0)
-- Dependencies: 319
-- Name: chunking_strategies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chunking_strategies_id_seq OWNED BY public.chunking_strategies.id;


--
-- TOC entry 322 (class 1259 OID 32047241)
-- Name: chunks; Type: TABLE; Schema: public; Owner: -
--

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


--
-- TOC entry 321 (class 1259 OID 32047240)
-- Name: chunks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chunks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4207 (class 0 OID 0)
-- Dependencies: 321
-- Name: chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chunks_id_seq OWNED BY public.chunks.id;


--
-- TOC entry 324 (class 1259 OID 32047252)
-- Name: chunktypes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunktypes (
    id integer NOT NULL,
    chunktype text NOT NULL
);


--
-- TOC entry 323 (class 1259 OID 32047251)
-- Name: chunktypes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chunktypes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4208 (class 0 OID 0)
-- Dependencies: 323
-- Name: chunktypes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chunktypes_id_seq OWNED BY public.chunktypes.id;


--
-- TOC entry 300 (class 1259 OID 3050049)
-- Name: document; Type: TABLE; Schema: public; Owner: -
--

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
    all_keywords text[]
);


--
-- TOC entry 299 (class 1259 OID 3050048)
-- Name: document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4209 (class 0 OID 0)
-- Dependencies: 299
-- Name: document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.document_id_seq OWNED BY public.document.id;


--
-- TOC entry 302 (class 1259 OID 3050078)
-- Name: document_keywords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_keywords (
    document_id integer NOT NULL,
    keyword text NOT NULL
);


--
-- TOC entry 326 (class 1259 OID 32047261)
-- Name: embedding_base; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.embedding_base (
    id integer NOT NULL,
    chunk_id integer NOT NULL,
    model_id integer
);


--
-- TOC entry 332 (class 1259 OID 44246962)
-- Name: emb_1024; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emb_1024 (
    embedding public.vector(1024)
)
INHERITS (public.embedding_base);


--
-- TOC entry 327 (class 1259 OID 32047267)
-- Name: emb_768; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emb_768 (
    embedding public.vector(768)
)
INHERITS (public.embedding_base);


--
-- TOC entry 325 (class 1259 OID 32047260)
-- Name: embedding_base_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.embedding_base_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4210 (class 0 OID 0)
-- Dependencies: 325
-- Name: embedding_base_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.embedding_base_id_seq OWNED BY public.embedding_base.id;


--
-- TOC entry 329 (class 1259 OID 32047280)
-- Name: embedding_models; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.embedding_models (
    id integer NOT NULL,
    provider_id integer,
    model_name text NOT NULL,
    model_description text,
    model_parameters jsonb
);


--
-- TOC entry 328 (class 1259 OID 32047279)
-- Name: embedding_models_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.embedding_models_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4211 (class 0 OID 0)
-- Dependencies: 328
-- Name: embedding_models_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.embedding_models_id_seq OWNED BY public.embedding_models.id;


--
-- TOC entry 331 (class 1259 OID 32047287)
-- Name: embedding_provider; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.embedding_provider (
    id integer NOT NULL,
    provider_name text NOT NULL,
    base_url text
);


--
-- TOC entry 330 (class 1259 OID 32047286)
-- Name: embedding_provider_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.embedding_provider_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4212 (class 0 OID 0)
-- Dependencies: 330
-- Name: embedding_provider_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.embedding_provider_id_seq OWNED BY public.embedding_provider.id;


--
-- TOC entry 306 (class 1259 OID 8186733)
-- Name: embedding_source; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.embedding_source (
    id integer NOT NULL,
    name text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- TOC entry 305 (class 1259 OID 8186732)
-- Name: embedding_source_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.embedding_source_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4213 (class 0 OID 0)
-- Dependencies: 305
-- Name: embedding_source_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.embedding_source_id_seq OWNED BY public.embedding_source.id;


--
-- TOC entry 339 (class 1259 OID 85920966)
-- Name: evaluations; Type: TABLE; Schema: public; Owner: -
--

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


--
-- TOC entry 314 (class 1259 OID 12865279)
-- Name: evaluators; Type: TABLE; Schema: public; Owner: -
--

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


--
-- TOC entry 313 (class 1259 OID 12865278)
-- Name: evaluators_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.evaluators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4214 (class 0 OID 0)
-- Dependencies: 313
-- Name: evaluators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.evaluators_id_seq OWNED BY public.evaluators.id;


--
-- TOC entry 334 (class 1259 OID 63980964)
-- Name: hypotheses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hypotheses (
    id integer NOT NULL,
    hypothesis text NOT NULL,
    counterhypothesis text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- TOC entry 333 (class 1259 OID 63980960)
-- Name: hypotheses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hypotheses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4215 (class 0 OID 0)
-- Dependencies: 333
-- Name: hypotheses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hypotheses_id_seq OWNED BY public.hypotheses.id;


--
-- TOC entry 335 (class 1259 OID 63980981)
-- Name: hypotheses_projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hypotheses_projects (
    project_id integer NOT NULL,
    hypothesis_id integer NOT NULL
);


--
-- TOC entry 301 (class 1259 OID 3050071)
-- Name: keywords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.keywords (
    keyword text NOT NULL
);


--
-- TOC entry 345 (class 1259 OID 104946899)
-- Name: model_capabilities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_capabilities (
    id integer NOT NULL,
    name text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- TOC entry 344 (class 1259 OID 104946898)
-- Name: model_capabilities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_capabilities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4216 (class 0 OID 0)
-- Dependencies: 344
-- Name: model_capabilities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_capabilities_id_seq OWNED BY public.model_capabilities.id;


--
-- TOC entry 346 (class 1259 OID 104946908)
-- Name: model_capability_junction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_capability_junction (
    model_id integer NOT NULL,
    capability_id integer NOT NULL
);


--
-- TOC entry 341 (class 1259 OID 104946868)
-- Name: model_providers; Type: TABLE; Schema: public; Owner: -
--

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


--
-- TOC entry 340 (class 1259 OID 104946867)
-- Name: model_providers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_providers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4217 (class 0 OID 0)
-- Dependencies: 340
-- Name: model_providers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_providers_id_seq OWNED BY public.model_providers.id;


--
-- TOC entry 343 (class 1259 OID 104946881)
-- Name: models; Type: TABLE; Schema: public; Owner: -
--

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


--
-- TOC entry 342 (class 1259 OID 104946880)
-- Name: models_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.models_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4218 (class 0 OID 0)
-- Dependencies: 342
-- Name: models_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.models_id_seq OWNED BY public.models.id;


--
-- TOC entry 312 (class 1259 OID 12567764)
-- Name: project_contributors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_contributors (
    project_id integer NOT NULL,
    user_id integer NOT NULL
);


--
-- TOC entry 338 (class 1259 OID 84271108)
-- Name: project_research_questions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_research_questions (
    project_id integer NOT NULL,
    question_id integer NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- TOC entry 311 (class 1259 OID 12567749)
-- Name: projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.projects (
    id integer NOT NULL,
    title text NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_worked_on timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    manager_id integer
);


--
-- TOC entry 310 (class 1259 OID 12567748)
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4219 (class 0 OID 0)
-- Dependencies: 310
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.projects_id_seq OWNED BY public.projects.id;


--
-- TOC entry 348 (class 1259 OID 104946924)
-- Name: prompts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompts (
    id integer NOT NULL,
    model_id integer,
    prompt text NOT NULL,
    purpose text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by integer
);


--
-- TOC entry 347 (class 1259 OID 104946923)
-- Name: prompts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.prompts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4220 (class 0 OID 0)
-- Dependencies: 347
-- Name: prompts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.prompts_id_seq OWNED BY public.prompts.id;


--
-- TOC entry 285 (class 1259 OID 931263)
-- Name: pubmed_download_log; Type: TABLE; Schema: public; Owner: -
--

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


--
-- TOC entry 284 (class 1259 OID 931262)
-- Name: pubmed_download_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pubmed_download_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4221 (class 0 OID 0)
-- Dependencies: 284
-- Name: pubmed_download_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pubmed_download_log_id_seq OWNED BY public.pubmed_download_log.id;


--
-- TOC entry 293 (class 1259 OID 986594)
-- Name: reading_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reading_records (
    id integer NOT NULL,
    user_id integer,
    read_timestamp timestamp without time zone,
    rating integer,
    notes text,
    document_id integer
);


--
-- TOC entry 292 (class 1259 OID 986593)
-- Name: reading_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reading_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4222 (class 0 OID 0)
-- Dependencies: 292
-- Name: reading_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reading_records_id_seq OWNED BY public.reading_records.id;


--
-- TOC entry 294 (class 1259 OID 986604)
-- Name: reading_records_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reading_records_tags (
    record_id integer NOT NULL,
    tag_id integer NOT NULL
);


--
-- TOC entry 316 (class 1259 OID 12865295)
-- Name: reading_suggestions; Type: TABLE; Schema: public; Owner: -
--

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


--
-- TOC entry 315 (class 1259 OID 12865294)
-- Name: reading_suggestions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reading_suggestions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4223 (class 0 OID 0)
-- Dependencies: 315
-- Name: reading_suggestions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reading_suggestions_id_seq OWNED BY public.reading_suggestions.id;


--
-- TOC entry 291 (class 1259 OID 986583)
-- Name: reading_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reading_tags (
    id integer NOT NULL,
    name text NOT NULL
);


--
-- TOC entry 290 (class 1259 OID 986582)
-- Name: reading_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reading_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4224 (class 0 OID 0)
-- Dependencies: 290
-- Name: reading_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reading_tags_id_seq OWNED BY public.reading_tags.id;


--
-- TOC entry 337 (class 1259 OID 63980999)
-- Name: research_questions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_questions (
    id integer NOT NULL,
    question text NOT NULL,
    details text
);


--
-- TOC entry 336 (class 1259 OID 63980998)
-- Name: research_questions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.research_questions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4225 (class 0 OID 0)
-- Dependencies: 336
-- Name: research_questions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.research_questions_id_seq OWNED BY public.research_questions.id;


--
-- TOC entry 296 (class 1259 OID 3050025)
-- Name: sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sources (
    id integer NOT NULL,
    name text NOT NULL,
    url text,
    is_reputable boolean DEFAULT false,
    is_free boolean DEFAULT true
);


--
-- TOC entry 295 (class 1259 OID 3050024)
-- Name: sources_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4226 (class 0 OID 0)
-- Dependencies: 295
-- Name: sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sources_id_seq OWNED BY public.sources.id;


--
-- TOC entry 283 (class 1259 OID 150363)
-- Name: summaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.summaries (
    id integer NOT NULL,
    summary text,
    evaluation boolean,
    reason text,
    interests text[],
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    document_id integer NOT NULL
);


--
-- TOC entry 282 (class 1259 OID 150362)
-- Name: summaries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.summaries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4227 (class 0 OID 0)
-- Dependencies: 282
-- Name: summaries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.summaries_id_seq OWNED BY public.summaries.id;


--
-- TOC entry 304 (class 1259 OID 3050096)
-- Name: tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tags (
    id integer NOT NULL,
    document_id integer,
    user_id integer,
    tag text NOT NULL
);


--
-- TOC entry 303 (class 1259 OID 3050095)
-- Name: tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4228 (class 0 OID 0)
-- Dependencies: 303
-- Name: tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tags_id_seq OWNED BY public.tags.id;


--
-- TOC entry 308 (class 1259 OID 8186768)
-- Name: unified_multiembeddings; Type: TABLE; Schema: public; Owner: -
--

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


--
-- TOC entry 307 (class 1259 OID 8186767)
-- Name: unified_multiembeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.unified_multiembeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4229 (class 0 OID 0)
-- Dependencies: 307
-- Name: unified_multiembeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unified_multiembeddings_id_seq OWNED BY public.unified_multiembeddings.id;


--
-- TOC entry 289 (class 1259 OID 953754)
-- Name: user_interests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_interests (
    id integer NOT NULL,
    user_id integer,
    interest text NOT NULL
);


--
-- TOC entry 288 (class 1259 OID 953753)
-- Name: user_interests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_interests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4230 (class 0 OID 0)
-- Dependencies: 288
-- Name: user_interests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_interests_id_seq OWNED BY public.user_interests.id;


--
-- TOC entry 287 (class 1259 OID 953741)
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username text NOT NULL,
    firstname text,
    surname text,
    email text NOT NULL,
    pwdhash text NOT NULL
);


--
-- TOC entry 286 (class 1259 OID 953740)
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 4231 (class 0 OID 0)
-- Dependencies: 286
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- TOC entry 309 (class 1259 OID 8276354)
-- Name: version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.version (
    version integer NOT NULL,
    migrated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    migration_success boolean NOT NULL
);


--
-- TOC entry 3832 (class 2604 OID 13027505)
-- Name: bookmarks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks ALTER COLUMN id SET DEFAULT nextval('public.bookmarks_id_seq'::regclass);


--
-- TOC entry 3813 (class 2604 OID 3050041)
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- TOC entry 3834 (class 2604 OID 32047235)
-- Name: chunking_strategies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunking_strategies ALTER COLUMN id SET DEFAULT nextval('public.chunking_strategies_id_seq'::regclass);


--
-- TOC entry 3835 (class 2604 OID 32047244)
-- Name: chunks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks ALTER COLUMN id SET DEFAULT nextval('public.chunks_id_seq'::regclass);


--
-- TOC entry 3838 (class 2604 OID 32047255)
-- Name: chunktypes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunktypes ALTER COLUMN id SET DEFAULT nextval('public.chunktypes_id_seq'::regclass);


--
-- TOC entry 3814 (class 2604 OID 3050052)
-- Name: document id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document ALTER COLUMN id SET DEFAULT nextval('public.document_id_seq'::regclass);


--
-- TOC entry 3843 (class 2604 OID 44246965)
-- Name: emb_1024 id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emb_1024 ALTER COLUMN id SET DEFAULT nextval('public.embedding_base_id_seq'::regclass);


--
-- TOC entry 3840 (class 2604 OID 32047270)
-- Name: emb_768 id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emb_768 ALTER COLUMN id SET DEFAULT nextval('public.embedding_base_id_seq'::regclass);


--
-- TOC entry 3839 (class 2604 OID 32047264)
-- Name: embedding_base id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_base ALTER COLUMN id SET DEFAULT nextval('public.embedding_base_id_seq'::regclass);


--
-- TOC entry 3841 (class 2604 OID 32047283)
-- Name: embedding_models id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_models ALTER COLUMN id SET DEFAULT nextval('public.embedding_models_id_seq'::regclass);


--
-- TOC entry 3842 (class 2604 OID 32047290)
-- Name: embedding_provider id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_provider ALTER COLUMN id SET DEFAULT nextval('public.embedding_provider_id_seq'::regclass);


--
-- TOC entry 3818 (class 2604 OID 8186736)
-- Name: embedding_source id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_source ALTER COLUMN id SET DEFAULT nextval('public.embedding_source_id_seq'::regclass);


--
-- TOC entry 3826 (class 2604 OID 12865282)
-- Name: evaluators id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluators ALTER COLUMN id SET DEFAULT nextval('public.evaluators_id_seq'::regclass);


--
-- TOC entry 3844 (class 2604 OID 63980967)
-- Name: hypotheses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hypotheses ALTER COLUMN id SET DEFAULT nextval('public.hypotheses_id_seq'::regclass);


--
-- TOC entry 3864 (class 2604 OID 104946902)
-- Name: model_capabilities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_capabilities ALTER COLUMN id SET DEFAULT nextval('public.model_capabilities_id_seq'::regclass);


--
-- TOC entry 3854 (class 2604 OID 104946871)
-- Name: model_providers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_providers ALTER COLUMN id SET DEFAULT nextval('public.model_providers_id_seq'::regclass);


--
-- TOC entry 3859 (class 2604 OID 104946884)
-- Name: models id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.models ALTER COLUMN id SET DEFAULT nextval('public.models_id_seq'::regclass);


--
-- TOC entry 3823 (class 2604 OID 12567752)
-- Name: projects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects ALTER COLUMN id SET DEFAULT nextval('public.projects_id_seq'::regclass);


--
-- TOC entry 3866 (class 2604 OID 104946927)
-- Name: prompts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompts ALTER COLUMN id SET DEFAULT nextval('public.prompts_id_seq'::regclass);


--
-- TOC entry 3803 (class 2604 OID 931266)
-- Name: pubmed_download_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pubmed_download_log ALTER COLUMN id SET DEFAULT nextval('public.pubmed_download_log_id_seq'::regclass);


--
-- TOC entry 3809 (class 2604 OID 986597)
-- Name: reading_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records ALTER COLUMN id SET DEFAULT nextval('public.reading_records_id_seq'::regclass);


--
-- TOC entry 3829 (class 2604 OID 12865298)
-- Name: reading_suggestions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_suggestions ALTER COLUMN id SET DEFAULT nextval('public.reading_suggestions_id_seq'::regclass);


--
-- TOC entry 3808 (class 2604 OID 986586)
-- Name: reading_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_tags ALTER COLUMN id SET DEFAULT nextval('public.reading_tags_id_seq'::regclass);


--
-- TOC entry 3846 (class 2604 OID 63981002)
-- Name: research_questions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_questions ALTER COLUMN id SET DEFAULT nextval('public.research_questions_id_seq'::regclass);


--
-- TOC entry 3810 (class 2604 OID 3050028)
-- Name: sources id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources ALTER COLUMN id SET DEFAULT nextval('public.sources_id_seq'::regclass);


--
-- TOC entry 3801 (class 2604 OID 150366)
-- Name: summaries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.summaries ALTER COLUMN id SET DEFAULT nextval('public.summaries_id_seq'::regclass);


--
-- TOC entry 3817 (class 2604 OID 3050099)
-- Name: tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags ALTER COLUMN id SET DEFAULT nextval('public.tags_id_seq'::regclass);


--
-- TOC entry 3820 (class 2604 OID 8186771)
-- Name: unified_multiembeddings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings ALTER COLUMN id SET DEFAULT nextval('public.unified_multiembeddings_id_seq'::regclass);


--
-- TOC entry 3807 (class 2604 OID 953757)
-- Name: user_interests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_interests ALTER COLUMN id SET DEFAULT nextval('public.user_interests_id_seq'::regclass);


--
-- TOC entry 3806 (class 2604 OID 953744)
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- TOC entry 3953 (class 2606 OID 13027513)
-- Name: bookmarks bookmarks_document_id_user_id_project_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT bookmarks_document_id_user_id_project_id_key UNIQUE (document_id, user_id, project_id);


--
-- TOC entry 3955 (class 2606 OID 13027511)
-- Name: bookmarks bookmarks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT bookmarks_pkey PRIMARY KEY (id);


--
-- TOC entry 3904 (class 2606 OID 3050047)
-- Name: categories categories_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_name_key UNIQUE (name);


--
-- TOC entry 3906 (class 2606 OID 3050045)
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- TOC entry 3961 (class 2606 OID 32047239)
-- Name: chunking_strategies chunking_strategies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunking_strategies
    ADD CONSTRAINT chunking_strategies_pkey PRIMARY KEY (id);


--
-- TOC entry 3964 (class 2606 OID 33554470)
-- Name: chunks chunks_doc_strategy_chunkno_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_doc_strategy_chunkno_unique UNIQUE (document_id, chunking_strategy_id, chunk_no);


--
-- TOC entry 3967 (class 2606 OID 32047250)
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- TOC entry 3970 (class 2606 OID 32047259)
-- Name: chunktypes chunktypes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunktypes
    ADD CONSTRAINT chunktypes_pkey PRIMARY KEY (id);


--
-- TOC entry 3917 (class 2606 OID 3050084)
-- Name: document_keywords document_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_pkey PRIMARY KEY (document_id, keyword);


--
-- TOC entry 3908 (class 2606 OID 3050058)
-- Name: document document_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_pkey PRIMARY KEY (id);


--
-- TOC entry 3910 (class 2606 OID 3050060)
-- Name: document document_source_id_external_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_source_id_external_id_key UNIQUE (source_id, external_id);


--
-- TOC entry 3982 (class 2606 OID 47683112)
-- Name: emb_1024 emb_1024_chunk_model_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emb_1024
    ADD CONSTRAINT emb_1024_chunk_model_unique UNIQUE (chunk_id, model_id);


--
-- TOC entry 3975 (class 2606 OID 47683110)
-- Name: emb_768 emb_768_chunk_model_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emb_768
    ADD CONSTRAINT emb_768_chunk_model_unique UNIQUE (chunk_id, model_id);


--
-- TOC entry 3972 (class 2606 OID 32047266)
-- Name: embedding_base embedding_base_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_base
    ADD CONSTRAINT embedding_base_pkey PRIMARY KEY (id);


--
-- TOC entry 3977 (class 2606 OID 33169064)
-- Name: embedding_models embedding_models_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_models
    ADD CONSTRAINT embedding_models_pkey PRIMARY KEY (id);


--
-- TOC entry 3979 (class 2606 OID 33169127)
-- Name: embedding_provider embedding_provider_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_provider
    ADD CONSTRAINT embedding_provider_pkey PRIMARY KEY (id);


--
-- TOC entry 3923 (class 2606 OID 8186743)
-- Name: embedding_source embedding_source_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_source
    ADD CONSTRAINT embedding_source_name_key UNIQUE (name);


--
-- TOC entry 3925 (class 2606 OID 8186741)
-- Name: embedding_source embedding_source_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_source
    ADD CONSTRAINT embedding_source_pkey PRIMARY KEY (id);


--
-- TOC entry 3997 (class 2606 OID 85920977)
-- Name: evaluations evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_pkey PRIMARY KEY (research_question_id, chunk_id, evaluator_id);


--
-- TOC entry 3944 (class 2606 OID 12865288)
-- Name: evaluators evaluators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluators
    ADD CONSTRAINT evaluators_pkey PRIMARY KEY (id);


--
-- TOC entry 3985 (class 2606 OID 63980973)
-- Name: hypotheses hypotheses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hypotheses
    ADD CONSTRAINT hypotheses_pkey PRIMARY KEY (id);


--
-- TOC entry 3987 (class 2606 OID 63980987)
-- Name: hypotheses_projects hypotheses_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hypotheses_projects
    ADD CONSTRAINT hypotheses_projects_pkey PRIMARY KEY (project_id, hypothesis_id);


--
-- TOC entry 3915 (class 2606 OID 3050077)
-- Name: keywords keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.keywords
    ADD CONSTRAINT keywords_pkey PRIMARY KEY (keyword);


--
-- TOC entry 4011 (class 2606 OID 104946907)
-- Name: model_capabilities model_capabilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_capabilities
    ADD CONSTRAINT model_capabilities_pkey PRIMARY KEY (id);


--
-- TOC entry 4015 (class 2606 OID 104946912)
-- Name: model_capability_junction model_capability_junction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_capability_junction
    ADD CONSTRAINT model_capability_junction_pkey PRIMARY KEY (model_id, capability_id);


--
-- TOC entry 4005 (class 2606 OID 104946879)
-- Name: model_providers model_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_providers
    ADD CONSTRAINT model_providers_pkey PRIMARY KEY (id);


--
-- TOC entry 4009 (class 2606 OID 104946892)
-- Name: models models_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.models
    ADD CONSTRAINT models_pkey PRIMARY KEY (id);


--
-- TOC entry 3942 (class 2606 OID 12567768)
-- Name: project_contributors project_contributors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_contributors
    ADD CONSTRAINT project_contributors_pkey PRIMARY KEY (project_id, user_id);


--
-- TOC entry 3995 (class 2606 OID 84271115)
-- Name: project_research_questions project_research_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_research_questions
    ADD CONSTRAINT project_research_questions_pkey PRIMARY KEY (project_id, question_id);


--
-- TOC entry 3939 (class 2606 OID 12567758)
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- TOC entry 4018 (class 2606 OID 104946932)
-- Name: prompts prompts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompts
    ADD CONSTRAINT prompts_pkey PRIMARY KEY (id);


--
-- TOC entry 3875 (class 2606 OID 931272)
-- Name: pubmed_download_log pubmed_download_log_file_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pubmed_download_log
    ADD CONSTRAINT pubmed_download_log_file_name_key UNIQUE (file_name);


--
-- TOC entry 3877 (class 2606 OID 931270)
-- Name: pubmed_download_log pubmed_download_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pubmed_download_log
    ADD CONSTRAINT pubmed_download_log_pkey PRIMARY KEY (id);


--
-- TOC entry 3896 (class 2606 OID 986601)
-- Name: reading_records reading_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records
    ADD CONSTRAINT reading_records_pkey PRIMARY KEY (id);


--
-- TOC entry 3898 (class 2606 OID 986608)
-- Name: reading_records_tags reading_records_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records_tags
    ADD CONSTRAINT reading_records_tags_pkey PRIMARY KEY (record_id, tag_id);


--
-- TOC entry 3951 (class 2606 OID 12865305)
-- Name: reading_suggestions reading_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_suggestions
    ADD CONSTRAINT reading_suggestions_pkey PRIMARY KEY (id);


--
-- TOC entry 3890 (class 2606 OID 986592)
-- Name: reading_tags reading_tags_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_tags
    ADD CONSTRAINT reading_tags_name_key UNIQUE (name);


--
-- TOC entry 3892 (class 2606 OID 986590)
-- Name: reading_tags reading_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_tags
    ADD CONSTRAINT reading_tags_pkey PRIMARY KEY (id);


--
-- TOC entry 3991 (class 2606 OID 63981006)
-- Name: research_questions research_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_questions
    ADD CONSTRAINT research_questions_pkey PRIMARY KEY (id);


--
-- TOC entry 3900 (class 2606 OID 3050036)
-- Name: sources sources_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_name_key UNIQUE (name);


--
-- TOC entry 3902 (class 2606 OID 3050034)
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (id);


--
-- TOC entry 3873 (class 2606 OID 150371)
-- Name: summaries summaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.summaries
    ADD CONSTRAINT summaries_pkey PRIMARY KEY (id);


--
-- TOC entry 3919 (class 2606 OID 3050105)
-- Name: tags tags_document_id_user_id_tag_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_document_id_user_id_tag_key UNIQUE (document_id, user_id, tag);


--
-- TOC entry 3921 (class 2606 OID 3050103)
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


--
-- TOC entry 3932 (class 2606 OID 8186778)
-- Name: unified_multiembeddings unified_multiembeddings_document_id_embed_source_id_chunk_n_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings
    ADD CONSTRAINT unified_multiembeddings_document_id_embed_source_id_chunk_n_key UNIQUE (document_id, embed_source_id, chunk_no, page_no, model_name);


--
-- TOC entry 3934 (class 2606 OID 8186776)
-- Name: unified_multiembeddings unified_multiembeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings
    ADD CONSTRAINT unified_multiembeddings_pkey PRIMARY KEY (id);


--
-- TOC entry 3886 (class 2606 OID 953761)
-- Name: user_interests user_interests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_interests
    ADD CONSTRAINT user_interests_pkey PRIMARY KEY (id);


--
-- TOC entry 3888 (class 2606 OID 953763)
-- Name: user_interests user_interests_user_id_interest_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_interests
    ADD CONSTRAINT user_interests_user_id_interest_key UNIQUE (user_id, interest);


--
-- TOC entry 3879 (class 2606 OID 953752)
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- TOC entry 3881 (class 2606 OID 953748)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- TOC entry 3883 (class 2606 OID 953750)
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- TOC entry 3936 (class 2606 OID 8276359)
-- Name: version version_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version
    ADD CONSTRAINT version_version_key UNIQUE (version);


--
-- TOC entry 3962 (class 1259 OID 56750459)
-- Name: chunks_chunktype_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX chunks_chunktype_id_idx ON public.chunks USING btree (chunktype_id);


--
-- TOC entry 3965 (class 1259 OID 56750460)
-- Name: chunks_document_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX chunks_document_id_idx ON public.chunks USING btree (document_id);


--
-- TOC entry 3980 (class 1259 OID 145200433)
-- Name: emb_1024_chunk_model_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX emb_1024_chunk_model_idx ON public.emb_1024 USING btree (chunk_id, model_id);


--
-- TOC entry 3973 (class 1259 OID 145200634)
-- Name: emb_768_chunk_model_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX emb_768_chunk_model_idx ON public.emb_768 USING btree (chunk_id, model_id);


--
-- TOC entry 3983 (class 1259 OID 63980979)
-- Name: hypotheses_hypothesis_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hypotheses_hypothesis_idx ON public.hypotheses USING gin (to_tsvector('english'::regconfig, hypothesis));


--
-- TOC entry 3956 (class 1259 OID 13027755)
-- Name: idx_bookmarks_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookmarks_document_id ON public.bookmarks USING btree (document_id);


--
-- TOC entry 3957 (class 1259 OID 13027757)
-- Name: idx_bookmarks_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookmarks_project_id ON public.bookmarks USING btree (project_id);


--
-- TOC entry 3958 (class 1259 OID 13027758)
-- Name: idx_bookmarks_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookmarks_type ON public.bookmarks USING btree (bookmark_type);


--
-- TOC entry 3959 (class 1259 OID 13027756)
-- Name: idx_bookmarks_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookmarks_user_id ON public.bookmarks USING btree (user_id);


--
-- TOC entry 3968 (class 1259 OID 33555518)
-- Name: idx_chunks_document_id_chunking_strategy_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chunks_document_id_chunking_strategy_id ON public.chunks USING btree (document_id, chunking_strategy_id);


--
-- TOC entry 3911 (class 1259 OID 14887175)
-- Name: idx_document_added_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_added_date ON public.document USING btree (added_date);


--
-- TOC entry 3912 (class 1259 OID 14856244)
-- Name: idx_document_publication_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_publication_date ON public.document USING btree (publication_date);


--
-- TOC entry 3913 (class 1259 OID 14888405)
-- Name: idx_document_updated_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_updated_date ON public.document USING btree (updated_date);


--
-- TOC entry 3998 (class 1259 OID 85920996)
-- Name: idx_eval_chunk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eval_chunk ON public.evaluations USING btree (chunk_id);


--
-- TOC entry 3999 (class 1259 OID 85920997)
-- Name: idx_eval_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eval_document ON public.evaluations USING btree (document_id);


--
-- TOC entry 4000 (class 1259 OID 85920998)
-- Name: idx_eval_evaluator; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eval_evaluator ON public.evaluations USING btree (evaluator_id);


--
-- TOC entry 4001 (class 1259 OID 85920999)
-- Name: idx_eval_llm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eval_llm ON public.evaluations USING btree (is_human_evaluator) WHERE (is_human_evaluator = false);


--
-- TOC entry 4002 (class 1259 OID 85920995)
-- Name: idx_eval_question; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eval_question ON public.evaluations USING btree (research_question_id);


--
-- TOC entry 4003 (class 1259 OID 85921000)
-- Name: idx_eval_question_doc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eval_question_doc ON public.evaluations USING btree (research_question_id, document_id);


--
-- TOC entry 3988 (class 1259 OID 63981030)
-- Name: idx_hypotheses_projects_hypothesis; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hypotheses_projects_hypothesis ON public.hypotheses_projects USING btree (hypothesis_id);


--
-- TOC entry 3989 (class 1259 OID 63981026)
-- Name: idx_hypotheses_projects_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hypotheses_projects_project ON public.hypotheses_projects USING btree (project_id);


--
-- TOC entry 4012 (class 1259 OID 104946946)
-- Name: idx_model_cap_junction_capability; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_cap_junction_capability ON public.model_capability_junction USING btree (capability_id);


--
-- TOC entry 4013 (class 1259 OID 104946945)
-- Name: idx_model_cap_junction_model; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_model_cap_junction_model ON public.model_capability_junction USING btree (model_id);


--
-- TOC entry 4006 (class 1259 OID 104946944)
-- Name: idx_models_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_models_name ON public.models USING btree (name);


--
-- TOC entry 4007 (class 1259 OID 104946943)
-- Name: idx_models_provider_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_models_provider_id ON public.models USING btree (provider_id);


--
-- TOC entry 3940 (class 1259 OID 12567779)
-- Name: idx_project_contributors_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_contributors_user_id ON public.project_contributors USING btree (user_id);


--
-- TOC entry 3937 (class 1259 OID 12567780)
-- Name: idx_projects_manager_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_manager_id ON public.projects USING btree (manager_id);


--
-- TOC entry 4016 (class 1259 OID 104946947)
-- Name: idx_prompts_model_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prompts_model_id ON public.prompts USING btree (model_id);


--
-- TOC entry 3992 (class 1259 OID 84271126)
-- Name: idx_prq_project_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prq_project_active ON public.project_research_questions USING btree (project_id) WHERE is_active;


--
-- TOC entry 3993 (class 1259 OID 84271127)
-- Name: idx_prq_question_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prq_question_active ON public.project_research_questions USING btree (question_id) WHERE is_active;


--
-- TOC entry 3893 (class 1259 OID 8277525)
-- Name: idx_reading_records_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_records_document_id ON public.reading_records USING btree (document_id);


--
-- TOC entry 3894 (class 1259 OID 986621)
-- Name: idx_reading_records_read_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_records_read_timestamp ON public.reading_records USING btree (read_timestamp);


--
-- TOC entry 3945 (class 1259 OID 12865561)
-- Name: idx_reading_suggestions_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_suggestions_document_id ON public.reading_suggestions USING btree (document_id);


--
-- TOC entry 3946 (class 1259 OID 12865563)
-- Name: idx_reading_suggestions_evaluator_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_suggestions_evaluator_id ON public.reading_suggestions USING btree (evaluator_id);


--
-- TOC entry 3947 (class 1259 OID 12865564)
-- Name: idx_reading_suggestions_recommendation_strength; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_suggestions_recommendation_strength ON public.reading_suggestions USING btree (recommendation_strength);


--
-- TOC entry 3948 (class 1259 OID 12865565)
-- Name: idx_reading_suggestions_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_reading_suggestions_unique ON public.reading_suggestions USING btree (document_id, user_id, evaluator_id);


--
-- TOC entry 3949 (class 1259 OID 12865562)
-- Name: idx_reading_suggestions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_suggestions_user_id ON public.reading_suggestions USING btree (user_id);


--
-- TOC entry 3871 (class 1259 OID 8277531)
-- Name: idx_summaries_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_summaries_document_id ON public.summaries USING btree (document_id);


--
-- TOC entry 3926 (class 1259 OID 8186792)
-- Name: idx_unified_multiembeddings_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_created_at ON public.unified_multiembeddings USING btree (created_at);


--
-- TOC entry 3927 (class 1259 OID 8186789)
-- Name: idx_unified_multiembeddings_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_document_id ON public.unified_multiembeddings USING btree (document_id);


--
-- TOC entry 3928 (class 1259 OID 8186790)
-- Name: idx_unified_multiembeddings_embed_source_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_embed_source_id ON public.unified_multiembeddings USING btree (embed_source_id);


--
-- TOC entry 3929 (class 1259 OID 8186793)
-- Name: idx_unified_multiembeddings_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_embedding ON public.unified_multiembeddings USING ivfflat (embedding public.vector_cosine_ops);


--
-- TOC entry 3930 (class 1259 OID 8186791)
-- Name: idx_unified_multiembeddings_model_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_model_name ON public.unified_multiembeddings USING btree (model_name);


--
-- TOC entry 3884 (class 1259 OID 953769)
-- Name: idx_user_interests_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_interests_user_id ON public.user_interests USING btree (user_id);


--
-- TOC entry 4055 (class 2620 OID 85920994)
-- Name: evaluations trg_update_eval_version; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_update_eval_version BEFORE UPDATE ON public.evaluations FOR EACH ROW EXECUTE FUNCTION public.trg_bump_version_and_timestamp();


--
-- TOC entry 4054 (class 2620 OID 84271129)
-- Name: project_research_questions trg_update_prq_status; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_update_prq_status BEFORE UPDATE ON public.project_research_questions FOR EACH ROW EXECUTE FUNCTION public.trg_update_timestamp_on_status_change();


--
-- TOC entry 4053 (class 2620 OID 9147951)
-- Name: document update_all_keywords_before_ins_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_all_keywords_before_ins_upd BEFORE INSERT OR UPDATE ON public.document FOR EACH ROW EXECUTE FUNCTION public.update_all_keywords_trigger();


--
-- TOC entry 4038 (class 2606 OID 13027740)
-- Name: bookmarks bookmarks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT bookmarks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- TOC entry 4039 (class 2606 OID 13027750)
-- Name: bookmarks bookmarks_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT bookmarks_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- TOC entry 4040 (class 2606 OID 13027745)
-- Name: bookmarks bookmarks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT bookmarks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 4024 (class 2606 OID 3050066)
-- Name: document document_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- TOC entry 4026 (class 2606 OID 3050085)
-- Name: document_keywords document_keywords_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- TOC entry 4027 (class 2606 OID 3050090)
-- Name: document_keywords document_keywords_keyword_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_keyword_fkey FOREIGN KEY (keyword) REFERENCES public.keywords(keyword) ON DELETE CASCADE;


--
-- TOC entry 4025 (class 2606 OID 3050061)
-- Name: document document_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- TOC entry 4045 (class 2606 OID 85920983)
-- Name: evaluations evaluations_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.chunks(id);


--
-- TOC entry 4046 (class 2606 OID 85920988)
-- Name: evaluations evaluations_evaluator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_evaluator_id_fkey FOREIGN KEY (evaluator_id) REFERENCES public.evaluators(id);


--
-- TOC entry 4047 (class 2606 OID 85920978)
-- Name: evaluations evaluations_research_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_research_question_id_fkey FOREIGN KEY (research_question_id) REFERENCES public.research_questions(id);


--
-- TOC entry 4034 (class 2606 OID 12865289)
-- Name: evaluators evaluators_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluators
    ADD CONSTRAINT evaluators_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- TOC entry 4041 (class 2606 OID 63980993)
-- Name: hypotheses_projects hypotheses_projects_hypothesis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hypotheses_projects
    ADD CONSTRAINT hypotheses_projects_hypothesis_id_fkey FOREIGN KEY (hypothesis_id) REFERENCES public.hypotheses(id) ON DELETE CASCADE;


--
-- TOC entry 4042 (class 2606 OID 63980988)
-- Name: hypotheses_projects hypotheses_projects_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hypotheses_projects
    ADD CONSTRAINT hypotheses_projects_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- TOC entry 4049 (class 2606 OID 104946918)
-- Name: model_capability_junction model_capability_junction_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_capability_junction
    ADD CONSTRAINT model_capability_junction_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.model_capabilities(id);


--
-- TOC entry 4050 (class 2606 OID 104946913)
-- Name: model_capability_junction model_capability_junction_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_capability_junction
    ADD CONSTRAINT model_capability_junction_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id);


--
-- TOC entry 4048 (class 2606 OID 104946893)
-- Name: models models_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.models
    ADD CONSTRAINT models_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.model_providers(id);


--
-- TOC entry 4032 (class 2606 OID 12567769)
-- Name: project_contributors project_contributors_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_contributors
    ADD CONSTRAINT project_contributors_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- TOC entry 4033 (class 2606 OID 12567774)
-- Name: project_contributors project_contributors_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_contributors
    ADD CONSTRAINT project_contributors_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 4043 (class 2606 OID 84271116)
-- Name: project_research_questions project_research_questions_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_research_questions
    ADD CONSTRAINT project_research_questions_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- TOC entry 4044 (class 2606 OID 84271121)
-- Name: project_research_questions project_research_questions_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_research_questions
    ADD CONSTRAINT project_research_questions_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.research_questions(id) ON DELETE CASCADE;


--
-- TOC entry 4031 (class 2606 OID 12567759)
-- Name: projects projects_manager_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 4051 (class 2606 OID 104946938)
-- Name: prompts prompts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompts
    ADD CONSTRAINT prompts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- TOC entry 4052 (class 2606 OID 104946933)
-- Name: prompts prompts_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompts
    ADD CONSTRAINT prompts_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id);


--
-- TOC entry 4021 (class 2606 OID 8277520)
-- Name: reading_records reading_records_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records
    ADD CONSTRAINT reading_records_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- TOC entry 4022 (class 2606 OID 986609)
-- Name: reading_records_tags reading_records_tags_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records_tags
    ADD CONSTRAINT reading_records_tags_record_id_fkey FOREIGN KEY (record_id) REFERENCES public.reading_records(id) ON DELETE CASCADE;


--
-- TOC entry 4023 (class 2606 OID 986614)
-- Name: reading_records_tags reading_records_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records_tags
    ADD CONSTRAINT reading_records_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.reading_tags(id) ON DELETE CASCADE;


--
-- TOC entry 4035 (class 2606 OID 12865546)
-- Name: reading_suggestions reading_suggestions_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_suggestions
    ADD CONSTRAINT reading_suggestions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id);


--
-- TOC entry 4036 (class 2606 OID 12865556)
-- Name: reading_suggestions reading_suggestions_evaluator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_suggestions
    ADD CONSTRAINT reading_suggestions_evaluator_id_fkey FOREIGN KEY (evaluator_id) REFERENCES public.evaluators(id);


--
-- TOC entry 4037 (class 2606 OID 12865551)
-- Name: reading_suggestions reading_suggestions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_suggestions
    ADD CONSTRAINT reading_suggestions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- TOC entry 4019 (class 2606 OID 8277526)
-- Name: summaries summaries_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.summaries
    ADD CONSTRAINT summaries_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- TOC entry 4028 (class 2606 OID 3050106)
-- Name: tags tags_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- TOC entry 4029 (class 2606 OID 8186779)
-- Name: unified_multiembeddings unified_multiembeddings_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings
    ADD CONSTRAINT unified_multiembeddings_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- TOC entry 4030 (class 2606 OID 8186784)
-- Name: unified_multiembeddings unified_multiembeddings_embed_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings
    ADD CONSTRAINT unified_multiembeddings_embed_source_id_fkey FOREIGN KEY (embed_source_id) REFERENCES public.embedding_source(id) ON DELETE CASCADE;


--
-- TOC entry 4020 (class 2606 OID 953764)
-- Name: user_interests user_interests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_interests
    ADD CONSTRAINT user_interests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


-- Completed on 2025-05-19 23:18:50 AEST

--
-- PostgreSQL database dump complete
--

