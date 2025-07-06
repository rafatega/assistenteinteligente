from fastapi import FastAPI, Depends
from assistente.api.webhook import router as webhook_router
from assistente.utils.hora_funcionamento import ensure_allowed_time

app = FastAPI()
app.include_router(
    webhook_router,
    dependencies=[Depends(ensure_allowed_time)]
)