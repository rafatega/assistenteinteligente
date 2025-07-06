import logging
import sys
import os

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("assistenteinteligente")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.propagate = True