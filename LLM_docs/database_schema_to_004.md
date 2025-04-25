# Database Schema Summary

## Core Tables
- **users**: User accounts
  - id (serial, PK)
  - username (text, UNIQUE)
  - firstname (text)
  - surname (text)
  - email (text, UNIQUE)
  - pwdhash (text)
- **document**: Research documents
  - id (serial, PK)
  - source_id (integer, FK → sources.id)
  - external_id (text, UNIQUE with source_id)
  - doi (text)
  - title (text)
  - abstract (text)
  - category_id (integer, FK → categories.id)
  - keywords (text[])
  - augmented_keywords (text[])
  - mesh_terms (text[])
  - authors (text[])
  - publication (text)
  - publication_date (date)
  - url (text)
  - pdf_url (text)
  - pdf_filename (text)
  - full_text (text)
  - added_date (timestamp, DEFAULT CURRENT_TIMESTAMP)
  - updated_date (timestamp, DEFAULT CURRENT_TIMESTAMP)
  - withdrawn_date (timestamp)
  - withdrawn_reason (text)
  - all_keywords (text[])
- **sources**: Document origins
  - id (serial, PK)
  - name (text, UNIQUE)
  - url (text)
  - is_reputable (boolean, DEFAULT false)
  - is_free (boolean, DEFAULT true)
- **categories**: Document classifications
  - id (serial, PK)
  - name (text, UNIQUE)
  - description (text)

## Reading System
- **reading_records**: User's document readings
  - id (serial, PK)
  - user_id (integer, FK → users.id)
  - document_id (integer, FK → document.id)
  - read_timestamp (timestamp)
  - rating (integer)
  - notes (text)
- **reading_tags**: Reusable tags for readings
  - id (serial, PK)
  - name (text, UNIQUE)
- **reading_records_tags**: Many-to-many relation
  - record_id (integer, PK, FK → reading_records.id)
  - tag_id (integer, PK, FK → reading_tags.id)
- **tags**: User-specific document tags
  - id (serial, PK)
  - document_id (integer, FK → document.id)
  - user_id (integer, FK → users.id)
  - tag (text)
  - UNIQUE(document_id, user_id, tag)
- **reading_suggestions**: AI-generated recommendations
  - id (serial, PK)
  - document_id (integer, FK → document.id)
  - user_id (integer, FK → users.id)
  - evaluator_id (integer, FK → evaluators.id)
  - recommendation_strength (integer)
  - confidence_level (double precision)
  - comment (text)
  - user_agreement (boolean)
  - created_at (timestamp, DEFAULT now())
  - updated_at (timestamp, DEFAULT now())

## AI & ML Components
- **evaluators**: Models for generating recommendations
  - id (serial, PK)
  - name (text)
  - user_id (integer, FK → users.id)
  - model_id (text)
  - parameters (jsonb)
  - prompt (text)
  - created_at (timestamp, DEFAULT now())
  - updated_at (timestamp, DEFAULT now())
- **summaries**: Document summaries
  - id (serial, PK)
  - document_id (integer, FK → document.id)
  - summary (text)
  - evaluation (boolean)
  - reason (text)
  - interests (text[])
  - created_at (timestamp, DEFAULT CURRENT_TIMESTAMP)
- **unified_multiembeddings**: Vector embeddings
  - id (serial, PK)
  - document_id (integer, FK → document.id)
  - embed_source_id (integer, FK → embedding_source.id)
  - chunk_no (integer)
  - page_no (integer)
  - text (text)
  - keywords (text[])
  - embedding (vector)
  - model_name (text)
  - metadata (jsonb)
  - created_at (timestamp with time zone, DEFAULT CURRENT_TIMESTAMP)
  - UNIQUE(document_id, embed_source_id, chunk_no, page_no, model_name)
- **embedding_source**: Sources for embeddings
  - id (serial, PK)
  - name (text, UNIQUE)
  - description (text)
  - created_at (timestamp with time zone, DEFAULT CURRENT_TIMESTAMP)

## Project Management
- **projects**: Research projects
  - id (serial, PK)
  - title (text)
  - description (text)
  - created_at (timestamp, DEFAULT CURRENT_TIMESTAMP)
  - last_worked_on (timestamp, DEFAULT CURRENT_TIMESTAMP)
  - manager_id (integer, FK → users.id)
- **project_contributors**: Many-to-many user-project relation
  - project_id (integer, PK, FK → projects.id)
  - user_id (integer, PK, FK → users.id)

## Keywords & Interests
- **keywords**: Unique keywords
  - keyword (text, PK)
- **document_keywords**: Many-to-many relation
  - document_id (integer, PK, FK → document.id)
  - keyword (text, PK, FK → keywords.keyword)
- **user_interests**: User interests
  - id (serial, PK)
  - user_id (integer, FK → users.id)
  - interest (text)
  - UNIQUE(user_id, interest)

## Maintenance
- **pubmed_download_log**: Track PubMed data imports
  - id (serial, PK)
  - file_name (character varying(255), UNIQUE)
  - file_type (character varying(50))
  - download_date (timestamp)
  - processed (boolean, DEFAULT false)
  - process_date (timestamp)
  - file_size (bigint)
  - checksum (character varying(64))
  - status (character varying(20), DEFAULT 'downloaded')
- **version**: Database version tracking
  - version (integer, UNIQUE)
  - migrated (timestamp with time zone, DEFAULT CURRENT_TIMESTAMP)
  - migration_success (boolean)

## Key Relationships
1. Document → Source (source_id → id)
2. Document → Category (category_id → id)
3. Reading Records → Document (document_id → id)
4. Reading Records → User (user_id → id)
5. Reading Suggestions → Document, User, Evaluator
6. Unified Multiembeddings → Document, Embedding Source
7. Projects → User (manager_id → id)
8. Document Keywords → Document, Keywords
9. User Interests → User
10. Tags → Document, User

## Indices
- Indices on foreign keys for reading_records, reading_suggestions, summaries, unified_multiembeddings
- Project management indices on projects.manager_id and project_contributors.user_id
- User interest index on user_interests.user_id