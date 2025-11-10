from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
                               QPushButton, QLabel, QListWidget, QListWidgetItem,
                               QSplitter, QMessageBox, QApplication)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from typing import List, Dict, Any
from data_manager.database_helper import get_db_helper
from app_utils.config_manager import get_config_manager


class PromptsDialog(QDialog):
    """Dialog for displaying and managing prompts from video"""

    prompts_changed = Signal(int)

    def __init__(self, video: Dict[str, Any], prompts: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.video = video
        self.prompts = prompts
        self.db = get_db_helper()
        self.setup_ui()
        self.load_prompts()

    def setup_ui(self):
        """Setup UI dialog"""
        self.setWindowTitle(f"Prompts - {self.video['filename']}")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        info_label = QLabel(f"Video: {self.video['filename']} | "
                           f"Status: {self.video['status'].title()} | "
                           f"Total Prompts: {len(self.prompts)}")
        info_label.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(info_label)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        self.prompts_list = QListWidget()
        self.prompts_list.currentItemChanged.connect(self.on_prompt_selected)
        splitter.addWidget(self.prompts_list)

        detail_layout = QVBoxLayout()
        detail_widget = self.create_detail_widget()
        detail_layout.addWidget(detail_widget)

        from PySide6.QtWidgets import QWidget
        detail_container = QWidget()
        detail_container.setLayout(detail_layout)
        splitter.addWidget(detail_container)

        splitter.setSizes([300, 500])

        button_layout = QHBoxLayout()

        copy_all_btn = QPushButton("Copy All Prompts")
        copy_all_btn.clicked.connect(self.copy_all_prompts)
        button_layout.addWidget(copy_all_btn)

        copy_selected_btn = QPushButton("Copy Selected")
        copy_selected_btn.clicked.connect(self.copy_selected_prompt)
        button_layout.addWidget(copy_selected_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def create_detail_widget(self):
        """Create widget for displaying prompt detail"""
        from PySide6.QtWidgets import QWidget, QFormLayout

        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.info_layout = QFormLayout()
        layout.addLayout(self.info_layout)

        self.prompt_text = QTextEdit()
        self.prompt_text.setReadOnly(True)
        self.prompt_text.setMinimumHeight(300)

        font = QFont("Consolas", 10)
        self.prompt_text.setFont(font)

        layout.addWidget(QLabel("Prompt Text:"))
        layout.addWidget(self.prompt_text)

        return widget

    def load_prompts(self):
        """Load prompts into list"""
        self.prompts_list.clear()

        for i, prompt in enumerate(self.prompts, 1):
            full_text = (prompt.get('prompt_text') or "").replace('\n', ' ').strip()
            max_len = 60
            if len(full_text) > max_len:
                snippet = full_text[:max_len].rsplit(' ', 1)[0] + '...'
            else:
                snippet = full_text

            is_copied = prompt.get('is_copied', False)
            item_text = f"{i}. {snippet}"
            if is_copied:
                item_text += " ✓"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, prompt)
            item.setToolTip(full_text)

            if is_copied:
                qcolors = get_config_manager().get_status_qcolors()
                copied_color = qcolors.get('copied')
                item.setForeground(copied_color)

            self.prompts_list.addItem(item)

        if self.prompts_list.count() > 0:
            self.prompts_list.setCurrentRow(0)

    def on_prompt_selected(self, current, previous):
        """Handle prompt selection"""
        if not current:
            return

        prompt = current.data(Qt.UserRole)

        self.clear_info_layout()

        self.add_info_row("Complexity Level", f"{prompt['complexity_level']}/10")
        self.add_info_row("Aspect Ratio", prompt['aspect_ratio'])
        self.add_info_row("Variation Level", f"{prompt['variation_level']}/10")
        self.add_info_row("Status", "Copied" if prompt['is_copied'] else "Generated")
        self.add_info_row("Created", prompt['created_at'][:19])

        self.prompt_text.setPlainText(prompt['prompt_text'])

    def clear_info_layout(self):
        """Clear info layout"""
        while self.info_layout.count():
            child = self.info_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def add_info_row(self, label: str, value: str):
        """Add row to info layout"""
        self.info_layout.addRow(f"{label}:", QLabel(value))

    def _refresh_parent_views(self):
        """Refresh parent views after DB changes"""
        try:
            top = self.window()
            if hasattr(top, 'video_table') and callable(getattr(top.video_table, 'refresh_table', None)):
                try:
                    top.video_table.refresh_table()
                except Exception:
                    pass

            if hasattr(top, 'refresh_prompt_table') and callable(getattr(top, 'refresh_prompt_table', None)):
                try:
                    top.refresh_prompt_table()
                except Exception:
                    pass

            if hasattr(top, 'update_stats') and callable(getattr(top, 'update_stats', None)):
                try:
                    top.update_stats()
                except Exception:
                    pass

        except Exception:
            pass

    def copy_all_prompts(self):
        """Copy all prompts to clipboard"""
        if not self.prompts:
            return

        try:
            prompt_texts = []
            for i, prompt in enumerate(self.prompts, 1):
                prompt_texts.append(f"{i}. {prompt['prompt_text']}")

                if not prompt['is_copied']:
                    self.db.mark_prompt_copied(prompt['id'])

            clipboard_text = "\n\n".join(prompt_texts)
            QApplication.clipboard().setText(clipboard_text)

            self.prompts = self.db.get_prompts_by_video(self.video['id'])
            self.load_prompts()

            try:
                self.prompts_changed.emit(self.video['id'])
            except Exception:
                pass

            print(f"Copied {len(self.prompts)} prompts to clipboard")

        except Exception as e:
            print(f"Error: Failed to copy prompts: {str(e)}")

    def copy_selected_prompt(self):
        """Copy selected prompt to clipboard"""
        current_item = self.prompts_list.currentItem()
        if not current_item:
            return

        try:
            prompt = current_item.data(Qt.UserRole)

            QApplication.clipboard().setText(prompt['prompt_text'])

            if not prompt['is_copied']:
                self.db.mark_prompt_copied(prompt['id'])

                self.prompts = self.db.get_prompts_by_video(self.video['id'])
                self.load_prompts()

                try:
                    self.prompts_changed.emit(self.video['id'])
                except Exception:
                    pass

            print("Prompt copied to clipboard")

        except Exception as e:
            print(f"Error: Failed to copy prompt: {str(e)}")