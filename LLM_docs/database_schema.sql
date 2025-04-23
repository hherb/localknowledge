-- Medical Literature Database Schema

-- Core Tables
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  firstname TEXT,
  surname TEXT,
  email TEXT UNIQUE NOT NULL,
  pwdhash TEXT NOT NULL
);

CREATE TABLE sources (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  url TEXT,
  is_reputable BOOLEAN DEFAULT FALSE,
  is_free BOOLEAN DEFAULT TRUE
);

CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT
);

CREATE TABLE document (
  id INTEGER PRIMARY KEY,
  source_id INTEGER REFERENCES sources(id),
  external_id TEXT NOT NULL,
  doi TEXT,
  title TEXT,
  abstract TEXT,
  category_id INTEGER REFERENCES categories(id),
  keywords TEXT[],
  augmented_keywords TEXT[],
  mesh_terms TEXT[],
  authors TEXT[],
  publication TEXT,
  publication_date DATE,
  url TEXT,
  pdf_url TEXT,
  pdf_filename TEXT,
  full_text TEXT,
  added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  withdrawn_date TIMESTAMP,
  withdrawn_reason TEXT,
  UNIQUE(source_id, external_id)
);

-- Keyword Management
CREATE TABLE keywords (
  keyword TEXT PRIMARY KEY
);

CREATE TABLE document_keywords (
  document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
  keyword TEXT REFERENCES keywords(keyword) ON DELETE CASCADE,
  PRIMARY KEY (document_id, keyword)
);

-- Vector Storage
CREATE TABLE embedding_source (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE unified_multiembeddings (
  id INTEGER PRIMARY KEY,
  document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
  embed_source_id INTEGER REFERENCES embedding_source(id) ON DELETE CASCADE,
  chunk_no INTEGER,
  page_no INTEGER,
  text TEXT,
  keywords TEXT[],
  embedding VECTOR(1024),
  model_name TEXT,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(document_id, embed_source_id, chunk_no, page_no, model_name)
);

-- Reading Tracking
CREATE TABLE reading_records (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  read_timestamp TIMESTAMP,
  rating INTEGER,
  notes TEXT,
  document_id INTEGER REFERENCES document(id) ON DELETE CASCADE
);

CREATE TABLE reading_tags (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE reading_records_tags (
  record_id INTEGER REFERENCES reading_records(id) ON DELETE CASCADE,
  tag_id INTEGER REFERENCES reading_tags(id) ON DELETE CASCADE,
  PRIMARY KEY (record_id, tag_id)
);

-- User Tagging System
CREATE TABLE tags (
  id INTEGER PRIMARY KEY,
  document_id INTEGER REFERENCES document(id) ON DELETE CASCADE,
  user_id INTEGER,
  tag TEXT NOT NULL,
  UNIQUE(document_id, user_id, tag)
);

CREATE TABLE user_interests (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  interest TEXT NOT NULL,
  UNIQUE(user_id, interest)
);

-- Document Summaries
CREATE TABLE summaries (
  id INTEGER PRIMARY KEY,
  summary TEXT,
  evaluation BOOLEAN,
  reason TEXT,
  interests TEXT[],
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE
);

-- PubMed Download Tracking
CREATE TABLE pubmed_download_log (
  id INTEGER PRIMARY KEY,
  file_name VARCHAR(255) UNIQUE NOT NULL,
  file_type VARCHAR(50) NOT NULL,
  download_date TIMESTAMP NOT NULL,
  processed BOOLEAN DEFAULT FALSE,
  process_date TIMESTAMP,
  file_size BIGINT,
  checksum VARCHAR(64),
  status VARCHAR(20) DEFAULT 'downloaded'
);

-- Schema Version Control
CREATE TABLE version (
  version INTEGER UNIQUE NOT NULL,
  migrated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  migration_success BOOLEAN NOT NULL
);

-- Key Indexes (simplified)
CREATE INDEX idx_unified_multiembeddings_embedding ON unified_multiembeddings USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_unified_multiembeddings_document_id ON unified_multiembeddings(document_id);
CREATE INDEX idx_summaries_document_id ON summaries(document_id);
CREATE INDEX idx_reading_records_document_id ON reading_records(document_id);
CREATE INDEX idx_user_interests_user_id ON user_interests(user_id);
