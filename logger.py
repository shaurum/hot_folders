"""
Модуль логирования для приложения Hot Folders.
"""
import logging
from pathlib import Path

# Путь к файлу логов
LOG_FILE = Path(__file__).parent / "hot_folders.log"

# Настроить логгер
logger = logging.getLogger("hot_folders")
logger.setLevel(logging.DEBUG)

# Обработчик файла
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)

# Формат
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)

# Добавить обработчик если ещё не добавлен
if not logger.handlers:
    logger.addHandler(file_handler)


def get_logger(name: str = "hot_folders") -> logging.Logger:
    """Получить логгер с указанным именем."""
    return logging.getLogger(name)
