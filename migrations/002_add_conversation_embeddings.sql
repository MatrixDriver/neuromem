-- Migration: Add embedding column to conversations table for P1 feature
-- Description: Enable recall to search original conversation fragments
-- Version: 0.2.0
-- Date: 2026-02-14

-- Add embedding column to conversations table
-- Using 1024 dimensions (compatible with MockEmbeddingProvider and SiliconFlow BAAI/bge-m3)
-- Note: For OpenAI text-embedding-3-small (1536 dims), recreate column or use vector without dimension
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- Create index for vector similarity search
-- Note: ivfflat index may not be optimal for small datasets; consider using hnsw for larger datasets
CREATE INDEX IF NOT EXISTS idx_conversations_embedding
ON conversations USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Note: Existing conversations will have NULL embeddings
-- New conversations will automatically get embeddings via ConversationsFacade.add_message()
-- To backfill existing conversations, run:
-- UPDATE conversations SET embedding = <generate_embedding(content)> WHERE embedding IS NULL;
