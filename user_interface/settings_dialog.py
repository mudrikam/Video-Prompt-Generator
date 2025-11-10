from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QLabel, QGroupBox,
                               QMessageBox, QTabWidget, QWidget, QSpinBox,
                               QComboBox, QCheckBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import qtawesome as qta
from app_utils.config_manager import get_config_manager


class SettingsDialog(QDialog):
    """Dialog for application settings"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config_manager()
        self.setup_ui()
        self.load_current_settings()

    def setup_ui(self):
        """Setup UI dialog"""
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)
        self.setWindowIcon(qta.icon('fa5s.cog'))

        layout = QVBoxLayout(self)

        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        api_tab = self.create_api_tab()
        tab_widget.addTab(api_tab, "API Settings")

        generation_tab = self.create_generation_tab()
        tab_widget.addTab(generation_tab, "Generation")

        ui_tab = self.create_ui_tab()
        tab_widget.addTab(ui_tab, "Interface")

        db_tab = self.create_database_tab()
        tab_widget.addTab(db_tab, "Database")

        button_layout = QHBoxLayout()

        self.test_api_btn = QPushButton("Test API")
        self.test_api_btn.setIcon(qta.icon('fa5s.flask'))
        self.test_api_btn.clicked.connect(self.test_api_connection)
        button_layout.addWidget(self.test_api_btn)

        button_layout.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setIcon(qta.icon('fa5s.undo'))
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setIcon(qta.icon('fa5s.save'))
        save_btn.clicked.connect(self.save_settings)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def create_api_tab(self) -> QWidget:
        """Create API settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        api_group = QGroupBox("Google GenAI API")
        api_layout = QFormLayout(api_group)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Enter your GenAI API key")
        api_layout.addRow("API Key:", self.api_key_edit)

        show_key_btn = QPushButton("Show")
        show_key_btn.clicked.connect(self.toggle_api_key_visibility)
        api_layout.addRow("", show_key_btn)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        models = self.config.get_available_models()
        self.model_combo.addItems(models)
        api_layout.addRow("Model:", self.model_combo)

        self.status_label = QLabel("")
        api_layout.addRow("Status:", self.status_label)

        layout.addWidget(api_group)

        video_group = QGroupBox("Video Processing")
        video_layout = QFormLayout(video_group)

        self.max_size_spinbox = QSpinBox()
        min_size, max_size = self.config.get_file_size_range()
        self.max_size_spinbox.setRange(min_size, max_size)
        self.max_size_spinbox.setSuffix(" MB")
        video_layout.addRow("Max File Size:", self.max_size_spinbox)

        self.timeout_spinbox = QSpinBox()
        min_timeout, max_timeout = self.config.get_timeout_range()
        self.timeout_spinbox.setRange(min_timeout, max_timeout)
        self.timeout_spinbox.setSuffix(" seconds")
        video_layout.addRow("Upload Timeout:", self.timeout_spinbox)

        layout.addWidget(video_group)
        layout.addStretch()

        return widget

    def create_generation_tab(self) -> QWidget:
        """Create generation settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        defaults_group = QGroupBox("Default Values")
        defaults_layout = QFormLayout(defaults_group)

        self.default_prompts_spinbox = QSpinBox()
        min_prompts, max_prompts = self.config.get_prompts_range()
        self.default_prompts_spinbox.setRange(min_prompts, max_prompts)
        defaults_layout.addRow("Prompts per Video:", self.default_prompts_spinbox)

        self.max_prompts_spinbox = QSpinBox()
        self.max_prompts_spinbox.setRange(min_prompts, max_prompts * 5)
        defaults_layout.addRow("Max Prompts per Video:", self.max_prompts_spinbox)

        self.default_complexity_spinbox = QSpinBox()
        min_complexity, max_complexity = self.config.get_complexity_range()
        self.default_complexity_spinbox.setRange(min_complexity, max_complexity)
        defaults_layout.addRow("Default Complexity:", self.default_complexity_spinbox)

        self.default_variation_spinbox = QSpinBox()
        min_variation, max_variation = self.config.get_variation_range()
        self.default_variation_spinbox.setRange(min_variation, max_variation)
        defaults_layout.addRow("Default Variation:", self.default_variation_spinbox)

        self.default_aspect_combo = QComboBox()
        aspect_ratios = self.config.get_available_aspect_ratios()
        self.default_aspect_combo.addItems(aspect_ratios)
        defaults_layout.addRow("Default Aspect Ratio:", self.default_aspect_combo)

        layout.addWidget(defaults_group)
        layout.addStretch()

        return widget

    def create_ui_tab(self) -> QWidget:
        """Create UI settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        window_group = QGroupBox("Window Settings")
        window_layout = QFormLayout(window_group)

        self.window_width_spinbox = QSpinBox()
        window_ranges = self.config.get_window_size_range()
        min_width, max_width = window_ranges['width']
        self.window_width_spinbox.setRange(min_width, max_width)
        self.window_width_spinbox.setSuffix(" px")
        window_layout.addRow("Default Width:", self.window_width_spinbox)

        self.window_height_spinbox = QSpinBox()
        min_height, max_height = window_ranges['height']
        self.window_height_spinbox.setRange(min_height, max_height)
        self.window_height_spinbox.setSuffix(" px")
        window_layout.addRow("Default Height:", self.window_height_spinbox)

        self.progress_interval_spinbox = QSpinBox()
        min_interval, max_interval = self.config.get_progress_interval_range()
        self.progress_interval_spinbox.setRange(min_interval, max_interval)
        self.progress_interval_spinbox.setSuffix(" ms")
        window_layout.addRow("Progress Update Interval:", self.progress_interval_spinbox)

        layout.addWidget(window_group)
        layout.addStretch()

        return widget

    def create_database_tab(self) -> QWidget:
        """Create database settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        db_group = QGroupBox("Database Settings")
        db_layout = QFormLayout(db_group)

        self.db_filename_edit = QLineEdit()
        db_layout.addRow("Database File:", self.db_filename_edit)

        self.auto_cleanup_checkbox = QCheckBox("Enable automatic cleanup")
        db_layout.addRow("", self.auto_cleanup_checkbox)

        self.cleanup_days_spinbox = QSpinBox()
        min_cleanup, max_cleanup = self.config.get_cleanup_days_range()
        self.cleanup_days_spinbox.setRange(min_cleanup, max_cleanup)
        self.cleanup_days_spinbox.setSuffix(" days")
        db_layout.addRow("Cleanup after:", self.cleanup_days_spinbox)

        self.backup_checkbox = QCheckBox("Enable automatic backup")
        db_layout.addRow("", self.backup_checkbox)

        layout.addWidget(db_group)
        layout.addStretch()

        return widget

    def load_current_settings(self):
        """Load current settings to form"""
        try:
            try:
                api_key = self.config.get_api_key()
            except ValueError:
                api_key = ""
            self.api_key_edit.setText(api_key)
            self.model_combo.setCurrentText(self.config.get("api.model_name"))

            self.max_size_spinbox.setValue(self.config.get("video.max_file_size_mb"))
            self.timeout_spinbox.setValue(self.config.get("video.upload_timeout_seconds"))

            self.default_prompts_spinbox.setValue(self.config.get("generation.default_prompts_per_video"))
            self.max_prompts_spinbox.setValue(self.config.get("generation.max_prompts_per_video"))
            self.default_complexity_spinbox.setValue(self.config.get("generation.default_complexity_level"))
            self.default_variation_spinbox.setValue(self.config.get("generation.default_variation_level"))
            self.default_aspect_combo.setCurrentText(self.config.get("generation.default_aspect_ratio"))

            self.window_width_spinbox.setValue(self.config.get("ui.window_width"))
            self.window_height_spinbox.setValue(self.config.get("ui.window_height"))
            self.progress_interval_spinbox.setValue(self.config.get("ui.progress_update_interval"))

            self.db_filename_edit.setText(self.config.get("database.filename"))
            self.auto_cleanup_checkbox.setChecked(self.config.get("database.auto_cleanup_days", 0) > 0)
            self.cleanup_days_spinbox.setValue(self.config.get("database.auto_cleanup_days", 30))
            self.backup_checkbox.setChecked(self.config.get("database.backup_enabled"))

        except Exception as e:
            print(f"Error: Failed to load settings: {str(e)}")

    def save_settings(self):
        """Save settings to config file"""
        try:
            self.config.set_api_key(self.api_key_edit.text())
            self.config.set("api.model_name", self.model_combo.currentText())

            self.config.set("video.max_file_size_mb", self.max_size_spinbox.value())
            self.config.set("video.upload_timeout_seconds", self.timeout_spinbox.value())

            self.config.set("generation.default_prompts_per_video", self.default_prompts_spinbox.value())
            self.config.set("generation.max_prompts_per_video", self.max_prompts_spinbox.value())
            self.config.set("generation.default_complexity_level", self.default_complexity_spinbox.value())
            self.config.set("generation.default_variation_level", self.default_variation_spinbox.value())
            self.config.set("generation.default_aspect_ratio", self.default_aspect_combo.currentText())

            self.config.set("ui.window_width", self.window_width_spinbox.value())
            self.config.set("ui.window_height", self.window_height_spinbox.value())
            self.config.set("ui.progress_update_interval", self.progress_interval_spinbox.value())

            self.config.set("database.filename", self.db_filename_edit.text())
            cleanup_days = self.cleanup_days_spinbox.value() if self.auto_cleanup_checkbox.isChecked() else 0
            self.config.set("database.auto_cleanup_days", cleanup_days)
            self.config.set("database.backup_enabled", self.backup_checkbox.isChecked())

            self.config.save_config()

            QMessageBox.information(self, "Success", "Settings saved successfully!")
            self.accept()

        except Exception as e:
            print(f"Error: Failed to save settings: {str(e)}")

    def toggle_api_key_visibility(self):
        """Toggle API key visibility"""
        if self.api_key_edit.echoMode() == QLineEdit.Password:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            self.sender().setText("Hide")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self.sender().setText("Show")

    def test_api_connection(self):
        """Test API connection"""
        api_key = self.api_key_edit.text()
        model_name = self.model_combo.currentText()

        if not api_key:
            print("Warning: Please enter your API key first.")
            return

        self.test_api_btn.setEnabled(False)
        self.test_api_btn.setText("Testing...")
        self.status_label.setText("Testing API...")

        try:
            try:
                original_api_key = self.config.get_api_key()
            except ValueError:
                original_api_key = ""
            original_model = self.config.get("api.model_name")

            self.config.set_api_key(api_key)
            self.config.set("api.model_name", model_name)

            from ai_engine.genai_helper import GenAIHelper

            test_helper = GenAIHelper()

            if test_helper.test_connection():
                self.status_label.setText("Test successful!")
                QMessageBox.information(self, "API Test Successful",
                                      f"Connection to {model_name} successful!\n"
                                      f"API key is valid and working.")
                print(f"API test successful! Connection to {model_name} successful! API key is valid and working.")
            else:
                self.status_label.setText("Test failed. Check console for details.")
                QMessageBox.warning(self, "API Test Failed",
                                  "Connection failed. Please check:\n"
                                  "- API key is correct\n"
                                  "- Model name is valid\n"
                                  "- Internet connection\n"
                                  "- API quota/limits")
                print("API test failed. Please check: - API key is correct - Model name is valid - Internet connection - API quota/limits")

            if original_api_key:
                self.config.set_api_key(original_api_key)
            self.config.set("api.model_name", original_model)

        except Exception as e:
            self.status_label.setText("Test failed. Check console for details.")
            QMessageBox.critical(self, "API Test Error",
                               f"Test failed with error:\n{str(e)}")
            print(f"API test error: Test failed with error: {str(e)}")

        finally:
            self.test_api_btn.setEnabled(True)
            self.test_api_btn.setText("Test API")

    def reset_to_defaults(self):
        """Reset settings to default values"""
        reply = QMessageBox.question(self, "Reset Settings",
                                   "Are you sure you want to reset all settings to defaults?",
                                   QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                self.config.load_config()
                self.load_current_settings()
                QMessageBox.information(self, "Reset", "Settings reset to defaults.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to reset settings: {str(e)}")
        else:
            print(f"Error: Failed to reset settings: {str(e)}")