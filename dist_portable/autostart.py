"""
Модуль автозапуска приложения.
Управление записью в реестр Windows.
"""
import winreg
import sys
import os
from pathlib import Path

# Ключ реестра для автозапуска
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "HotFolders"


def get_app_path() -> str:
    """Получить полный путь к исполняемому файлу приложения."""
    # Если скомпилировано в exe
    if getattr(sys, 'frozen', False):
        return sys.executable
    
    # Если запускается как скрипт
    python_exe = sys.executable
    script_path = Path(__file__).parent / "main.py"
    return f'{python_exe} "{script_path}"'


def is_auto_start_enabled() -> bool:
    """Проверить, включен ли автозапуск."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except OSError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def enable_auto_start():
    """Включить автозапуск приложения."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE)
        app_path = get_app_path()
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_path)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Ошибка включения автозапуска: {e}")
        return False


def disable_auto_start():
    """Отключить автозапуск приложения."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE)
        try:
            winreg.DeleteValue(key, APP_NAME)
        except OSError:
            pass  # Значение не существует
        finally:
            winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Ошибка отключения автозапуска: {e}")
        return False


def update_auto_start(enabled: bool):
    """Обновить настройку автозапуска."""
    if enabled:
        return enable_auto_start()
    else:
        return disable_auto_start()
