## Database Tables

### User Management
```sql
CREATE TABLE users (
  id integer NOT NULL,
  username text NOT NULL,
  firstname text,
  surname text,
  email text NOT NULL,
  pwdhash text NOT NULL
);

CREATE TABLE user_interests (
  id integer NOT NULL,
  user_id integer,
  interest text NOT NULL
);
```

### Document Management
```sql
CREATE TABLE sources (
  id integer NOT NULL,
  name text NOT NULL,
  url text,
  is_reputable boolean DEFAULT false,
  is_free boolean DEFAULT true
);

CREATE TABLE categories (
  id integer NOT NULL,
  name text NOT NULL,
  description text
);

CREATE TABLE document (
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

CREATE TABLE document_keywords (
  document_id integer NOT NULL,
  keyword text NOT NULL
);

CREATE TABLE keywords (
  keyword text NOT NULL
);

CREATE TABLE tags (
  id integer NOT NULL,
  document_id integer,
  user_id integer,
  tag text NOT NULL
);

CREATE TABLE summaries (
  id integer NOT NULL,
  summary text,
  evaluation boolean,
  reason text,
  interests text[],
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  document_id integer NOT NULL
);

CREATE TABLE bookmarks (
  id integer NOT NULL,
  document_id integer NOT NULL,
  user_id integer NOT NULL,
  project_id integer,
  bookmark_type text NOT NULL,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT bookmarks_bookmark_type_check CHECK ((bookmark_type = ANY (ARRAY['personal'::text, 'project'::text, 'both'::text])))
);
```

### Document Chunking and Embedding
```sql
CREATE TABLE chunking_strategies (
  id integer NOT NULL,
  strategy_name text NOT NULL,
  modelname text,
  parameters jsonb
);

CREATE TABLE chunktypes (
  id integer NOT NULL,
  chunktype text NOT NULL
);

CREATE TABLE chunks (
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

CREATE TABLE embedding_base (
  id integer NOT NULL,
  chunk_id integer NOT NULL,
  model_id integer
);

CREATE TABLE emb_768 (
  embedding vector(768)
) INHERITS (embedding_base);

CREATE TABLE emb_1024 (
  embedding vector(1024)
) INHERITS (embedding_base);

CREATE TABLE embedding_models (
  id integer NOT NULL,
  provider_id integer,
  model_name text NOT NULL,
  model_description text,
  model_parameters jsonb
);

CREATE TABLE embedding_provider (
  id integer NOT NULL,
  provider_name text NOT NULL,
  base_url text
);

CREATE TABLE embedding_source (
  id integer NOT NULL,
  name text NOT NULL,
  description text,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE unified_multiembeddings (
  id integer NOT NULL,
  document_id integer,
  embed_source_id integer,
  chunk_no integer,
  page_no integer,
  text text,
  keywords text[],
  embedding vector(1024),
  model_name text,
  metadata jsonb,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);
```

### Reading Records and Recommendations
```sql
CREATE TABLE reading_records (
  id integer NOT NULL,
  user_id integer,
  read_timestamp timestamp without time zone,
  rating integer,
  notes text,
  document_id integer
);

CREATE TABLE reading_tags (
  id integer NOT NULL,
  name text NOT NULL
);

CREATE TABLE reading_records_tags (
  record_id integer NOT NULL,
  tag_id integer NOT NULL
);

CREATE TABLE evaluators (
  id integer NOT NULL,
  name text NOT NULL,
  user_id integer,
  model_id text,
  parameters jsonb,
  prompt text,
  created_at timestamp without time zone DEFAULT now(),
  updated_at timestamp without time zone DEFAULT now()
);

CREATE TABLE reading_suggestions (
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
  CONSTRAINT reading_suggestions_recommendation_strength_check CHECK (recommendation_strength >= 0 AND recommendation_strength <= 5)
);
```

### Research and Projects
```sql
CREATE TABLE projects (
  id integer NOT NULL,
  title text NOT NULL,
  description text,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  last_worked_on timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  manager_id integer
);

CREATE TABLE project_contributors (
  project_id integer NOT NULL,
  user_id integer NOT NULL
);

CREATE TABLE research_questions (
  id integer NOT NULL,
  question text NOT NULL,
  details text
);

CREATE TABLE project_research_questions (
  project_id integer NOT NULL,
  question_id integer NOT NULL,
  is_active boolean DEFAULT true NOT NULL,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hypotheses (
  id integer NOT NULL,
  hypothesis text NOT NULL,
  counterhypothesis text,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hypotheses_projects (
  project_id integer NOT NULL,
  hypothesis_id integer NOT NULL
);

CREATE TABLE evaluations (
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
  CONSTRAINT evaluations_confidence_level_check CHECK (confidence_level >= 0.0 AND confidence_level <= 1.0)
);
```

### Models and AI
```sql
CREATE TABLE model_providers (
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

CREATE TABLE models (
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

CREATE TABLE model_capabilities (
  id integer NOT NULL,
  name text NOT NULL,
  description text,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE model_capability_junction (
  model_id integer NOT NULL,
  capability_id integer NOT NULL
);

CREATE TABLE prompts (
  id integer NOT NULL,
  model_id integer,
  prompt text NOT NULL,
  purpose text,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  created_by integer
);
```

### Utility Tables
```sql
CREATE TABLE pubmed_download_log (
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

CREATE TABLE version (
  version integer NOT NULL,
  migrated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  migration_success boolean NOT NULL
);
```

## Key Relationships

### Document Relations
```sql
ALTER TABLE document ADD CONSTRAINT document_source_id_fkey FOREIGN KEY (source_id) REFERENCES sources(id);
ALTER TABLE document ADD CONSTRAINT document_category_id_fkey FOREIGN KEY (category_id) REFERENCES categories(id);

ALTER TABLE document_keywords ADD CONSTRAINT document_keywords_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE;
ALTER TABLE document_keywords ADD CONSTRAINT document_keywords_keyword_fkey FOREIGN KEY (keyword) REFERENCES keywords(keyword) ON DELETE CASCADE;

ALTER TABLE summaries ADD CONSTRAINT summaries_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE;
ALTER TABLE tags ADD CONSTRAINT tags_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE;
```

### Chunk and Embedding Relations
```sql
ALTER TABLE chunks ADD CONSTRAINT chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id);
ALTER TABLE embedding_base ADD CONSTRAINT embedding_base_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES chunks(id);

ALTER TABLE unified_multiembeddings ADD CONSTRAINT unified_multiembeddings_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE;
ALTER TABLE unified_multiembeddings ADD CONSTRAINT unified_multiembeddings_embed_source_id_fkey FOREIGN KEY (embed_source_id) REFERENCES embedding_source(id) ON DELETE CASCADE;
```

### User Relations
```sql
ALTER TABLE user_interests ADD CONSTRAINT user_interests_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE tags ADD CONSTRAINT tags_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id);
ALTER TABLE reading_records ADD CONSTRAINT reading_records_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id);
ALTER TABLE evaluators ADD CONSTRAINT evaluators_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id);
```

### Project Relations
```sql
ALTER TABLE projects ADD CONSTRAINT projects_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE project_contributors ADD CONSTRAINT project_contributors_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE project_contributors ADD CONSTRAINT project_contributors_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE project_research_questions ADD CONSTRAINT project_research_questions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE project_research_questions ADD CONSTRAINT project_research_questions_question_id_fkey FOREIGN KEY (question_id) REFERENCES research_questions(id) ON DELETE CASCADE;

ALTER TABLE hypotheses_projects ADD CONSTRAINT hypotheses_projects_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE hypotheses_projects ADD CONSTRAINT hypotheses_projects_hypothesis_id_fkey FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(id) ON DELETE CASCADE;
```

### Evaluation Relations
```sql
ALTER TABLE evaluations ADD CONSTRAINT evaluations_research_question_id_fkey FOREIGN KEY (research_question_id) REFERENCES research_questions(id);
ALTER TABLE evaluations ADD CONSTRAINT evaluations_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES chunks(id);
ALTER TABLE evaluations ADD CONSTRAINT evaluations_evaluator_id_fkey FOREIGN KEY (evaluator_id) REFERENCES evaluators(id);
ALTER TABLE evaluations ADD CONSTRAINT evaluations_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id);
```

### Model Relations
```sql
ALTER TABLE models ADD CONSTRAINT models_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES model_providers(id);
ALTER TABLE model_capability_junction ADD CONSTRAINT model_capability_junction_model_id_fkey FOREIGN KEY (model_id) REFERENCES models(id);
ALTER TABLE model_capability_junction ADD CONSTRAINT model_capability_junction_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES model_capabilities(id);
ALTER TABLE prompts ADD CONSTRAINT prompts_model_id_fkey FOREIGN KEY (model_id) REFERENCES models(id);
ALTER TABLE prompts ADD CONSTRAINT prompts_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id);
```

### Bookmark Relations
```sql
ALTER TABLE bookmarks ADD CONSTRAINT bookmarks_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE;
ALTER TABLE bookmarks ADD CONSTRAINT bookmarks_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE bookmarks ADD CONSTRAINT bookmarks_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
```

### Reading Relations
```sql
ALTER TABLE reading_records ADD CONSTRAINT reading_records_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE;
ALTER TABLE reading_records_tags ADD CONSTRAINT reading_records_tags_record_id_fkey FOREIGN KEY (record_id) REFERENCES reading_records(id) ON DELETE CASCADE;
ALTER TABLE reading_records_tags ADD CONSTRAINT reading_records_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES reading_tags(id) ON DELETE CASCADE;

ALTER TABLE reading_suggestions ADD CONSTRAINT reading_suggestions_document_id_fkey FOREIGN KEY (document_id) REFERENCES document(id);
ALTER TABLE reading_suggestions ADD CONSTRAINT reading_suggestions_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id);
ALTER TABLE reading_suggestions ADD CONSTRAINT reading_suggestions_evaluator_id_fkey FOREIGN KEY (evaluator_id) REFERENCES evaluators(id);
```
