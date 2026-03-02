"""
Модуль мониторинга папок.
Использует watchdog для отслеживания новых файлов.
"""
import time
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from config import FolderConfig
from processor import process_file, ProcessorError, IMAGE_EXTENSIONS, PDF_EXTENSION
from logger import get_logger

logger = get_logger("watcher")


class FolderWatcher:
    """Класс для мониторинга одной папки."""
    
    def __init__(self, folder_config: FolderConfig, iw_path: str,
                 on_success: Optional[Callable] = None,
                 on_error: Optional[Callable] = None):
        self.config = folder_config
        self.iw_path = iw_path
        self.on_success = on_success
        self.on_error = on_error
        self.observer: Optional[Observer] = None
        self._event_handler = None
    
    def start(self):
        """Запустить мониторинг папки."""
        input_path = Path(self.config.input_path)

        if not input_path.exists():
            logger.warning(f"Входная папка не существует, создаю: {input_path}")
            # Создать папку если не существует
            input_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Запуск мониторинга папки: {self.config.name} -> {input_path}")

        self._event_handler = FileHandler(
            folder_config=self.config,
            iw_path=self.iw_path,
            on_success=self.on_success,
            on_error=self.on_error
        )

        self.observer = Observer()
        self.observer.schedule(
            self._event_handler,
            str(input_path),
            recursive=False
        )
        self.observer.start()
    
    def stop(self):
        """Остановить мониторинг папки."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None


class FileHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы."""

    # Поддерживаемые расширения
    SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | {PDF_EXTENSION}

    def __init__(self, folder_config: FolderConfig, iw_path: str,
                 on_success: Optional[Callable] = None,
                 on_error: Optional[Callable] = None):
        super().__init__()
        self.folder_config = folder_config
        self.iw_path = iw_path
        self.on_success = on_success
        self.on_error = on_error
        self._processing_files = set()
        self._existing_files = set()  # Файлы которые уже были при старте
        self._populate_existing_files()
    
    def _populate_existing_files(self):
        """Запомнить существующие файлы чтобы не обрабатывать их при старте."""
        try:
            input_path = Path(self.folder_config.input_path)
            if input_path.exists():
                for ext in self.SUPPORTED_EXTENSIONS:
                    for file in input_path.glob(f'*{ext}'):
                        self._existing_files.add(str(file))
                    for file in input_path.glob(f'*{ext.upper()}'):
                        self._existing_files.add(str(file))
                logger.debug(f"Найдено {len(self._existing_files)} существующих файлов в {input_path}")
        except Exception as e:
            logger.warning(f"Ошибка при сканировании существующих файлов: {e}")

    def _should_process(self, file_path: Path) -> bool:
        """Проверить, нужно ли обрабатывать файл."""
        # Проверить что файл существует
        if not file_path.exists():
            return False

        # Проверить расширение
        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return False

        # Проверить, не временный ли это файл (начинается с ~ или _)
        if file_path.name.startswith('~') or file_path.name.startswith('_'):
            return False

        # Проверить, не обрабатывается ли уже
        if str(file_path) in self._processing_files:
            return False
        
        # Проверить, не был ли этот файл создан до запуска приложения
        if str(file_path) in self._existing_files:
            logger.debug(f"Пропускаем существующий файл: {file_path}")
            return False

        return True
    
    def _process_file_safe(self, file_path: Path):
        """Безопасная обработка файла с обработкой ошибок."""
        # Проверить что файл ещё существует
        if not file_path.exists():
            logger.debug(f"Файл больше не существует, пропускаем: {file_path}")
            self._processing_files.discard(str(file_path))
            return
        
        logger.info(f"Начало обработки файла: {file_path}")
        try:
            result_path = process_file(
                file_path=file_path,
                folder_config=self.folder_config,
                iw_path=self.iw_path,
                delete_original=self.folder_config.delete_original
            )

            logger.info(f"Файл успешно обработан: {file_path} -> {result_path}")
            if self.on_success:
                self.on_success(file_path, result_path, self.folder_config.name)

        except ProcessorError as e:
            logger.error(f"Ошибка обработки {file_path}: {e}")
            if self.on_error:
                self.on_error(file_path, str(e), self.folder_config.name)
        except Exception as e:
            logger.error(f"Неизвестная ошибка при обработке {file_path}: {e}")
            if self.on_error:
                self.on_error(file_path, f"Неизвестная ошибка: {e}", self.folder_config.name)
        finally:
            # Удалить из множества обрабатываемых
            self._processing_files.discard(str(file_path))
    
    def on_created(self, event):
        """Обработка события создания файла."""
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            file_path = Path(event.src_path)
            logger.debug(f"Создан файл: {file_path}")

            if self._should_process(file_path):
                logger.info(f"Файл добавлен в очередь обработки: {file_path}")
                # Небольшая задержка чтобы файл полностью записался
                time.sleep(0.5)
                self._processing_files.add(str(file_path))
                self._process_file_safe(file_path)

    def on_modified(self, event):
        """Обработка события изменения файла."""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            file_path = Path(event.src_path)
            logger.debug(f"Файл изменен: {file_path}")

            if self._should_process(file_path):
                logger.info(f"Измененный файл добавлен в очередь обработки: {file_path}")
                # Проверить что файл больше не изменяется
                time.sleep(1)
                self._processing_files.add(str(file_path))
                self._process_file_safe(file_path)


class WatchdogManager:
    """Менеджер всех наблюдателей папок."""
    
    def __init__(self, iw_path: str,
                 on_success: Optional[Callable] = None,
                 on_error: Optional[Callable] = None):
        self.iw_path = iw_path
        self.on_success = on_success
        self.on_error = on_error
        self.watchers: dict[str, FolderWatcher] = {}
    
    def add_folder(self, folder_config: FolderConfig):
        """Добавить папку для мониторинга."""
        if folder_config.name not in self.watchers:
            watcher = FolderWatcher(
                folder_config=folder_config,
                iw_path=self.iw_path,
                on_success=self.on_success,
                on_error=self.on_error
            )
            watcher.start()
            self.watchers[folder_config.name] = watcher
    
    def remove_folder(self, name: str):
        """Удалить папку из мониторинга."""
        if name in self.watchers:
            self.watchers[name].stop()
            del self.watchers[name]
    
    def update_folder(self, folder_config: FolderConfig):
        """Обновить настройки папки."""
        self.remove_folder(folder_config.name)
        self.add_folder(folder_config)
    
    def start_all(self, folders: list[FolderConfig]):
        """Запустить все наблюдатели."""
        for folder_config in folders:
            if folder_config.enabled:
                self.add_folder(folder_config)
    
    def stop_all(self):
        """Остановить все наблюдатели."""
        for watcher in self.watchers.values():
            watcher.stop()
        self.watchers.clear()
