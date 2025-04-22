CREATE TABLE sources(
    id serial primary key,
    name text,
    url text,
    is_reputable boolean default False,
    is_free boolean default True
)

insert into sources(name, url, is_reputable, is_free) 
values('pubmed', 'https://pubmed.ncbi.nlm.nih.gov/', True, True);

insert into sources(name, url, is_reputable, is_free) 
values('medrxiv', 'https://www.medrxiv.org/', True, True);

CREATE TABLE categories(
    id serial primary key,
    name text,
    description text
)

CREATE TABLE document(
    id serial primary key,
    source_id integer foreign key references sources,
    external_id text, #eg doi or pmid
    doi text,
    title text,
    abstract text,
    category_id integer foreign key references categories,
    keywords text[],
    augmented_keywords text[], #keywords expanded and AI generated
    mesh_terms text[],
    authors text[],
    publication text,
    publication_date date,
    url text,
    pdf_url text,
    pdf_filename text,
    full_text text,
    added_date timestamp default CURRENT_TIMESTAMP,
    updated_date timestamp default CURRENT_TIMESTAMP,
    withdrawn_date timestamp,
    withdrawn_reason text
)

create table keywords(
    keyword text UNIQUE
)

create table document_keywords(
    document_id integer foreign key references document,
    keyword_id integer foreign key references keywords
)

create table tags(
    id serial primary key,
    document_id integer foreign key references document,
    user_id integer foreign key references users,
    tag text
)

