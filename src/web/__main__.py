import uvicorn

from src.config import WEB_HOST, WEB_PORT
from src.logging_config import configurar_logging

if __name__ == "__main__":
    configurar_logging()
    uvicorn.run("src.web.app:app", host=WEB_HOST, port=WEB_PORT, reload=False)
