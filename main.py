"""
Hot Folders - Приложение для автоматической обработки файлов.
Мониторит папки, конвертирует изображения в PDF и применяет ImpositionWizard.
"""
import sys
import os

# Добавить текущую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tray_app import main

if __name__ == "__main__":
    main()
