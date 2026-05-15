-- RAG similarity search function for policy_chunks
-- Called by RAGService.retrieve_policy() via client.rpc("match_policy_chunks", ...)

CREATE OR REPLACE FUNCTION match_policy_chunks(
    query_embedding  vector(1024),
    match_threshold  float DEFAULT 0.65,
    match_count      int   DEFAULT 5,
    filter_org_id    uuid  DEFAULT NULL,
    filter_source    text  DEFAULT NULL
)
RETURNS TABLE (
    id          uuid,
    source      text,
    section     text,
    content     text,
    similarity  float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pc.id,
        pc.source,
        pc.section,
        pc.content,
        1 - (pc.embedding <=> query_embedding) AS similarity
    FROM policy_chunks pc
    WHERE
        (filter_org_id IS NULL OR pc.org_id IS NULL OR pc.org_id = filter_org_id)
        AND (filter_source IS NULL OR pc.source = filter_source)
        AND 1 - (pc.embedding <=> query_embedding) >= match_threshold
    ORDER BY pc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
