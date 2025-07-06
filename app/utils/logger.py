import logging
import sys
import os

# Garante que a pasta de logs existe
os.makedirs("logs", exist_ok=True)

# Configuração básica do logger
logger = logging.getLogger("assistenteinteligente")
logger.setLevel(logging.INFO)

# Handler para console
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)
handler.setFormatter(formatter)