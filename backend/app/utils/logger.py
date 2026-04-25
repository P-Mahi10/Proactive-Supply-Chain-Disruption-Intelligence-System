import logging
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    # Centralized logger factory to keep logging consistent across modules.
    logger = logging.getLogger(name)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    return logger
