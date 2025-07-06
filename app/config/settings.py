import os

# Carrega as variáveis de ambiente mapeadas no Railway
API_KEY_OPENAI = os.getenv("API_KEY_OPENAI")
API_KEY_PINECONE = os.getenv("API_KEY_PINECONE")
PUBLIC_URL = os.getenv("PUBLIC_URL")
REDIS_URL = os.getenv("REDIS_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
