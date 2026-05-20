import sys

from loguru import logger

from app.config import settings


def setup_logger() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "| <level>{level: <8}</level> "
            "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
            "| <level>{message}</level>"
        ),
    )


setup_logger()
