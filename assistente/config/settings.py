from pydantic import BaseSettings

class Settings(BaseSettings):
    pinecone_index_name: str
    pinecone_namespace: str
    zapi_instance_id: str
    zapi_token: str
    zapi_phone_header: str

    start: str | None = None
    end: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()