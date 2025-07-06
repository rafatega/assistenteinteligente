from fastapi import FastAPI
from assistente.api.webhook import router as webhook_router

app = FastAPI()
app.include_router(
    webhook_router
)