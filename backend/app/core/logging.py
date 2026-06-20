import logging
import sys
from app.core.config import settings

def setup_logging():
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Define log format
    log_format = (
        "%(asctime)s [%(levelname)s] %(name)s - %(filename)s:%(lineno)d - %(message)s"
    )
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Suppress verbose third-party logs if necessary
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logger = logging.getLogger("telemetry-twin")
    logger.info("Logging configured successfully.")
    return logger

logger = setup_logging()
