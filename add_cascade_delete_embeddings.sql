-- Migration script to add CASCADE DELETE constraint to embedding_base table
-- This ensures that when chunks are deleted, their embeddings are automatically deleted

-- First, check if the constraint already exists
DO $$
BEGIN
    -- Check if the foreign key constraint exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = 'embedding_base'
        AND tc.constraint_type = 'FOREIGN KEY'
        AND kcu.column_name = 'chunk_id'
        AND tc.constraint_name LIKE '%chunk_id%'
    ) THEN
        -- Add the foreign key constraint with CASCADE DELETE
        ALTER TABLE embedding_base 
        ADD CONSTRAINT embedding_base_chunk_id_fkey 
        FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
        
        RAISE NOTICE 'Added CASCADE DELETE constraint to embedding_base.chunk_id';
    ELSE
        -- Check if existing constraint has CASCADE DELETE
        IF EXISTS (
            SELECT 1
            FROM information_schema.referential_constraints rc
            JOIN information_schema.table_constraints tc 
                ON rc.constraint_name = tc.constraint_name
            WHERE tc.table_name = 'embedding_base'
            AND rc.delete_rule = 'CASCADE'
        ) THEN
            RAISE NOTICE 'CASCADE DELETE constraint already exists on embedding_base.chunk_id';
        ELSE
            -- Drop existing constraint and recreate with CASCADE
            RAISE NOTICE 'Updating existing constraint to include CASCADE DELETE';
            
            -- Find the existing constraint name
            DECLARE
                constraint_name_var TEXT;
            BEGIN
                SELECT tc.constraint_name INTO constraint_name_var
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'embedding_base'
                AND tc.constraint_type = 'FOREIGN KEY'
                AND kcu.column_name = 'chunk_id'
                LIMIT 1;
                
                IF constraint_name_var IS NOT NULL THEN
                    -- Drop the existing constraint
                    EXECUTE 'ALTER TABLE embedding_base DROP CONSTRAINT ' || constraint_name_var;
                    
                    -- Add the new constraint with CASCADE DELETE
                    ALTER TABLE embedding_base 
                    ADD CONSTRAINT embedding_base_chunk_id_fkey 
                    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
                    
                    RAISE NOTICE 'Updated constraint % to include CASCADE DELETE', constraint_name_var;
                END IF;
            END;
        END IF;
    END IF;
END $$;

-- Verify the constraint was added correctly
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    rc.delete_rule
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.table_name = 'embedding_base'
AND tc.constraint_type = 'FOREIGN KEY'
AND kcu.column_name = 'chunk_id';
