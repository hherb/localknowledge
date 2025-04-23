--
-- PostgreSQL database dump
--

-- Dumped from database version 16.8 (Postgres.app)
-- Dumped by pg_dump version 16.8 (Postgres.app)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    name text NOT NULL,
    description text
);


--
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
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
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
    withdrawn_reason text
);


--
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
-- Name: document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.document_id_seq OWNED BY public.document.id;


--
-- Name: document_keywords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_keywords (
    document_id integer NOT NULL,
    keyword text NOT NULL
);


--
-- Name: embedding_source; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.embedding_source (
    id integer NOT NULL,
    name text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
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
-- Name: embedding_source_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.embedding_source_id_seq OWNED BY public.embedding_source.id;


--
-- Name: keywords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.keywords (
    keyword text NOT NULL
);


--
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
-- Name: pubmed_download_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pubmed_download_log_id_seq OWNED BY public.pubmed_download_log.id;


--
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
-- Name: reading_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reading_records_id_seq OWNED BY public.reading_records.id;


--
-- Name: reading_records_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reading_records_tags (
    record_id integer NOT NULL,
    tag_id integer NOT NULL
);


--
-- Name: reading_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reading_tags (
    id integer NOT NULL,
    name text NOT NULL
);


--
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
-- Name: reading_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reading_tags_id_seq OWNED BY public.reading_tags.id;


--
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
-- Name: sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sources_id_seq OWNED BY public.sources.id;


--
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
-- Name: summaries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.summaries_id_seq OWNED BY public.summaries.id;


--
-- Name: tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tags (
    id integer NOT NULL,
    document_id integer,
    user_id integer,
    tag text NOT NULL
);


--
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
-- Name: tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tags_id_seq OWNED BY public.tags.id;


--
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
-- Name: unified_multiembeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unified_multiembeddings_id_seq OWNED BY public.unified_multiembeddings.id;


--
-- Name: user_interests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_interests (
    id integer NOT NULL,
    user_id integer,
    interest text NOT NULL
);


--
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
-- Name: user_interests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_interests_id_seq OWNED BY public.user_interests.id;


--
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
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.version (
    version integer NOT NULL,
    migrated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    migration_success boolean NOT NULL
);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: document id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document ALTER COLUMN id SET DEFAULT nextval('public.document_id_seq'::regclass);


--
-- Name: embedding_source id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_source ALTER COLUMN id SET DEFAULT nextval('public.embedding_source_id_seq'::regclass);


--
-- Name: pubmed_download_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pubmed_download_log ALTER COLUMN id SET DEFAULT nextval('public.pubmed_download_log_id_seq'::regclass);


--
-- Name: reading_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records ALTER COLUMN id SET DEFAULT nextval('public.reading_records_id_seq'::regclass);


--
-- Name: reading_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_tags ALTER COLUMN id SET DEFAULT nextval('public.reading_tags_id_seq'::regclass);


--
-- Name: sources id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources ALTER COLUMN id SET DEFAULT nextval('public.sources_id_seq'::regclass);


--
-- Name: summaries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.summaries ALTER COLUMN id SET DEFAULT nextval('public.summaries_id_seq'::regclass);


--
-- Name: tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags ALTER COLUMN id SET DEFAULT nextval('public.tags_id_seq'::regclass);


--
-- Name: unified_multiembeddings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings ALTER COLUMN id SET DEFAULT nextval('public.unified_multiembeddings_id_seq'::regclass);


--
-- Name: user_interests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_interests ALTER COLUMN id SET DEFAULT nextval('public.user_interests_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: categories categories_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_name_key UNIQUE (name);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: document_keywords document_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_pkey PRIMARY KEY (document_id, keyword);


--
-- Name: document document_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_pkey PRIMARY KEY (id);


--
-- Name: document document_source_id_external_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_source_id_external_id_key UNIQUE (source_id, external_id);


--
-- Name: embedding_source embedding_source_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_source
    ADD CONSTRAINT embedding_source_name_key UNIQUE (name);


--
-- Name: embedding_source embedding_source_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.embedding_source
    ADD CONSTRAINT embedding_source_pkey PRIMARY KEY (id);


--
-- Name: keywords keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.keywords
    ADD CONSTRAINT keywords_pkey PRIMARY KEY (keyword);


--
-- Name: pubmed_download_log pubmed_download_log_file_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pubmed_download_log
    ADD CONSTRAINT pubmed_download_log_file_name_key UNIQUE (file_name);


--
-- Name: pubmed_download_log pubmed_download_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pubmed_download_log
    ADD CONSTRAINT pubmed_download_log_pkey PRIMARY KEY (id);


--
-- Name: reading_records reading_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records
    ADD CONSTRAINT reading_records_pkey PRIMARY KEY (id);


--
-- Name: reading_records_tags reading_records_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records_tags
    ADD CONSTRAINT reading_records_tags_pkey PRIMARY KEY (record_id, tag_id);


--
-- Name: reading_tags reading_tags_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_tags
    ADD CONSTRAINT reading_tags_name_key UNIQUE (name);


--
-- Name: reading_tags reading_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_tags
    ADD CONSTRAINT reading_tags_pkey PRIMARY KEY (id);


--
-- Name: sources sources_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_name_key UNIQUE (name);


--
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (id);


--
-- Name: summaries summaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.summaries
    ADD CONSTRAINT summaries_pkey PRIMARY KEY (id);


--
-- Name: tags tags_document_id_user_id_tag_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_document_id_user_id_tag_key UNIQUE (document_id, user_id, tag);


--
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


--
-- Name: unified_multiembeddings unified_multiembeddings_document_id_embed_source_id_chunk_n_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings
    ADD CONSTRAINT unified_multiembeddings_document_id_embed_source_id_chunk_n_key UNIQUE (document_id, embed_source_id, chunk_no, page_no, model_name);


--
-- Name: unified_multiembeddings unified_multiembeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings
    ADD CONSTRAINT unified_multiembeddings_pkey PRIMARY KEY (id);


--
-- Name: user_interests user_interests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_interests
    ADD CONSTRAINT user_interests_pkey PRIMARY KEY (id);


--
-- Name: user_interests user_interests_user_id_interest_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_interests
    ADD CONSTRAINT user_interests_user_id_interest_key UNIQUE (user_id, interest);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: version version_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version
    ADD CONSTRAINT version_version_key UNIQUE (version);


--
-- Name: idx_reading_records_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_records_document_id ON public.reading_records USING btree (document_id);


--
-- Name: idx_reading_records_read_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_records_read_timestamp ON public.reading_records USING btree (read_timestamp);


--
-- Name: idx_summaries_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_summaries_document_id ON public.summaries USING btree (document_id);


--
-- Name: idx_unified_multiembeddings_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_created_at ON public.unified_multiembeddings USING btree (created_at);


--
-- Name: idx_unified_multiembeddings_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_document_id ON public.unified_multiembeddings USING btree (document_id);


--
-- Name: idx_unified_multiembeddings_embed_source_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_embed_source_id ON public.unified_multiembeddings USING btree (embed_source_id);


--
-- Name: idx_unified_multiembeddings_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_embedding ON public.unified_multiembeddings USING ivfflat (embedding public.vector_cosine_ops);


--
-- Name: idx_unified_multiembeddings_model_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_multiembeddings_model_name ON public.unified_multiembeddings USING btree (model_name);


--
-- Name: idx_user_interests_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_interests_user_id ON public.user_interests USING btree (user_id);


--
-- Name: document document_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: document_keywords document_keywords_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- Name: document_keywords document_keywords_keyword_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_keywords
    ADD CONSTRAINT document_keywords_keyword_fkey FOREIGN KEY (keyword) REFERENCES public.keywords(keyword) ON DELETE CASCADE;


--
-- Name: document document_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: reading_records reading_records_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records
    ADD CONSTRAINT reading_records_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- Name: reading_records_tags reading_records_tags_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records_tags
    ADD CONSTRAINT reading_records_tags_record_id_fkey FOREIGN KEY (record_id) REFERENCES public.reading_records(id) ON DELETE CASCADE;


--
-- Name: reading_records_tags reading_records_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_records_tags
    ADD CONSTRAINT reading_records_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.reading_tags(id) ON DELETE CASCADE;


--
-- Name: summaries summaries_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.summaries
    ADD CONSTRAINT summaries_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- Name: tags tags_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- Name: unified_multiembeddings unified_multiembeddings_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings
    ADD CONSTRAINT unified_multiembeddings_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id) ON DELETE CASCADE;


--
-- Name: unified_multiembeddings unified_multiembeddings_embed_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_multiembeddings
    ADD CONSTRAINT unified_multiembeddings_embed_source_id_fkey FOREIGN KEY (embed_source_id) REFERENCES public.embedding_source(id) ON DELETE CASCADE;


--
-- Name: user_interests user_interests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_interests
    ADD CONSTRAINT user_interests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

