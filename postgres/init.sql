CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
--CREATE EXTENSION IF NOT EXISTS pg_cron;

CREATE TABLE all_sources (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (
        source_type IN ('webpages',
        'pdfs',
        'northdata_publications',
        'northdata_events',
        'northdata_related_companies',
        'northdata_related_persons',
        'northdata_sheets',
        'northdata_companies')
    ),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE webpages (
    id BIGINT PRIMARY KEY REFERENCES all_sources(id) ON DELETE CASCADE,

    normalized_url TEXT UNIQUE,
    raw_url TEXT NOT NULL,
    company TEXT NOT NULL,
    page_type TEXT NOT NULL,

    title TEXT,
    raw_text TEXT,
    text_length INT,
    date TEXT,

    last_mod TEXT,

    crawl_method TEXT,
    source_tag TEXT,

    content_hash TEXT,
    minhash_signature JSONB,
    process_meta JSONB,

    updated_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE webpage_lsh_bands (
    webpage_id BIGINT NOT NULL REFERENCES webpages(id) ON DELETE CASCADE,
    band_index INT NOT NULL,
    band_hash TEXT NOT NULL,

    PRIMARY KEY (webpage_id, band_index)
);

CREATE TABLE duplicate_webpage_urls (
    id BIGSERIAL PRIMARY KEY,

    raw_url TEXT NOT NULL,
    normalized_url TEXT UNIQUE,
    duplicate_of_webpage_id BIGINT REFERENCES webpages(id) ON DELETE CASCADE,

    source_tag TEXT,
    crawl_method TEXT,

    similarity NUMERIC,
    reason TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pdfs (
    id BIGINT PRIMARY KEY REFERENCES all_sources(id) ON DELETE CASCADE,

    pdf_link TEXT NOT NULL UNIQUE,
    company TEXT NOT NULL,

    title TEXT,
    date TEXT,
    language TEXT,

    parent_url TEXT,

    crawl_method TEXT,
    source_tag TEXT,
    html_string TEXT,

    process_meta JSONB,

    created_at TIMESTAMP DEFAULT NOW()

);

CREATE TABLE pdf_segments (
    id BIGSERIAL PRIMARY KEY,
    pdf_id BIGINT NOT NULL REFERENCES pdfs(id) ON DELETE CASCADE,

    segment_index INT NOT NULL,
    heading TEXT,
    heading_path TEXT[],
    token_count INT NOT NULL DEFAULT 0,
    segment_text TEXT NOT NULL DEFAULT '',

    meta JSONB,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (pdf_id, segment_index)
);

CREATE TABLE pdf_chunks (
    id BIGSERIAL PRIMARY KEY,
    pdf_id BIGINT NOT NULL REFERENCES pdfs(id) ON DELETE CASCADE,
    segment_id BIGINT NOT NULL REFERENCES pdf_segments(id) ON DELETE CASCADE,

    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INT,

    headings TEXT[],
    meta JSONB,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (pdf_id, chunk_index)
);

CREATE TABLE webpage_chunks (
    id BIGSERIAL PRIMARY KEY,
    webpage_id BIGINT NOT NULL REFERENCES webpages(id) ON DELETE CASCADE,

    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INT,

    meta JSONB,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (webpage_id, chunk_index)
);

CREATE TABLE source_enrichments (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES all_sources(id) ON DELETE CASCADE,
    pdf_segment_id BIGINT REFERENCES pdf_segments(id) ON DELETE CASCADE,
    content_scope TEXT NOT NULL DEFAULT 'source' CHECK (
        content_scope IN ('source', 'pdf_segment')
    ),

    is_relevant BOOLEAN,
    bucket TEXT NOT NULL CHECK (
        bucket IN ('main', 'weak', 'noise')
    ),

    category TEXT,
    secondary_categories TEXT[],

    signal_strength TEXT CHECK (signal_strength IN ('strong', 'medium', '')),
    pntn_fit_check TEXT CHECK (pntn_fit_check IN ('yes', 'no', '')),

    short_summary TEXT,
    evidence TEXT,
    why_it_matters_for_pntn TEXT,
    possible_business_suggestion TEXT,

    direction TEXT CHECK (direction IN ('opportunity', 'risk', 'neutral')),
    confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),

    source_type TEXT,   --this is not necessary but will simplify the retrieval query if this is a necessary parameter
    prompt_version TEXT,
    model_used TEXT,

    raw_json JSONB,     --can be removed eventually

    created_at TIMESTAMP DEFAULT NOW(),

    CHECK (
        (content_scope = 'source' AND pdf_segment_id IS NULL)
        OR
        (content_scope = 'pdf_segment' AND pdf_segment_id IS NOT NULL)
    )
);

CREATE TABLE source_enrichments_noise (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES all_sources(id) ON DELETE CASCADE,
    pdf_segment_id BIGINT REFERENCES pdf_segments(id) ON DELETE CASCADE,
    content_scope TEXT NOT NULL DEFAULT 'source' CHECK (
        content_scope IN ('source', 'pdf_segment')
    ),

    result TEXT,
    reason TEXT,
    source_type TEXT,
    prompt_version TEXT,
    model_used TEXT,

    raw_json JSONB,
    created_at TIMESTAMP DEFAULT NOW(),

    CHECK (
        (content_scope = 'source' AND pdf_segment_id IS NULL)
        OR
        (content_scope = 'pdf_segment' AND pdf_segment_id IS NOT NULL)
    )
);

CREATE TABLE enrichment_embeddings (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES all_sources(id) ON DELETE CASCADE,
    enrichment_id BIGINT NOT NULL REFERENCES source_enrichments(id) ON DELETE CASCADE,

    field_name TEXT,    --short_summary, evidence, why_it_matters_for_pntn, possible_business_suggestion, all
    content TEXT,

    embedding VECTOR(3072),

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (enrichment_id, field_name)
);

CREATE TABLE IF NOT EXISTS northdata_publications (
    id BIGINT PRIMARY KEY REFERENCES all_sources(id) ON DELETE CASCADE,

   company_name TEXT,
   company_url TEXT,

   publication_url TEXT UNIQUE,
   source_name TEXT,

   title TEXT,
   text TEXT,
   html TEXT,

   date TEXT,
   source_tag TEXT,
   crawl_method TEXT,

   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE publication_topics (
    id             BIGSERIAL PRIMARY KEY,
    publication_id BIGINT NOT NULL REFERENCES all_sources(id) ON DELETE CASCADE,
    type           TEXT,
    value          TEXT
);

CREATE TABLE northdata_companies (
    id         BIGINT PRIMARY KEY REFERENCES all_sources(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    northdata_url TEXT NOT NULL,
    history    JSONB,
    financials JSONB,
    freshest_financial_date TEXT,
    source_tag TEXT,
    crawl_method TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- run every week
CREATE TABLE northdata_events (
    id BIGINT PRIMARY KEY REFERENCES all_sources(id) ON DELETE CASCADE ,

    company_name TEXT NOT NULL,
    company_url TEXT,
    description TEXT NOT NULL,
    type TEXT NOT NULL,

    date TEXT NOT NULL,
    source_tag TEXT,
    crawl_method TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_company_event UNIQUE (company_name, description, date)

);
-- run every two weeks
CREATE TABLE northdata_related_companies (
    id BIGINT PRIMARY KEY REFERENCES all_sources(id) ON DELETE CASCADE,
    related_to TEXT NOT NULL,
    related_to_company_url TEXT,
    company_name TEXT NOT NULL,
    company_url TEXT,
    company_address TEXT,
    description TEXT,
    status TEXT,
    roles JSONB,
    source_tag TEXT,
    crawl_method TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_company_related_to_role UNIQUE (related_to, company_name)


);
-- run every two weeks
CREATE TABLE northdata_related_persons (
    id BIGINT PRIMARY KEY REFERENCES all_sources(id) ON DELETE CASCADE,
    related_to TEXT NOT NULL,
    full_name TEXT NOT NULL,
    description TEXT NOT NULL,
    roles JSONB,
    source_tag TEXT,
    crawl_method TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_person_related_name_role UNIQUE (full_name, related_to, description)
);

 -- make it s.t. the sheets get fetched every year delete old sheets
CREATE TABLE northdata_sheets (
    id BIGINT PRIMARY KEY REFERENCES all_sources(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    sheet_type TEXT NOT NULL,
    name TEXT NOT NULL,
    level INT,
    values JSONB,
    freshest_date TEXT NOT NULL,
    source_tag TEXT,
    crawl_method TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_company_sheet_name_value UNIQUE (company_name, name, freshest_date)
);

CREATE TABLE northdata_publication_chunks (
    id BIGSERIAL PRIMARY KEY,
    publication_id BIGINT NOT NULL REFERENCES northdata_publications(id) ON DELETE CASCADE,

    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INT,

    meta JSONB,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (publication_id, chunk_index)
);

CREATE TABLE northdata_event_chunks (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES northdata_events(id) ON DELETE CASCADE,

    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INT,

    meta JSONB,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (event_id, chunk_index)
);

CREATE TABLE chunk_embeddings (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES all_sources(id) ON DELETE CASCADE,

    content_scope TEXT NOT NULL CHECK (
        content_scope IN (
            'webpage_chunk',
            'pdf_chunk',
            'northdata_publication_chunk',
            'northdata_event_chunk'
        )
    ),

    webpage_chunk_id BIGINT REFERENCES webpage_chunks(id) ON DELETE CASCADE,
    pdf_chunk_id BIGINT REFERENCES pdf_chunks(id) ON DELETE CASCADE,
    northdata_publication_chunk_id BIGINT REFERENCES northdata_publication_chunks(id) ON DELETE CASCADE,
    northdata_event_chunk_id BIGINT REFERENCES northdata_event_chunks(id) ON DELETE CASCADE,

    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_type TEXT NOT NULL DEFAULT 'raw_text',
    token_count INT,

    embedding_model TEXT NOT NULL DEFAULT 'text-embedding-3-large',
    embedding VECTOR(3072),
    created_at TIMESTAMP DEFAULT NOW(),

    CHECK (
        (
            content_scope = 'webpage_chunk'
            AND webpage_chunk_id IS NOT NULL
            AND pdf_chunk_id IS NULL
            AND northdata_publication_chunk_id IS NULL
            AND northdata_event_chunk_id IS NULL
        )
        OR
        (
            content_scope = 'pdf_chunk'
            AND pdf_chunk_id IS NOT NULL
            AND webpage_chunk_id IS NULL
            AND northdata_publication_chunk_id IS NULL
            AND northdata_event_chunk_id IS NULL
        )
        OR
        (
            content_scope = 'northdata_publication_chunk'
            AND northdata_publication_chunk_id IS NOT NULL
            AND webpage_chunk_id IS NULL
            AND pdf_chunk_id IS NULL
            AND northdata_event_chunk_id IS NULL
        )
        OR
        (
            content_scope = 'northdata_event_chunk'
            AND northdata_event_chunk_id IS NOT NULL
            AND webpage_chunk_id IS NULL
            AND pdf_chunk_id IS NULL
            AND northdata_publication_chunk_id IS NULL
        )
    )

);


CREATE INDEX idx_publication_topics_type
    ON publication_topics(type);

CREATE INDEX chunk_embeddings_source_id_idx
    ON chunk_embeddings(source_id);

CREATE INDEX webpage_chunks_webpage_id_idx
    ON webpage_chunks(webpage_id);

CREATE INDEX northdata_publication_chunks_publication_id_idx
    ON northdata_publication_chunks(publication_id);

CREATE INDEX northdata_event_chunks_event_id_idx
    ON northdata_event_chunks(event_id);

CREATE INDEX chunk_embeddings_content_scope_idx
    ON chunk_embeddings(content_scope);

CREATE INDEX chunk_embeddings_webpage_chunk_id_idx
    ON chunk_embeddings(webpage_chunk_id)
    WHERE webpage_chunk_id IS NOT NULL;

CREATE INDEX chunk_embeddings_pdf_chunk_id_idx
    ON chunk_embeddings(pdf_chunk_id)
    WHERE pdf_chunk_id IS NOT NULL;

CREATE INDEX chunk_embeddings_northdata_publication_chunk_id_idx
    ON chunk_embeddings(northdata_publication_chunk_id)
    WHERE northdata_publication_chunk_id IS NOT NULL;

CREATE INDEX chunk_embeddings_northdata_event_chunk_id_idx
    ON chunk_embeddings(northdata_event_chunk_id)
    WHERE northdata_event_chunk_id IS NOT NULL;

CREATE UNIQUE INDEX chunk_embeddings_webpage_chunk_model_unique_idx
    ON chunk_embeddings(webpage_chunk_id, embedding_model)
    WHERE webpage_chunk_id IS NOT NULL;

CREATE UNIQUE INDEX chunk_embeddings_pdf_chunk_model_unique_idx
    ON chunk_embeddings(pdf_chunk_id, embedding_model)
    WHERE pdf_chunk_id IS NOT NULL;

CREATE UNIQUE INDEX chunk_embeddings_northdata_publication_chunk_model_unique_idx
    ON chunk_embeddings(northdata_publication_chunk_id, embedding_model)
    WHERE northdata_publication_chunk_id IS NOT NULL;

CREATE UNIQUE INDEX chunk_embeddings_northdata_event_chunk_model_unique_idx
    ON chunk_embeddings(northdata_event_chunk_id, embedding_model)
    WHERE northdata_event_chunk_id IS NOT NULL;

CREATE INDEX chunk_embeddings_embedding_cosine_idx
    ON chunk_embeddings
    USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);

CREATE INDEX enrichment_embeddings_source_id_idx
    ON enrichment_embeddings(source_id);

CREATE INDEX enrichment_embeddings_embedding_cosine_idx
    ON enrichment_embeddings
    USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);

CREATE UNIQUE INDEX source_enrichments_source_unique_idx
    ON source_enrichments(source_id)
    WHERE content_scope = 'source';

CREATE UNIQUE INDEX source_enrichments_pdf_segment_unique_idx
    ON source_enrichments(pdf_segment_id)
    WHERE content_scope = 'pdf_segment';

CREATE UNIQUE INDEX source_enrichments_noise_source_unique_idx
    ON source_enrichments_noise(source_id)
    WHERE content_scope = 'source';

CREATE UNIQUE INDEX source_enrichments_noise_pdf_segment_unique_idx
    ON source_enrichments_noise(pdf_segment_id)
    WHERE content_scope = 'pdf_segment';

CREATE INDEX source_enrichments_category_idx
    ON source_enrichments(category);

CREATE INDEX source_enrichments_bucket_idx
    ON source_enrichments(bucket);

CREATE INDEX source_enrichments_direction_idx
    ON source_enrichments(direction);

CREATE INDEX source_enrichments_confidence_idx
    ON source_enrichments(confidence);

CREATE INDEX source_enrichments_signal_strength_idx
    ON source_enrichments(signal_strength);

CREATE INDEX source_enrichments_secondary_categories_gin_idx
    ON source_enrichments
    USING GIN (secondary_categories);

CREATE INDEX webpages_company_idx
    ON webpages(company);

CREATE INDEX webpages_page_type_idx
    ON webpages(page_type);

CREATE INDEX webpages_content_hash_idx
    ON webpages(content_hash);

CREATE INDEX webpage_lsh_bands_lookup_idx
    ON webpage_lsh_bands(band_index, band_hash);

CREATE INDEX duplicate_webpage_urls_normalized_url_idx
    ON duplicate_webpage_urls(normalized_url);

CREATE INDEX pdfs_source_tag_idx
    ON pdfs(source_tag);

CREATE INDEX pdfs_crawl_method_idx
    ON pdfs(crawl_method);

CREATE INDEX pdf_segments_pdf_id_idx
    ON pdf_segments(pdf_id);

CREATE INDEX pdf_chunks_pdf_id_idx
    ON pdf_chunks(pdf_id);

CREATE INDEX pdf_chunks_segment_id_idx
    ON pdf_chunks(segment_id);

CREATE INDEX enrichment_embeddings_field_name_idx
    ON enrichment_embeddings(field_name);

CREATE INDEX enrichment_embeddings_field_source_idx
    ON enrichment_embeddings(field_name, source_id);
