from fastapi import FastAPI
from app.utils.logger import logger
from app.api.webhook import router as webhook_router

logger.info("🚀 Iniciado com sucesso 🚀 ")

app = FastAPI()
app.include_router(
    webhook_router
)
