# # import os

# # DB_DSN = os.getenv("DB_DSN", "postgresql://nba:nba@localhost:5433/nba")
# # OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# # EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
# # LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")

# import os

# DB_DSN = os.getenv("DB_DSN", "postgresql://nba:nba@localhost:5433/nba")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Required for Groq
# EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Using sentence-transformers for embeddings
# LLM_MODEL = "llama3-8b-8192"  # Groq model (or use "llama3-70b-8192" for better quality)

import os

DB_DSN = os.getenv("DB_DSN", "postgresql://nba:nba@localhost:5433/nba")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Required for Groq
EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"  # 768 dimensions
LLM_MODEL = "llama3-8b-8192"  # Groq model (or use "llama3-70b-8192" for better quality)
