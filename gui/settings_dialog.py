"""
Диалог настроек приложения.
Управление папками, пресетами и путями.
"""
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QFileDialog, QMessageBox, QFormLayout,
    QDialogButtonBox, QTabWidget, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPixmap, QIcon

from config import config, FolderConfig
from autostart import update_auto_start


class FolderEditDialog(QDialog):
    """Диалог добавления/редактирования папки."""
    
    def __init__(self, folder_config: FolderConfig = None, parent=None):
        super().__init__(parent)
        self.folder_config = folder_config
        self.setup_ui()
        
        if folder_config:
            self.load_data()
    
    def setup_ui(self):
        self.setWindowTitle("📁 Добавить папку" if not self.folder_config else "📁 Редактировать папку")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        title = QLabel("Настройки папки" if not self.folder_config else "Редактирование папки")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #318ce7;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Форма с полями
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(12)

        # Стиль для полей
        field_style = """
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #318ce7;
            }
            QLabel {
                font-weight: bold;
                color: #555;
                font-size: 13px;
            }
        """
        form_widget.setStyleSheet(field_style)

        # Название (идентификатор)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: A4, A5, единички")
        form_layout.addRow("📛 Название:", self.name_edit)

        # Входная папка
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Папка для мониторинга")
        input_btn = QPushButton("📂")
        input_btn.setFixedWidth(40)
        input_btn.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(input_btn)
        form_layout.addRow("📥 Входная папка:", input_layout)

        # Выходная папка
        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Папка для результатов")
        output_btn = QPushButton("📤")
        output_btn.setFixedWidth(40)
        output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(output_btn)
        form_layout.addRow("📤 Выходная папка:", output_layout)

        # Имя пресета
        self.preset_edit = QLineEdit()
        self.preset_edit.setPlaceholderText("Например: My Preset Name")
        form_layout.addRow("🎯 Пресет Imposition:", self.preset_edit)

        # Разделитель
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #ddd;")
        line.setMaximumWidth(400)
        layout.addWidget(line, alignment=Qt.AlignCenter)

        # Включено
        self.enabled_check = QCheckBox("✅ Включить мониторинг")
        self.enabled_check.setChecked(True)
        self.enabled_check.setStyleSheet("font-size: 13px; padding: 5px;")
        layout.addWidget(self.enabled_check)

        # Удалять исходный файл
        self.delete_check = QCheckBox("🗑️ Удалять исходный файл после обработки")
        self.delete_check.setChecked(False)
        self.delete_check.setStyleSheet("font-size: 13px; padding: 5px;")
        layout.addWidget(self.delete_check)

        layout.addWidget(form_widget)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("💾 Сохранить")
        buttons.button(QDialogButtonBox.Cancel).setText("❌ Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def browse_input(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите входную папку"
        )
        if folder:
            self.input_edit.setText(folder)
    
    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите выходную папку"
        )
        if folder:
            self.output_edit.setText(folder)
    
    def load_data(self):
        self.name_edit.setText(self.folder_config.name)
        self.input_edit.setText(self.folder_config.input_path)
        self.output_edit.setText(self.folder_config.output_path)
        self.preset_edit.setText(self.folder_config.preset_name)
        self.enabled_check.setChecked(self.folder_config.enabled)
        self.delete_check.setChecked(self.folder_config.delete_original)

    def get_data(self) -> FolderConfig:
        return FolderConfig(
            name=self.name_edit.text().strip(),
            input_path=self.input_edit.text().strip(),
            output_path=self.output_edit.text().strip(),
            preset_name=self.preset_edit.text().strip(),
            enabled=self.enabled_check.isChecked(),
            delete_original=self.delete_check.isChecked()
        )
    
    def accept(self):
        # Валидация
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите название папки")
            return
        
        if not self.input_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Выберите входную папку")
            return
        
        if not self.output_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Выберите выходную папку")
            return
        
        if not self.preset_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите имя пресета")
            return
        
        super().accept()


class SettingsDialog(QDialog):
    """Основной диалог настроек приложения."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_data()
        self.load_logo()
        self.apply_styles()

    def apply_styles(self):
        """Применить современные стили."""
        # Основной стиль окна
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                background-color: white;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                color: #333;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #318ce7;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #f0f0f0;
            }
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                padding: 8px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #318ce7;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
            QPushButton {
                background-color: #318ce7;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
            QPushButton:disabled {
                background-color: #bdbdbd;
            }
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #318ce7;
            }
            QCheckBox {
                spacing: 8px;
                color: #333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #318ce7;
                border-color: #318ce7;
            }
            QCheckBox::indicator:hover {
                border-color: #318ce7;
            }
            QLabel {
                color: #333;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #318ce7;
            }
            QDialogButtonBox button {
                min-width: 80px;
                padding: 8px 20px;
            }
        """)

    def setup_ui(self):
        self.setWindowTitle("Настройки Hot Folders")
        self.setMinimumSize(700, 550)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        title_label = QLabel("🖨️ Hot Folders — Настройки")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #318ce7;
            padding: 10px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Логотип вверху
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setMaximumHeight(100)
        self.logo_label.setStyleSheet("padding: 10px;")
        layout.addWidget(self.logo_label)

        # Вкладки
        tabs = QTabWidget()
        tabs.setStyleSheet("font-size: 14px;")
        
        # Вкладка папок
        folders_widget = QWidget()
        folders_layout = QVBoxLayout(folders_widget)
        folders_layout.setContentsMargins(10, 10, 10, 10)

        # Заголовок вкладки
        folder_title = QLabel("📁 Папки для мониторинга")
        folder_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #318ce7; padding: 5px;")
        folders_layout.addWidget(folder_title)

        # Список папок
        self.folders_list = QListWidget()
        self.folders_list.itemDoubleClicked.connect(self.edit_folder)
        self.folders_list.setMinimumHeight(200)
        folders_layout.addWidget(self.folders_list)

        # Кнопки управления папками
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_folder)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Изменить")
        self.edit_btn.clicked.connect(self.edit_folder)
        btn_layout.addWidget(self.edit_btn)

        self.remove_btn = QPushButton("🗑️ Удалить")
        self.remove_btn.clicked.connect(self.remove_folder)
        btn_layout.addWidget(self.remove_btn)

        btn_layout.addStretch()
        folders_layout.addLayout(btn_layout)

        tabs.addTab(folders_widget, "📁 Папки")
        
        # Вкладка общих настроек
        general_widget = QWidget()
        general_layout = QVBoxLayout(general_widget)
        general_layout.setContentsMargins(10, 10, 10, 10)

        # Заголовок
        general_title = QLabel("⚙️ Общие настройки")
        general_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #318ce7; padding: 5px;")
        general_layout.addWidget(general_title)

        # Группа для ImpositionWizard
        iw_group = QGroupBox("Путь к ImpositionWizard")
        iw_group_layout = QVBoxLayout()
        
        iw_path_layout = QHBoxLayout()
        self.iw_path_edit = QLineEdit()
        self.iw_path_edit.setPlaceholderText("Путь к ImpositionWizard.exe")
        self.iw_path_edit.textChanged.connect(self.validate_iw_path)
        iw_btn = QPushButton("📂 Обзор")
        iw_btn.clicked.connect(self.browse_iw)
        iw_path_layout.addWidget(self.iw_path_edit)
        iw_path_layout.addWidget(iw_btn)
        iw_group_layout.addLayout(iw_path_layout)
        
        # Кнопка проверки
        self.iw_test_btn = QPushButton("✅ Проверить")
        self.iw_test_btn.clicked.connect(self.test_iw_path)
        iw_group_layout.addWidget(self.iw_test_btn)
        
        # Индикатор статуса
        self.iw_status_label = QLabel("")
        self.iw_status_label.setStyleSheet("padding: 5px;")
        iw_group_layout.addWidget(self.iw_status_label)
        
        iw_group.setLayout(iw_group_layout)
        general_layout.addWidget(iw_group)

        # Автозапуск
        self.auto_start_check = QCheckBox("🚀 Запускать при старте Windows")
        self.auto_start_check.setStyleSheet("padding: 10px; font-size: 13px;")
        general_layout.addWidget(self.auto_start_check)
        
        general_layout.addStretch()

        tabs.addTab(general_widget, "⚙️ Общие")

        layout.addWidget(tabs)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("💾 Сохранить")
        buttons.button(QDialogButtonBox.Cancel).setText("❌ Отмена")
        buttons.accepted.connect(self.save_data)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def browse_iw(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите ImpositionWizard.exe",
            "", "Executable Files (*.exe);;All Files (*)"
        )
        if file_path:
            self.iw_path_edit.setText(file_path)

    def load_logo(self):
        """Загрузить логотип типографии."""
        from PyQt5.QtGui import QPixmap, QIcon
        
        # Поиск логотипа в папке проекта
        logo_paths = [
            Path(__file__).parent.parent / "logo.png",
            Path(__file__).parent.parent / "logo.jpg",
            Path(__file__).parent.parent / "logo.ico",
            Path(__file__).parent.parent / "logo.svg",
        ]
        
        for logo_path in logo_paths:
            if logo_path.exists():
                pixmap = QPixmap(str(logo_path))
                if not pixmap.isNull():
                    # Масштабировать логотип
                    scaled_pixmap = pixmap.scaledToHeight(
                        60, 
                        mode=Qt.SmoothTransformation
                    )
                    self.logo_label.setPixmap(scaled_pixmap)
                    return
        
        # Если логотип не найден — скрыть метку
        self.logo_label.hide()

    def validate_iw_path(self):
        """Проверить путь к ImpositionWizard при изменении."""
        path = self.iw_path_edit.text().strip()
        if not path:
            self.iw_status_label.setText("")
            return
        
        import os
        if os.path.isfile(path):
            self.iw_status_label.setText("✓ Файл найден")
            self.iw_status_label.setStyleSheet("color: green;")
        else:
            self.iw_status_label.setText("✗ Файл не найден")
            self.iw_status_label.setStyleSheet("color: red;")

    def test_iw_path(self):
        """Протестировать путь к ImpositionWizard."""
        path = self.iw_path_edit.text().strip()
        
        if not path:
            QMessageBox.warning(self, "Ошибка", "Укажите путь к ImpositionWizard")
            return
        
        import os
        if not os.path.isfile(path):
            QMessageBox.critical(self, "Ошибка", f"Файл не найден:\n{path}")
            return
        
        # Запустить с --help для проверки
        try:
            cmd = f'"{path}" --help'
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Если вернул 0 или есть вывод - программа работает
            if result.returncode == 0 or result.stdout or result.stderr:
                QMessageBox.information(
                    self, "Успешно",
                    f"ImpositionWizard работает!\n\nПуть: {path}\n"
                    f"Версия/инфо: {result.stdout[:200] if result.stdout else 'OK'}"
                )
            else:
                QMessageBox.warning(
                    self, "Предупреждение",
                    f"ImpositionWizard вернул код {result.returncode}\n\n{result.stderr[:200]}"
                )
        except subprocess.TimeoutExpired:
            QMessageBox.information(
                self, "Работает",
                "ImpositionWizard запустился (тест прерван по таймауту)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить:\n{e}")

    def load_data(self):
        # Загрузить папки
        self.folders_list.clear()
        for folder in config.folders:
            status_icon = "✅" if folder.enabled else "❌"
            delete_icon = "🗑️" if folder.delete_original else ""
            
            # Создать элемент с красивым форматированием
            item = QListWidgetItem(f"{status_icon} {folder.name}")
            item.setData(Qt.UserRole, folder.name)
            
            # Добавить вторую строку с информацией
            info_text = f"📁 {folder.preset_name} {delete_icon}"
            item.setToolTip(f"{folder.input_path}\n⬇\n{folder.output_path}\n\nПресет: {folder.preset_name}\nУдаление: {'включено' if folder.delete_original else 'отключено'}")
            
            if not folder.enabled:
                item.setForeground(QColor("#999"))
            
            self.folders_list.addItem(item)

        # Загрузить общие настройки
        self.iw_path_edit.setText(config.imposition_wizard_path)
        self.auto_start_check.setChecked(config.auto_start)

        # Обновить статус пути
        self.validate_iw_path()
    
    def add_folder(self):
        dialog = FolderEditDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            folder_config = dialog.get_data()
            
            # Проверить уникальность имени
            if any(f.name == folder_config.name for f in config.folders):
                QMessageBox.warning(
                    self, "Ошибка",
                    f"Папка с именем '{folder_config.name}' уже существует"
                )
                return
            
            config.add_folder(folder_config)
            self.load_data()
    
    def edit_folder(self, item=None):
        # `clicked` signal sends bool, while list double-click sends QListWidgetItem.
        if isinstance(item, bool) or item is None:
            item = self.folders_list.currentItem()

        if not isinstance(item, QListWidgetItem):
            QMessageBox.information(
                self, "Информация", "Выберите папку для редактирования"
            )
            return

        folder_name = item.data(Qt.UserRole)
        folder_config = next(
            (f for f in config.folders if f.name == folder_name), 
            None
        )
        
        if folder_config:
            dialog = FolderEditDialog(folder_config=folder_config, parent=self)
            if dialog.exec_() == QDialog.Accepted:
                new_config = dialog.get_data()
                
                # Если имя изменилось, проверить уникальность
                if new_config.name != folder_config.name:
                    if any(f.name == new_config.name for f in config.folders):
                        QMessageBox.warning(
                            self, "Ошибка",
                            f"Папка с именем '{new_config.name}' уже существует"
                        )
                        return
                
                config.remove_folder(folder_config.name)
                config.add_folder(new_config)
                self.load_data()
    
    def remove_folder(self):
        current_item = self.folders_list.currentItem()
        if not current_item:
            QMessageBox.information(
                self, "Информация", "Выберите папку для удаления"
            )
            return
        
        folder_name = current_item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить папку '{folder_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            config.remove_folder(folder_name)
            self.load_data()
    
    def save_data(self):
        # Сохранить путь к ImpositionWizard
        config.imposition_wizard_path = self.iw_path_edit.text().strip() or "ImpositionWizard"
        config.auto_start = self.auto_start_check.isChecked()
        config.save()

        # Применить настройку автозапуска
        update_auto_start(config.auto_start)

        self.accept()
