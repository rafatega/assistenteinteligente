from pydantic import BaseSettings

class Settings(BaseSettings):
    API_KEY_OPENAI: str
    API_KEY_PINECONE: str
    REDIS_URL: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    ZAPI_PHONE_HEADER: str

    class Config:
        env_file = ".env"

settings = Settings()