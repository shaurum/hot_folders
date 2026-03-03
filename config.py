"""
Модуль управления конфигурацией приложения.
Хранит настройки папок, пресетов и путей.
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional

CONFIG_FILE = Path(__file__).parent / "config.json"


class FolderConfig:
    """Конфигурация одной папки для мониторинга."""

    def __init__(self, name: str, input_path: str, output_path: str,
                 preset_name: str, printer_name: str = "",
                 enabled: bool = True, delete_original: bool = False):
        self.name = name  # Идентификатор папки (напр. "A4", "A5")
        self.input_path = input_path  # Путь к входной папке
        self.output_path = output_path  # Путь к выходной папке
        self.preset_name = preset_name  # Имя пресета ImpositionWizard
        self.printer_name = printer_name  # Имя принтера для печати результата
        self.enabled = enabled  # Включена ли папка
        self.delete_original = delete_original  # Удалять исходный файл

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "preset_name": self.preset_name,
            "printer_name": self.printer_name,
            "enabled": self.enabled,
            "delete_original": self.delete_original
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FolderConfig":
        return cls(
            name=data["name"],
            input_path=data["input_path"],
            output_path=data["output_path"],
            preset_name=data["preset_name"],
            printer_name=data.get("printer_name", ""),
            enabled=data.get("enabled", True),
            delete_original=data.get("delete_original", False)
        )


class Config:
    """Основной класс конфигурации приложения."""
    
    def __init__(self):
        self.folders: List[FolderConfig] = []
        self.imposition_wizard_path: str = "ImpositionWizard"  # Путь к exe
        self.auto_start: bool = False
        self._load()
    
    def _load(self):
        """Загрузить конфигурацию из файла."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.folders = [FolderConfig.from_dict(fd) for fd in data.get("folders", [])]
                self.imposition_wizard_path = data.get("imposition_wizard_path", "ImpositionWizard")
                self.auto_start = data.get("auto_start", False)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Ошибка загрузки конфига: {e}")
                self.folders = []
    
    def save(self):
        """Сохранить конфигурацию в файл."""
        data = {
            "folders": [f.to_dict() for f in self.folders],
            "imposition_wizard_path": self.imposition_wizard_path,
            "auto_start": self.auto_start
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_folder(self, folder: FolderConfig):
        """Добавить папку для мониторинга."""
        self.folders.append(folder)
        self.save()
    
    def remove_folder(self, name: str):
        """Удалить папку из мониторинга."""
        self.folders = [f for f in self.folders if f.name != name]
        self.save()
    
    def update_folder(self, name: str, **kwargs):
        """Обновить настройки папки."""
        for folder in self.folders:
            if folder.name == name:
                for key, value in kwargs.items():
                    if hasattr(folder, key):
                        setattr(folder, key, value)
                self.save()
                return True
        return False
    
    def get_enabled_folders(self) -> List[FolderConfig]:
        """Получить список включенных папок."""
        return [f for f in self.folders if f.enabled]


# Глобальный экземпляр конфигурации
config = Config()
