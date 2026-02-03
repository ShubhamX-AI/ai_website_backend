import logging
import sys
import os
from logging.handlers import RotatingFileHandler

def setup_logging(level=logging.INFO):
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "app.log")

    # Get the root logger
    root_logger = logging.getLogger()
    
    # If the root logger already has handlers, don't add more to avoid double logging
    if root_logger.hasHandlers():
        return

    root_logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler (Rotating)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Set levels for noisy libraries
    logging.getLogger("livekit").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("app")

