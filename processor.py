"""
Модуль обработки файлов.
Конвертация изображений в PDF и вызов ImpositionWizard.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from PIL import Image

from logger import get_logger

logger = get_logger("processor")

# Поддерживаемые расширения изображений
IMAGE_EXTENSIONS = {'.tif', '.tiff', '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
PDF_EXTENSION = '.pdf'


class ProcessorError(Exception):
    """Ошибка обработки файла."""
    pass


def convert_image_to_pdf(image_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Конвертировать изображение в PDF.

    Args:
        image_path: Путь к изображению
        output_path: Путь для сохранения PDF (необязательно)

    Returns:
        Путь к созданному PDF файлу
    """
    if output_path is None:
        output_path = image_path.with_suffix('.pdf')

    try:
        with Image.open(image_path) as img:
            # Получить оригинальное DPI изображения если есть
            dpi = img.info.get('dpi', (300, 300))
            
            # Конвертировать в RGB если нужно (для PNG с альфа-каналом)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            # Сохранить как PDF с высоким качеством (300 DPI для печати)
            img.save(
                output_path, 
                'PDF', 
                resolution=dpi[0],  # Сохранить оригинальное DPI или 300
                quality=95  # Максимальное качество JPEG сжатия
            )

        return output_path
    except Exception as e:
        raise ProcessorError(f"Ошибка конвертации {image_path}: {e}")


def run_imposition_wizard(iw_path: str, preset_name: str,
                          input_pdf: Path, output_pdf: Path) -> Path:
    """
    Вызвать ImpositionWizard с указанным пресетом.

    Args:
        iw_path: Путь к исполняемому файлу ImpositionWizard
        preset_name: Имя пресета
        input_pdf: Входной PDF файл
        output_pdf: Выходной PDF файл

    Returns:
        Путь к созданному PDF файлу
    """
    # Сформировать команду как строку для корректной обработки путей с пробелами
    cmd = (
        f'"{iw_path}" --impose --project="{preset_name}" '
        f'"{input_pdf}" "{output_pdf}"'
    )

    try:
        # Сначала сменить кодировку консоли на cp1251 (Windows Cyrillic)
        # Затем запустить команду
        full_cmd = f'chcp 1251 >nul 2>&1 && {cmd}'
        
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',  # После chcp 1251 вывод будет в UTF-8
            errors='replace',
            timeout=300  # 5 минут таймаут
        )

        logger.debug(f"ImpositionWizard stdout: {result.stdout}")
        logger.debug(f"ImpositionWizard stderr: {result.stderr}")

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or f"Код ошибки: {result.returncode}"
            logger.error(f"ImpositionWizard вернул ошибку: {error_msg}")
            raise ProcessorError(
                f"ImpositionWizard вернул ошибку {result.returncode}: {error_msg}"
            )

        logger.info(f"Успешно создан {output_pdf}")
        return output_pdf

    except subprocess.TimeoutExpired:
        logger.error("ImpositionWizard превысил таймаут выполнения")
        raise ProcessorError(f"ImpositionWizard превысил таймаут выполнения")
    except FileNotFoundError:
        logger.error(f"ImpositionWizard не найден: {iw_path}")
        raise ProcessorError(f"ImpositionWizard не найден: {iw_path}")
    except Exception as e:
        logger.error(f"Ошибка вызова ImpositionWizard: {e}")
        raise ProcessorError(f"Ошибка вызова ImpositionWizard: {e}")


def process_file(file_path: Path, folder_config, iw_path: str, 
                 delete_original: bool = False) -> Path:
    """
    Обработать файл: конвертировать в PDF если нужно и применить imposition.

    Args:
        file_path: Путь к файлу
        folder_config: Конфигурация папки
        iw_path: Путь к ImpositionWizard
        delete_original: Удалить исходный файл после обработки

    Returns:
        Путь к финальному PDF файлу
    """
    logger.info(f"Обработка файла: {file_path}")
    
    # Создать выходную папку если не существует
    output_dir = Path(folder_config.output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Определить тип файла и получить PDF
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        logger.debug(f"Конвертация изображения в PDF: {file_path}")
        # Конвертировать изображение в PDF во временную папку
        import tempfile
        temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf', prefix='hot_folders_')
        os.close(temp_fd)
        pdf_path = Path(temp_path)
        try:
            pdf_path = convert_image_to_pdf(file_path, pdf_path)
        except Exception:
            # Очистить temp файл если конвертация не создала его
            if pdf_path.exists():
                pdf_path.unlink()
            raise
    elif file_path.suffix.lower() == PDF_EXTENSION:
        logger.debug(f"Использование PDF как есть: {file_path}")
        # Уже PDF, использовать как есть
        pdf_path = file_path
    else:
        error_msg = f"Неподдерживаемый формат: {file_path.suffix}"
        logger.error(error_msg)
        raise ProcessorError(error_msg)

    # Создать имя выходного файла
    output_pdf = output_dir / f"{file_path.stem}_imposed.pdf"

    try:
        # Вызвать ImpositionWizard
        logger.info(f"Вызов ImpositionWizard с пресетом: {folder_config.preset_name}")
        result = run_imposition_wizard(
            iw_path=iw_path,
            preset_name=folder_config.preset_name,
            input_pdf=pdf_path,
            output_pdf=output_pdf
        )

        return result
    finally:
        # Удалить исходный файл если указано (после успешной обработки)
        if delete_original and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Удалён исходный файл: {file_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить исходный файл {file_path}: {e}")
        
        # Удалить временный PDF если он был создан (не в исходной папке)
        if pdf_path != file_path and pdf_path.exists():
            try:
                pdf_path.unlink()
                logger.debug(f"Удалён временный файл: {pdf_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {pdf_path}: {e}")
