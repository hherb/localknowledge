CREATE OR REPLACE FUNCTION generate_embedding()
RETURNS trigger
LANGUAGE plpython3u
AS $$
    # Use SD to cache the imported module per connection
    if 'ollama' not in SD:
        import ollama
        SD['ollama'] = ollama
    
    ollama = SD['ollama']
    
    # Process the embedding with the cached module
    try:
        response = ollama.embeddings(
            model="snowflake-arctic-embed2:latest",
            prompt=TD["new"]["text_content"]
        )
        TD["new"]["embedding_vector"] = response.get("embedding")
    except Exception as e:
        plpy.warning(f"Embedding generation error: {str(e)}")
    
    return "MODIFY"
$$;