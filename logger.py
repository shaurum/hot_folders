"""Модуль логирования для приложения Hot Folders."""
import logging
import os
import sys
from pathlib import Path

APP_NAME = "HotFolders"


def _get_log_file() -> Path:
    """Выбрать путь к файлу логов с учетом режима запуска."""
    if getattr(sys, "frozen", False):
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME / "hot_folders.log"
        return Path.home() / f".{APP_NAME.lower()}" / "hot_folders.log"
    return Path(__file__).parent / "hot_folders.log"


LOG_FILE = _get_log_file()

logger = logging.getLogger("hot_folders")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Не блокируем запуск приложения, если лог-файл недоступен.
        logger.addHandler(logging.NullHandler())


def get_logger(name: str = "hot_folders") -> logging.Logger:
    """Получить логгер с указанным именем."""
    return logging.getLogger(name)
