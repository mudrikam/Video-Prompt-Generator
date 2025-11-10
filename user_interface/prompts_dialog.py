from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
                               QPushButton, QLabel, QListWidget, QListWidgetItem,
                               QSplitter, QMessageBox, QApplication)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from typing import List, Dict, Any
from data_manager.database_helper import get_db_helper


class PromptsDialog(QDialog):
    """Dialog untuk menampilkan dan mengelola prompts dari video"""
    # Signal emitted when prompts status changed (e.g., marked copied)
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
        
        # Video info
        info_label = QLabel(f"Video: {self.video['filename']} | "
                           f"Status: {self.video['status'].title()} | "
                           f"Total Prompts: {len(self.prompts)}")
        info_label.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(info_label)
        
        # Splitter untuk prompts list dan detail
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Prompts list
        self.prompts_list = QListWidget()
        self.prompts_list.currentItemChanged.connect(self.on_prompt_selected)
        splitter.addWidget(self.prompts_list)
        
        # Prompt detail
        detail_layout = QVBoxLayout()
        detail_widget = self.create_detail_widget()
        detail_layout.addWidget(detail_widget)
        
        # Detail container
        from PySide6.QtWidgets import QWidget
        detail_container = QWidget()
        detail_container.setLayout(detail_layout)
        splitter.addWidget(detail_container)
        
        # Set splitter sizes
        splitter.setSizes([300, 500])
        
        # Buttons
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
        """Create widget untuk menampilkan detail prompt"""
        from PySide6.QtWidgets import QWidget, QFormLayout
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Prompt info
        self.info_layout = QFormLayout()
        layout.addLayout(self.info_layout)
        
        # Prompt text
        self.prompt_text = QTextEdit()
        self.prompt_text.setReadOnly(True)
        self.prompt_text.setMinimumHeight(300)
        
        # Set font untuk better readability
        font = QFont("Consolas", 10)
        self.prompt_text.setFont(font)
        
        layout.addWidget(QLabel("Prompt Text:"))
        layout.addWidget(self.prompt_text)
        
        return widget
    
    def load_prompts(self):
        """Load prompts ke list"""
        self.prompts_list.clear()
        
        for i, prompt in enumerate(self.prompts, 1):
            # Build a short snippet from the prompt text for the list view
            full_text = (prompt.get('prompt_text') or "").replace('\n', ' ').strip()
            max_len = 60
            if len(full_text) > max_len:
                # Truncate on word boundary
                snippet = full_text[:max_len].rsplit(' ', 1)[0] + '...'
            else:
                snippet = full_text

            is_copied = prompt.get('is_copied', False)
            item_text = f"{i}. {snippet}"
            if is_copied:
                item_text += " ✓"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, prompt)
            # show full prompt on hover
            item.setToolTip(full_text)

            # Color coding berdasarkan status: use yellow text (foreground) instead of background
            if is_copied:
                try:
                    item.setForeground(QColor(255, 195, 42))
                except Exception:
                    pass

            self.prompts_list.addItem(item)
        
        # Select first item
        if self.prompts_list.count() > 0:
            self.prompts_list.setCurrentRow(0)
    
    def on_prompt_selected(self, current, previous):
        """Handle ketika prompt dipilih"""
        if not current:
            return
        
        prompt = current.data(Qt.UserRole)
        
        # Clear previous info
        self.clear_info_layout()
        
        # Add prompt info
        self.add_info_row("Complexity Level", f"{prompt['complexity_level']}/5")
        self.add_info_row("Aspect Ratio", prompt['aspect_ratio'])
        self.add_info_row("Variation Level", f"{prompt['variation_level']}/5")
        self.add_info_row("Status", "Copied" if prompt['is_copied'] else "Generated")
        self.add_info_row("Created", prompt['created_at'][:19])
        
        # Set prompt text
        self.prompt_text.setPlainText(prompt['prompt_text'])
    
    def clear_info_layout(self):
        """Clear info layout"""
        while self.info_layout.count():
            child = self.info_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def add_info_row(self, label: str, value: str):
        """Add row ke info layout"""
        self.info_layout.addRow(f"{label}:", QLabel(value))

    def _refresh_parent_views(self):
        """Refresh main window / parent views after DB changes so UI stays in sync.

        This tries to find the top-level window and call common update methods if present:
        - video_table.refresh_table()
        - refresh_prompt_table()
        - update_stats()
        """
        try:
            top = self.window()  # top-level widget (MainWindow)
            # If the top window has a video_table child, refresh it
            if hasattr(top, 'video_table') and callable(getattr(top.video_table, 'refresh_table', None)):
                try:
                    top.video_table.refresh_table()
                except Exception:
                    pass

            # If the main window exposes refresh_prompt_table (to refresh right-hand prompt table), call it
            if hasattr(top, 'refresh_prompt_table') and callable(getattr(top, 'refresh_prompt_table', None)):
                try:
                    top.refresh_prompt_table()
                except Exception:
                    pass

            # Update stats if available
            if hasattr(top, 'update_stats') and callable(getattr(top, 'update_stats', None)):
                try:
                    top.update_stats()
                except Exception:
                    pass

        except Exception:
            # Best-effort only; don't crash the dialog if main window can't be refreshed
            pass
    
    def copy_all_prompts(self):
        """Copy semua prompts ke clipboard"""
        if not self.prompts:
            return
        
        try:
            # Format semua prompts
            prompt_texts = []
            for i, prompt in enumerate(self.prompts, 1):
                prompt_texts.append(f"{i}. {prompt['prompt_text']}")
                
                # Mark sebagai copied
                if not prompt['is_copied']:
                    self.db.mark_prompt_copied(prompt['id'])
            
            # Copy ke clipboard
            clipboard_text = "\n\n".join(prompt_texts)
            QApplication.clipboard().setText(clipboard_text)
            
            # Refresh prompts dengan status terbaru
            self.prompts = self.db.get_prompts_by_video(self.video['id'])
            self.load_prompts()

            # Emit signal so callers (main window) can refresh views reliably
            try:
                self.prompts_changed.emit(self.video['id'])
            except Exception:
                pass

            QMessageBox.information(self, "Copied", f"Copied {len(self.prompts)} prompts to clipboard")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy prompts: {str(e)}")
    
    def copy_selected_prompt(self):
        """Copy selected prompt ke clipboard"""
        current_item = self.prompts_list.currentItem()
        if not current_item:
            return
        
        try:
            prompt = current_item.data(Qt.UserRole)
            
            # Copy ke clipboard
            QApplication.clipboard().setText(prompt['prompt_text'])
            
            # Mark sebagai copied
            if not prompt['is_copied']:
                self.db.mark_prompt_copied(prompt['id'])

                # Refresh prompts
                self.prompts = self.db.get_prompts_by_video(self.video['id'])
                self.load_prompts()

                # Notify listeners that prompts changed so main UI can refresh
                try:
                    self.prompts_changed.emit(self.video['id'])
                except Exception:
                    pass

            QMessageBox.information(self, "Copied", "Prompt copied to clipboard")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy prompt: {str(e)}")