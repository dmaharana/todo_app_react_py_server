-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the main bugs table
CREATE TABLE bugs (
    id SERIAL PRIMARY KEY,
    incident_number VARCHAR(100) UNIQUE NOT NULL,
    product VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    closing_notes TEXT,
    resolution_tier_1 VARCHAR(100),
    resolution_tier_2 VARCHAR(100),
    resolution_tier_3 VARCHAR(100),
    problem_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create embeddings table for RAG functionality
CREATE TABLE bug_embeddings (
    id SERIAL PRIMARY KEY,
    bug_id INTEGER REFERENCES bugs(id) ON DELETE CASCADE,
    content_type VARCHAR(50) NOT NULL, -- 'description', 'resolution', 'combined'
    content_text TEXT NOT NULL,
    embedding vector(1536), -- Adjust dimension based on your embedding model
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient querying
CREATE INDEX idx_bugs_incident_number ON bugs(incident_number);
CREATE INDEX idx_bugs_product ON bugs(product);
CREATE INDEX idx_bugs_resolution_tier_1 ON bugs(resolution_tier_1);
CREATE INDEX idx_bugs_resolution_tier_2 ON bugs(resolution_tier_2);
CREATE INDEX idx_bugs_resolution_tier_3 ON bugs(resolution_tier_3);
CREATE INDEX idx_bugs_problem_id ON bugs(problem_id) WHERE problem_id IS NOT NULL;

-- Create vector similarity search indexes (HNSW for better performance)
CREATE INDEX idx_bug_embeddings_vector ON bug_embeddings 
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_bug_embeddings_content_type ON bug_embeddings(content_type);
CREATE INDEX idx_bug_embeddings_bug_id ON bug_embeddings(bug_id);

-- Create a view for easier querying
CREATE VIEW bugs_with_embeddings AS
SELECT 
    b.*,
    be.content_type,
    be.content_text,
    be.embedding
FROM bugs b
JOIN bug_embeddings be ON b.id = be.bug_id;

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update the updated_at column
CREATE TRIGGER update_bugs_updated_at 
    BEFORE UPDATE ON bugs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Example function for similarity search
CREATE OR REPLACE FUNCTION search_similar_bugs(
    query_embedding vector(1536),
    content_type_filter VARCHAR(50) DEFAULT NULL,
    product_filter VARCHAR(255) DEFAULT NULL,
    similarity_threshold FLOAT DEFAULT 0.7,
    result_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    incident_number VARCHAR(100),
    product VARCHAR(255),
    description TEXT,
    closing_notes TEXT,
    resolution_tier_1 VARCHAR(100),
    resolution_tier_2 VARCHAR(100),
    resolution_tier_3 VARCHAR(100),
    problem_id VARCHAR(100),
    similarity_score FLOAT,
    content_type VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        b.incident_number,
        b.product,
        b.description,
        b.closing_notes,
        b.resolution_tier_1,
        b.resolution_tier_2,
        b.resolution_tier_3,
        b.problem_id,
        1 - (be.embedding <=> query_embedding) as similarity_score,
        be.content_type
    FROM bugs b
    JOIN bug_embeddings be ON b.id = be.bug_id
    WHERE 
        (content_type_filter IS NULL OR be.content_type = content_type_filter)
        AND (product_filter IS NULL OR b.product = product_filter)
        AND (1 - (be.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY be.embedding <=> query_embedding
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;