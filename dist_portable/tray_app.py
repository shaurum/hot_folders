"""
Основное приложение с системным треем.
"""
import sys
import traceback
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox,
    QStyle
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QBrush, QColor, QImage
from PyQt5.QtCore import QCoreApplication, Qt

from config import config
from watcher import WatchdogManager
from gui.settings_dialog import SettingsDialog
from logger import get_logger

logger = get_logger("tray_app")


def create_icon() -> QIcon:
    """Создать иконку приложения с логотипом."""
    # Поиск логотипа
    logo_paths = [
        Path(__file__).parent / "logo.png",
        Path(__file__).parent / "logo.jpg",
        Path(__file__).parent / "logo.ico",
    ]
    
    logo_path = None
    for path in logo_paths:
        if path.exists():
            logo_path = path
            break
    
    if logo_path:
        # Загрузить логотип и использовать как иконку
        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            # Масштабировать к размеру иконки
            scaled = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Создать круглую иконку с фоном
            final_pixmap = QPixmap(64, 64)
            final_pixmap.fill(QColor(49, 140, 231))  # Синий фон
            
            painter = QPainter(final_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Нарисовать логотип по центру
            x = (64 - scaled.width()) // 2
            y = (64 - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.end()
            
            return QIcon(final_pixmap)
    
    # Если логотипа нет — создать стандартную иконку
    return create_default_icon()


def create_default_icon() -> QIcon:
    """Создать стандартную иконку приложения."""
    # Создать pixmap 64x64
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(49, 140, 231))  # Синий фон

    # Нарисовать простую иконку папки
    painter = QPainter(pixmap)
    painter.setPen(QColor(255, 255, 255))
    painter.setBrush(QBrush(QColor(255, 255, 255)))

    # Контур папки
    painter.drawRect(12, 20, 40, 30)
    painter.drawRect(12, 20, 16, 10)

    # Стрелка вниз (конвертация)
    painter.drawLine(32, 35, 32, 45)
    painter.drawLine(28, 41, 32, 45)
    painter.drawLine(36, 41, 32, 45)

    painter.end()

    return QIcon(pixmap)


class TrayApplication:
    """Основное приложение."""

    def __init__(self):
        try:
            logger.info("Запуск приложения Hot Folders")
            logger.info(f"Путь к ImpositionWizard: {config.imposition_wizard_path}")
            logger.info(f"Найдено папок: {len(config.folders)}")
            
            self.app = QApplication(sys.argv)
            self.app.setQuitOnLastWindowClosed(False)

            # Создать менеджер наблюдателей
            self.watcher_manager = WatchdogManager(
                iw_path=config.imposition_wizard_path,
                on_success=self.on_file_processed,
                on_error=self.on_file_error
            )

            # Настроить системный трей
            self.setup_tray()

            # Запустить наблюдатели
            self.watcher_manager.start_all(config.get_enabled_folders())
            
            logger.info("Приложение успешно запущено")
        except Exception as e:
            logger.error(f"Ошибка при запуске: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(
                None,
                "Ошибка запуска",
                f"Не удалось запустить приложение:\n{e}\n\nПроверьте лог файл: hot_folders.log"
            )
            raise
    
    def setup_tray(self):
        """Настроить системный трей."""
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(create_icon())
        self.tray_icon.setToolTip("Hot Folders - Мониторинг папок")
        
        # Создать меню
        menu = QMenu()
        
        # Действие настроек
        settings_action = QAction("Настройки", menu)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        
        menu.addSeparator()
        
        # Действие выхода
        exit_action = QAction("Выход", menu)
        exit_action.triggered.connect(self.quit_app)
        menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
    
    def on_tray_activated(self, reason):
        """Обработка клика по иконке."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_settings()
    
    def show_settings(self):
        """Показать диалог настроек."""
        logger.info("Открытие диалога настроек")
        dialog = SettingsDialog()
        dialog.exec_()

        # Перезапустить наблюдатели если конфиг изменился
        logger.info("Перезапуск наблюдателей с обновленными настройками")
        self.watcher_manager.stop_all()
        self.watcher_manager.iw_path = config.imposition_wizard_path
        self.watcher_manager.start_all(config.get_enabled_folders())

    def on_file_processed(self, input_path, output_path, folder_name):
        """Файл успешно обработан."""
        logger.info(f"Файл обработан: {input_path} -> {output_path} (папка: {folder_name})")
        # Показать уведомление
        self.tray_icon.showMessage(
            "✅ Готово",
            f"{input_path.name}\nПапка: {folder_name}",
            QSystemTrayIcon.Information,
            3000
        )

    def on_file_error(self, file_path, error_msg, folder_name):
        """Ошибка обработки файла."""
        logger.error(f"Ошибка обработки {file_path} (папка {folder_name}): {error_msg}")
        self.tray_icon.showMessage(
            "❌ Ошибка",
            f"{file_path.name}\n{error_msg}",
            QSystemTrayIcon.Critical,
            5000
        )
    
    def run(self):
        """Запустить приложение."""
        # Показать приветственное уведомление
        self.tray_icon.showMessage(
            "Hot Folders запущен",
            "Приложение работает в фоне. Нажмите на иконку для настроек.",
            QSystemTrayIcon.Information,
            3000
        )
        
        return self.app.exec_()
    
    def quit_app(self):
        """Выйти из приложения."""
        self.watcher_manager.stop_all()
        self.tray_icon.hide()
        QCoreApplication.quit()


def main():
    """Точка входа приложения."""
    app = TrayApplication()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
