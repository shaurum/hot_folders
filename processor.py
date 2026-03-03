"""
Модуль обработки файлов.
Конвертация изображений в PDF и вызов ImpositionWizard.
"""
import os
import sys
import subprocess
import tempfile
import ctypes
import shutil
import time
import threading
from pathlib import Path
from typing import Optional
from ctypes import wintypes
from PIL import Image

from logger import get_logger

logger = get_logger("processor")

# Поддерживаемые расширения изображений
IMAGE_EXTENSIONS = {'.tif', '.tiff', '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
PDF_EXTENSION = '.pdf'


class ProcessorError(Exception):
    """Ошибка обработки файла."""
    pass


class PRINTER_INFO_2(ctypes.Structure):
    _fields_ = [
        ("pServerName", wintypes.LPWSTR),
        ("pPrinterName", wintypes.LPWSTR),
        ("pShareName", wintypes.LPWSTR),
        ("pPortName", wintypes.LPWSTR),
        ("pDriverName", wintypes.LPWSTR),
        ("pComment", wintypes.LPWSTR),
        ("pLocation", wintypes.LPWSTR),
        ("pDevMode", wintypes.LPVOID),
        ("pSepFile", wintypes.LPWSTR),
        ("pPrintProcessor", wintypes.LPWSTR),
        ("pDatatype", wintypes.LPWSTR),
        ("pParameters", wintypes.LPWSTR),
        ("pSecurityDescriptor", wintypes.LPVOID),
        ("Attributes", wintypes.DWORD),
        ("Priority", wintypes.DWORD),
        ("DefaultPriority", wintypes.DWORD),
        ("StartTime", wintypes.DWORD),
        ("UntilTime", wintypes.DWORD),
        ("Status", wintypes.DWORD),
        ("cJobs", wintypes.DWORD),
        ("AveragePPM", wintypes.DWORD),
    ]


PRINTER_STATUS_PAUSED = 0x00000001
PRINTER_STATUS_ERROR = 0x00000002
PRINTER_STATUS_PAPER_OUT = 0x00000010
PRINTER_STATUS_OFFLINE = 0x00000080
PRINTER_STATUS_USER_INTERVENTION = 0x00100000
PRINTER_STATUS_NOT_AVAILABLE = 0x00001000


def _get_printer_status(printer_name: str) -> int:
    """Получить статус принтера через WinAPI."""
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    open_printer = winspool.OpenPrinterW
    open_printer.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), wintypes.LPVOID]
    open_printer.restype = wintypes.BOOL

    get_printer = winspool.GetPrinterW
    get_printer.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPBYTE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    get_printer.restype = wintypes.BOOL

    close_printer = winspool.ClosePrinter
    close_printer.argtypes = [wintypes.HANDLE]
    close_printer.restype = wintypes.BOOL

    handle = wintypes.HANDLE()
    if not open_printer(printer_name, ctypes.byref(handle), None):
        error_code = ctypes.get_last_error()
        raise ProcessorError(
            f"Принтер '{printer_name}' недоступен (OpenPrinterW error={error_code})"
        )

    try:
        needed = wintypes.DWORD(0)
        get_printer(handle, 2, None, 0, ctypes.byref(needed))
        if needed.value == 0:
            error_code = ctypes.get_last_error()
            raise ProcessorError(
                f"Не удалось прочитать статус принтера '{printer_name}' (GetPrinterW error={error_code})"
            )

        buffer = ctypes.create_string_buffer(needed.value)
        if not get_printer(
            handle,
            2,
            ctypes.cast(buffer, wintypes.LPBYTE),
            needed.value,
            ctypes.byref(needed),
        ):
            error_code = ctypes.get_last_error()
            raise ProcessorError(
                f"Не удалось получить статус принтера '{printer_name}' (GetPrinterW error={error_code})"
            )

        info = ctypes.cast(buffer, ctypes.POINTER(PRINTER_INFO_2)).contents
        return int(info.Status)
    finally:
        close_printer(handle)


def _ensure_printer_available(printer_name: str):
    status = _get_printer_status(printer_name)
    bad_flags = (
        PRINTER_STATUS_PAUSED
        | PRINTER_STATUS_ERROR
        | PRINTER_STATUS_PAPER_OUT
        | PRINTER_STATUS_OFFLINE
        | PRINTER_STATUS_USER_INTERVENTION
        | PRINTER_STATUS_NOT_AVAILABLE
    )
    if status & bad_flags:
        raise ProcessorError(
            f"Принтер '{printer_name}' недоступен (status=0x{status:08X})"
        )


def print_pdf_to_printer(pdf_path: Path, printer_name: str):
    """
    Отправить PDF на указанный принтер.

    Используется ShellExecute с операцией printto, поэтому печать зависит
    от приложения по умолчанию для PDF в Windows.
    """
    printer_name = (printer_name or "").strip()
    if not printer_name:
        raise ProcessorError("Не указан принтер для печати")

    _ensure_printer_available(printer_name)

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell_execute = shell32.ShellExecuteW
    shell_execute.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_int,
    ]
    shell_execute.restype = wintypes.HINSTANCE

    result = shell_execute(
        None,
        "printto",
        str(pdf_path),
        f'"{printer_name}"',
        None,
        0,
    )
    if isinstance(result, int):
        result_code = result
    else:
        result_code = ctypes.cast(result, ctypes.c_void_p).value or 0
    if result_code <= 32:
        raise ProcessorError(
            f"Не удалось отправить файл на принтер '{printer_name}' (ShellExecute={result_code})"
        )

    logger.info(f"Файл отправлен на принтер '{printer_name}': {pdf_path}")


def _schedule_file_delete(file_path: Path, delay_seconds: int = 180):
    """Удалить файл с задержкой в фоне, чтобы печатающее приложение успело открыть его."""
    def _delete_later():
        try:
            time.sleep(delay_seconds)
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Удалён временный файл печати: {file_path}")
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл печати {file_path}: {e}")

    threading.Thread(target=_delete_later, daemon=True).start()


def _move_to_print_spool_temp(pdf_path: Path) -> Path:
    """
    Переместить PDF во временную папку печати.
    Это позволяет не держать файл в output-папке и не ломать печать.
    """
    temp_dir = Path(tempfile.gettempdir()) / "hot_folders_print_spool"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_name = f"{pdf_path.stem}_{time.time_ns()}.pdf"
    temp_pdf = temp_dir / temp_name
    shutil.move(str(pdf_path), str(temp_pdf))
    return temp_pdf


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
    # Запускать без shell, чтобы избежать проблем с кавычками и наследованием лишнего окружения.
    cmd = [
        iw_path,
        "--impose",
        f"--project={preset_name}",
        str(input_pdf),
        str(output_pdf),
    ]

    env = os.environ.copy()
    for var in (
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QT_QPA_FONTDIR",
        "QT_QPA_PLATFORMTHEME",
        "QML2_IMPORT_PATH",
        "PYTHONHOME",
        "PYTHONPATH",
    ):
        env.pop(var, None)

    iw_dir = ""
    iw_path_obj = Path(iw_path)
    if iw_path_obj.parent != Path("."):
        iw_dir = str(iw_path_obj.resolve().parent)
        # Для внешнего Qt-приложения его папка должна быть первой в PATH,
        # чтобы подхватились "родные" DLL, а не из _MEIPASS.
        env["PATH"] = iw_dir + os.pathsep + env.get("PATH", "")

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            normalized_meipass = os.path.normcase(os.path.abspath(meipass))
            path_parts = env.get("PATH", "").split(os.pathsep)
            cleaned_parts = []
            for part in path_parts:
                if not part:
                    continue
                normalized_part = os.path.normcase(os.path.abspath(part))
                if normalized_part == normalized_meipass:
                    continue
                if normalized_part.startswith(normalized_meipass + os.sep):
                    continue
                cleaned_parts.append(part)
            env["PATH"] = os.pathsep.join(cleaned_parts)

    try:
        # Использовать cp866 (OEM кодировка русской консоли)
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            encoding='cp866',  # OEM кодировка Windows для русского языка
            errors='replace',
            cwd=iw_dir or None,
            env=env,
            timeout=300  # 5 минут таймаут
        )

        logger.debug(f"ImpositionWizard stdout: {result.stdout}")
        logger.debug(f"ImpositionWizard stderr: {result.stderr}")

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or f"Код ошибки: {result.returncode}"
            # Очистить сообщение от мусора кодировки
            error_msg_clean = error_msg.encode('cp866', errors='replace').decode('cp866', errors='replace')
            
            # Проверить на предупреждения (не критичные ошибки)
            is_warning = (
                'Preflight failed' in error_msg and (
                    'Неподдерживаемые PDF элементы' in error_msg_clean or
                    'Аннотации' in error_msg_clean or
                    'размер trim box' in error_msg_clean or
                    'PDF аннотации найдены' in error_msg_clean
                )
            )
            
            if is_warning:
                # Это предупреждение - логируем но продолжаем
                logger.warning(f"ImpositionWizard предупреждение: {error_msg_clean[:200]}")
                # Копировать входной файл в выходной если обработка не удалась
                import shutil
                try:
                    shutil.copy2(input_pdf, output_pdf)
                    logger.info(f"Файл скопирован без обработки: {output_pdf}")
                    return output_pdf
                except Exception as copy_err:
                    logger.error(f"Не удалось скопировать файл: {copy_err}")
                    raise ProcessorError(f"ImpositionWizard вернул ошибку {result.returncode}: {error_msg_clean[:200]}")
            else:
                # Критическая ошибка
                logger.error(f"ImpositionWizard вернул ошибку: {error_msg_clean}")
                raise ProcessorError(
                    f"ImpositionWizard вернул ошибку {result.returncode}: {error_msg_clean[:200]}"
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
    processing_completed = False

    try:
        # Вызвать ImpositionWizard
        logger.info(f"Вызов ImpositionWizard с пресетом: {folder_config.preset_name}")
        result = run_imposition_wizard(
            iw_path=iw_path,
            preset_name=folder_config.preset_name,
            input_pdf=pdf_path,
            output_pdf=output_pdf
        )

        printer_name = getattr(folder_config, "printer_name", "").strip()
        if printer_name:
            print_source = result
            try:
                if result.exists():
                    print_source = _move_to_print_spool_temp(result)
                    logger.info(
                        f"Итоговый PDF перенесён во временную папку печати: {print_source}"
                    )
            except Exception as move_err:
                logger.warning(
                    f"Не удалось перенести PDF во временную папку печати, печатаю из output: {move_err}"
                )

            print_pdf_to_printer(print_source, printer_name)
            _schedule_file_delete(print_source, delay_seconds=180)
        else:
            logger.warning(
                f"Для папки '{folder_config.name}' не выбран принтер, печать пропущена"
            )

        processing_completed = True
        return result
    finally:
        # Удалить исходный файл если указано (после успешной обработки)
        if delete_original and processing_completed and file_path.exists():
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
