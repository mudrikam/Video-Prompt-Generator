from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QSlider, QSpinBox, QComboBox,
                               QProgressBar, QGroupBox, QGridLayout, QStatusBar,
                               QMenuBar, QMessageBox, QSplitter, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu,
                               QFileDialog)
from PySide6.QtCore import Qt, QTimer, Signal, QSize, Slot
from PySide6.QtGui import QAction, QIcon, QColor
import os
import qtawesome as qta
from typing import Dict, Any

from user_interface.custom_widgets.video_table import VideoTableWidget
from user_interface.settings_dialog import SettingsDialog
from app_utils.config_manager import get_config_manager
from data_manager.database_helper import get_db_helper
from app_utils.threading_helper import get_thread_manager


class MainWindow(QMainWindow):
    """Main window for Video Prompt Generator application"""

    generation_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        self.config = get_config_manager()
        self.db = get_db_helper()
        self.thread_manager = get_thread_manager()

        self.is_generating = False
        self.current_worker_id = None

        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(5000)

        self.setup_ui()
        self.setup_menu()
        self.setup_connections()
        self.update_stats()

    def setup_ui(self):
        """Setup main UI"""
        width, height = self.config.get_window_size()
        self.setWindowTitle("Video Prompt Generator")
        self.setMinimumSize(width, height)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        content_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(content_splitter, 1)

        self.video_table = VideoTableWidget()
        content_splitter.addWidget(self.video_table)

        self.prompt_table = self.create_prompt_table()
        content_splitter.addWidget(self.prompt_table)

        content_splitter.setSizes([500, 500])

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.stats_label = QLabel("Ready")
        self.status_bar.addWidget(self.stats_label)

    def create_control_panel(self) -> QWidget:
        """Create control panel with settings and buttons"""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(12)

        settings_group = self.create_settings_group()
        layout.addWidget(settings_group)

        actions_group = self.create_actions_group()
        layout.addWidget(actions_group)

        return panel

    def create_settings_group(self) -> QGroupBox:
        """Create generation settings group"""
        group = QGroupBox("Settings")
        layout = QGridLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        prompts_label = QLabel("Prompts:")
        layout.addWidget(prompts_label, 0, 0)
        self.prompts_spinbox = QSpinBox()
        self.prompts_spinbox.setMinimumHeight(25)
        min_prompts, max_prompts = self.config.get_prompts_range()
        self.prompts_spinbox.setRange(min_prompts, max_prompts)
        self.prompts_spinbox.setValue(self.config.get_default_prompts_per_video())
        self.prompts_spinbox.valueChanged.connect(self.on_prompts_changed)
        max_batch = self.config.get("generation.max_prompts_per_batch")
        self.prompts_spinbox.setToolTip(
            f"Total prompts per video. Large requests are auto-split into batches "
            f"of up to {max_batch} prompts to avoid token limits."
        )
        layout.addWidget(self.prompts_spinbox, 0, 1)

        complexity_label = QLabel("Complexity:")
        layout.addWidget(complexity_label, 1, 0)
        self.complexity_slider = QSlider(Qt.Horizontal)
        self.complexity_slider.setMinimumHeight(25)
        min_complexity, max_complexity = self.config.get_complexity_range()
        self.complexity_slider.setRange(min_complexity, max_complexity)
        default_complexity = self.config.get("generation.default_complexity_level")
        self.complexity_slider.setValue(default_complexity)
        self.complexity_slider.valueChanged.connect(self.on_complexity_changed)
        layout.addWidget(self.complexity_slider, 1, 1)

        self.complexity_label = QLabel(str(default_complexity))
        layout.addWidget(self.complexity_label, 1, 2)

        variation_label = QLabel("Variation:")
        layout.addWidget(variation_label, 2, 0)
        self.variation_slider = QSlider(Qt.Horizontal)
        self.variation_slider.setMinimumHeight(25)
        min_variation, max_variation = self.config.get_variation_range()
        self.variation_slider.setRange(min_variation, max_variation)
        default_variation = self.config.get("generation.default_variation_level")
        self.variation_slider.setValue(default_variation)
        self.variation_slider.valueChanged.connect(self.on_variation_changed)
        layout.addWidget(self.variation_slider, 2, 1)

        self.variation_label = QLabel(str(default_variation))
        layout.addWidget(self.variation_label, 2, 2)

        aspect_label = QLabel("Ratio:")
        layout.addWidget(aspect_label, 3, 0)
        self.aspect_ratio_combo = QComboBox()
        self.aspect_ratio_combo.setMinimumHeight(25)
        aspect_ratios = self.config.get_available_aspect_ratios()
        self.aspect_ratio_combo.addItems(aspect_ratios)
        default_ratio = self.config.get("generation.default_aspect_ratio")
        self.aspect_ratio_combo.setCurrentText(default_ratio)
        self.aspect_ratio_combo.currentTextChanged.connect(self.on_aspect_ratio_changed)
        layout.addWidget(self.aspect_ratio_combo, 3, 1)

        self.complexity_slider.valueChanged.connect(
            lambda v: self.complexity_label.setText(str(v)))
        self.variation_slider.valueChanged.connect(
            lambda v: self.variation_label.setText(str(v)))

        return group

    def create_actions_group(self) -> QGroupBox:
        """Create actions group with buttons"""
        group = QGroupBox("Actions")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.start_stop_btn = QPushButton("Generate Prompts")
        self.start_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_stop_btn.setIcon(qta.icon('fa5s.play', color='white'))
        self.start_stop_btn.clicked.connect(self.toggle_generation)
        layout.addWidget(self.start_stop_btn)

        mode_layout = QHBoxLayout()
        mode_label = QLabel("Mode:")
        mode_layout.addWidget(mode_label)

        self.generation_mode_combo = QComboBox()
        self.generation_mode_combo.addItems([
            "Selected Videos",
            "All Videos", 
            "Ungenerated Only"
        ])
        self.generation_mode_combo.setCurrentIndex(2)
        self.generation_mode_combo.setMinimumHeight(25)
        mode_layout.addWidget(self.generation_mode_combo, 1)
        layout.addLayout(mode_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(qta.icon('fa5s.sync'))
        self.refresh_btn.clicked.connect(self.refresh_data)
        buttons_layout.addWidget(self.refresh_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setIcon(qta.icon('fa5s.trash'))
        self.clear_btn.clicked.connect(self.show_clear_options)
        buttons_layout.addWidget(self.clear_btn)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setIcon(qta.icon('fa5s.cog'))
        self.settings_btn.clicked.connect(self.show_settings)
        buttons_layout.addWidget(self.settings_btn)

        layout.addLayout(buttons_layout)

        return group

    def create_prompt_table(self) -> QTableWidget:
        """Create prompt table with Prompt, Char Length, and Copy Button"""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Prompt", "Char Length", "Copy"])

        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)

        table.verticalHeader().setVisible(True)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 50)

        table.verticalHeader().setDefaultSectionSize(28)

        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show_prompt_context_menu)

        return table

    def on_video_selection_changed(self):
        """Handle video selection change"""
        self.refresh_prompt_table()

    def on_prompt_selected(self):
        """Handle prompt selection"""
        pass

    def refresh_prompt_table(self):
        """Refresh prompt table based on selected video"""
        selected_video_id = self.video_table.get_selected_video_id()

        if selected_video_id <= 0:
            self.prompt_table.setRowCount(0)
            return

        prompts = self.db.get_prompts_by_video(selected_video_id)
        self.prompt_table.setRowCount(len(prompts))

        for row, prompt in enumerate(prompts):
            prompt_text = prompt['prompt_text'] if prompt['prompt_text'] else ""
            display_text = (prompt_text[:100] + "...") if len(prompt_text) > 100 else prompt_text
            prompt_item = QTableWidgetItem(display_text)

            if prompt.get('is_copied', False):
                qcolors = self.config.get_status_qcolors()
                copied_color = qcolors.get('copied', QColor(255, 195, 42))
                prompt_item.setData(Qt.ForegroundRole, copied_color)

            self.prompt_table.setItem(row, 0, prompt_item)

            char_len = len(prompt_text)
            char_item = QTableWidgetItem(str(char_len))

            if prompt.get('is_copied', False):
                qcolors = self.config.get_status_qcolors()
                copied_color = qcolors.get('copied', QColor(255, 195, 42))
                char_item.setData(Qt.ForegroundRole, copied_color)

            self.prompt_table.setItem(row, 1, char_item)

            copy_btn = QPushButton()
            copy_btn.setText("")
            copy_btn.setIcon(qta.icon('fa5s.copy'))
            copy_btn.setFixedSize(28, 28)
            copy_btn.setIconSize(QSize(14, 14))
            copy_btn.setFlat(False)
            copy_btn.setToolTip("Copy prompt")

            if prompt.get('is_copied', False):
                copy_btn.setIcon(qta.icon('fa5s.check'))
                copy_btn.setToolTip("Already copied")

            copy_btn.clicked.connect(lambda checked, p=prompt: self.copy_single_prompt(p))

            container = QWidget()
            hl = QHBoxLayout(container)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(0)
            hl.addStretch()
            hl.addWidget(copy_btn)
            hl.addStretch()
            self.prompt_table.setCellWidget(row, 2, container)

            prompt_item.setData(Qt.UserRole, prompt)
            char_item.setData(Qt.UserRole, prompt)

    def refresh_prompt_table_for(self, video_id: int):
        """Refresh prompt table if video_id matches selected video"""
        try:
            selected_video_id = self.video_table.get_selected_video_id()
            self.video_table.refresh_table()
            self.update_stats()

            if selected_video_id == video_id:
                self.refresh_prompt_table()
        except Exception:
            pass

    def setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        settings_action = QAction(qta.icon('fa5s.cog'), "Settings", self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)

        import_files_action = QAction(qta.icon('fa5s.file-import'), "Import Video(s)...", self)
        import_files_action.triggered.connect(self.import_videos_from_files)
        file_menu.addAction(import_files_action)

        file_menu.addSeparator()

        exit_action = QAction(qta.icon('fa5s.sign-out-alt'), "Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        import_action = QAction(qta.icon('fa5s.folder-open'), "Import Videos from Folder", self)
        import_action.triggered.connect(self.import_videos_from_folder)
        file_menu.insertAction(exit_action, import_action)

        tools_menu = menubar.addMenu("Tools")

        clear_action = QAction(qta.icon('fa5s.trash'), "Clear All Data", self)
        clear_action.triggered.connect(self.clear_all_data)
        tools_menu.addAction(clear_action)

        refresh_action = QAction(qta.icon('fa5s.sync'), "Refresh", self)
        refresh_action.triggered.connect(self.refresh_data)
        tools_menu.addAction(refresh_action)

        help_menu = menubar.addMenu("Help")

        about_action = QAction(qta.icon('fa5s.info-circle'), "About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_connections(self):
        """Setup signal connections"""
        self.video_table.video_added.connect(self.on_video_added)
        self.video_table.video_removed.connect(self.on_video_removed)
        self.video_table.prompt_copied.connect(self.on_prompt_copied)

        self.video_table.itemSelectionChanged.connect(self.on_video_selection_changed)

        self.video_table.refresh_table()

    def import_videos_from_folder(self):
        """Import supported video files from chosen folder recursively"""
        try:
            folder = QFileDialog.getExistingDirectory(self, "Select folder to import videos", os.path.expanduser("~"))
            if not folder:
                return

            supported_formats = set(self.config.get_supported_video_formats())
            imported = 0

            for root, dirs, files in os.walk(folder):
                for fname in files:
                    _, ext = os.path.splitext(fname.lower())
                    if ext in supported_formats:
                        full_path = os.path.join(root, fname)
                        try:
                            added = self.video_table.add_video_file(full_path)
                            if added:
                                imported += 1
                        except Exception:
                            pass

            self.video_table.refresh_table()
            self.update_stats()

            print(f"Imported {imported} new video(s) from:\n{folder}")

        except Exception as e:
            print(f"Error: Failed to import videos: {e}")

    def import_videos_from_files(self):
        """Import selected video files via file picker"""
        try:
            supported = self.config.get_supported_video_formats()
            if not supported:
                supported = ['.mp4', '.mov', '.mkv']

            exts = ' '.join(f'*{ext}' for ext in supported)
            filter_str = f"Video files ({exts});;All files (*)"

            files, _ = QFileDialog.getOpenFileNames(self, "Select video files to import", os.path.expanduser("~"), filter_str)
            if not files:
                return

            imported = 0
            for f in files:
                try:
                    added = self.video_table.add_video_file(f)
                    if added:
                        imported += 1
                except Exception:
                    pass

            self.video_table.refresh_table()
            self.update_stats()

            print(f"Imported {imported} new video(s)")
        except Exception as e:
            print(f"Error: Failed to import videos: {e}")

    def get_generation_parameters(self) -> Dict[str, Any]:
        """Get current generation parameters"""
        return {
            'prompts_per_video': self.prompts_spinbox.value(),
            'complexity_level': self.complexity_slider.value(),
            'aspect_ratio': self.aspect_ratio_combo.currentText(),
            'variation_level': self.variation_slider.value()
        }

    def toggle_generation(self):
        """Toggle between start and stop generation"""
        if self.is_generating:
            self.stop_generation()
        else:
            self.start_generation()

    def start_generation(self):
        """Start generation process"""
        generation_mode = self.generation_mode_combo.currentText()

        if generation_mode == "Selected Videos":
            videos = self.video_table.get_selected_videos()
            if not videos:
                print("No videos selected for processing")
                return
        elif generation_mode == "All Videos":
            videos = self.db.get_all_videos()
            if not videos:
                print("No videos found")
                return
        else:
            videos = self.video_table.get_ungenerated_videos()
            if not videos:
                print("No ungenerated videos found")
                return

        try:
            self.config.get_api_key()
        except ValueError:
            print("API key missing, configure in Settings first")
            self.show_settings()
            return

        self.is_generating = True
        self._last_generation_video_count = len(videos)
        self._last_generation_failed_count = 0
        self.start_stop_btn.setText("Stop Generation")
        self.start_stop_btn.setIcon(qta.icon('fa5s.stop', color='white'))
        self.start_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        params = self.get_generation_parameters()
        params['videos'] = videos

        self.generation_requested.emit(params)

        self.status_bar.showMessage(f"Generation started for {len(videos)} video(s)...")

    def stop_generation(self):
        """Stop generation process"""
        if self.current_worker_id:
            self.thread_manager.stop_worker(self.current_worker_id)

        self.reset_generation_ui()
        self.status_bar.showMessage("Generation stopped")

    def reset_generation_ui(self):
        """Reset UI state after generation"""
        self.is_generating = False
        self.current_worker_id = None
        self.start_stop_btn.setText("Generate Prompts")
        self.start_stop_btn.setIcon(qta.icon('fa5s.play', color='white'))
        self.start_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.progress_bar.setVisible(False)

        self.video_table.refresh_table()
        self.refresh_prompt_table()

    @Slot(int, str)
    def update_generation_progress(self, percentage: int, message: str = ""):
        """Update progress bar and status"""
        self.progress_bar.setValue(percentage)
        if message:
            self.status_bar.showMessage(message)

    @Slot(bool, str)
    def on_generation_finished(self, success: bool, message: str = ""):
        """Handle generation completion"""
        self.reset_generation_ui()

        if success:
            # Get latest stats for detailed status message
            try:
                stats = self.db.get_stats()
                processed_videos = getattr(self, '_last_generation_video_count', 0)
                generated_prompts = stats.get('total_prompts', 0)
                failed_videos = stats.get('error_videos', 0)

                status_msg = f"Generation completed! Processed: {processed_videos} videos, Generated: {generated_prompts} prompts"
                if failed_videos > 0:
                    status_msg += f", Failed: {failed_videos} videos"

                self.status_bar.showMessage(status_msg)
                print(status_msg)
            except Exception as e:
                self.status_bar.showMessage("Generation completed successfully")
                print(f"Generation completed successfully (stats error: {e})")
        else:
            self.status_bar.showMessage(f"Generation failed: {message}")
            print(f"Generation error: {message}")

        self.update_stats()

    def update_stats(self):
        """Update statistics display"""
        try:
            stats = self.db.get_stats()
            total_videos = stats.get('total_videos', 0)
            total_prompts = stats.get('total_prompts', 0)
            copied_prompts = stats.get('copied_prompts', 0)

            success_rate = 0.0
            if total_prompts:
                success_rate = (copied_prompts / total_prompts) * 100

            try:
                if hasattr(self, 'total_videos_label'):
                    self.total_videos_label.setText(f"Videos: {total_videos}")
                if hasattr(self, 'total_prompts_label'):
                    self.total_prompts_label.setText(f"Prompts: {total_prompts}")
                if hasattr(self, 'copied_prompts_label'):
                    self.copied_prompts_label.setText(f"Copied: {copied_prompts}")
                if hasattr(self, 'success_rate_label'):
                    self.success_rate_label.setText(f"Rate: {success_rate:.1f}%")
            except Exception:
                pass

            if hasattr(self, 'stats_label') and self.stats_label is not None:
                self.stats_label.setText(
                    f"Videos: {total_videos} | Prompts: {total_prompts} | Copied: {copied_prompts} | {success_rate:.1f}%"
                )

        except Exception as e:
            print(f"Error updating stats: {e}")

    def on_video_added(self, filepath: str):
        """Handle video addition"""
        self.update_stats()
        self.status_bar.showMessage(f"Added: {filepath}")

    def on_video_removed(self, video_id: int):
        """Handle video removal"""
        self.update_stats()
        self.status_bar.showMessage("Video removed")

    def on_prompt_copied(self, video_id: int, prompt_count: int):
        """Handle prompt copy"""
        self.update_stats()
        self.status_bar.showMessage(f"Copied {prompt_count} prompts")

    def show_clear_options(self):
        """Show clear options menu"""
        menu = QMenu(self)

        selected_video_id = self.video_table.get_selected_video_id()
        if selected_video_id > 0:
            video = self.db.get_video_by_id(selected_video_id)
            if video:
                clear_video_action = QAction(f"Clear prompts from '{video['filename']}'", self)
                clear_video_action.triggered.connect(lambda: self.clear_video_prompts(selected_video_id))
                menu.addAction(clear_video_action)

        clear_all_prompts_action = QAction("Clear all prompts from all videos", self)
        clear_all_prompts_action.triggered.connect(self.clear_all_prompts)
        menu.addAction(clear_all_prompts_action)

        menu.addSeparator()

        clear_all_action = QAction("Clear all videos and prompts", self)
        clear_all_action.triggered.connect(self.clear_all_data)
        menu.addAction(clear_all_action)

        menu.exec_(self.clear_btn.mapToGlobal(self.clear_btn.rect().bottomLeft()))

    def clear_video_prompts(self, video_id: int):
        """Clear prompts from specific video"""
        video = self.db.get_video_by_id(video_id)
        if not video:
            return

        reply = QMessageBox.question(self, "Clear Video Prompts",
                                   f"Clear all prompts from '{video['filename']}'?",
                                   QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM prompts WHERE video_id = ?", (video_id,))
                conn.commit()

            self.refresh_prompt_table()
            self.video_table.refresh_table()
            self.update_stats()
            self.status_bar.showMessage(f"Cleared prompts from {video['filename']}")

    def clear_all_prompts(self):
        """Clear all prompts from all videos"""
        reply = QMessageBox.question(self, "Clear All Prompts",
                                   "Clear all prompts from all videos?\n"
                                   "Videos will remain but all generated prompts will be deleted.",
                                   QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM prompts")
                conn.commit()

            self.refresh_prompt_table()
            self.video_table.refresh_table()
            self.update_stats()
            self.status_bar.showMessage("All prompts cleared")

    def clear_all_data(self):
        """Clear all data with confirmation"""
        self.video_table.clear_all_videos()
        self.refresh_prompt_table()
        self.update_stats()

    def refresh_data(self):
        """Refresh all data"""
        self.video_table.refresh_table()
        self.update_stats()
        self.status_bar.showMessage("Data refreshed")

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec_() == SettingsDialog.Accepted:
            self.config.reload()
            self.refresh_ui_from_config()
            self.status_bar.showMessage("Settings updated")

    def refresh_ui_from_config(self):
        """Refresh UI controls from current config values"""
        try:
            # Update prompts spinbox range and value
            min_prompts, max_prompts = self.config.get_prompts_range()
            self.prompts_spinbox.setRange(min_prompts, max_prompts)
            self.prompts_spinbox.setValue(self.config.get_default_prompts_per_video())

            # Update complexity slider range and value
            min_complexity, max_complexity = self.config.get_complexity_range()
            self.complexity_slider.setRange(min_complexity, max_complexity)
            complexity_value = self.config.get("generation.default_complexity_level")
            self.complexity_slider.setValue(complexity_value)
            self.complexity_label.setText(str(complexity_value))

            # Update variation slider range and value
            min_variation, max_variation = self.config.get_variation_range()
            self.variation_slider.setRange(min_variation, max_variation)
            variation_value = self.config.get("generation.default_variation_level")
            self.variation_slider.setValue(variation_value)
            self.variation_label.setText(str(variation_value))

            # Update aspect ratio combo
            default_ratio = self.config.get("generation.default_aspect_ratio")
            self.aspect_ratio_combo.setCurrentText(default_ratio)

        except Exception as e:
            print(f"Error refreshing UI from config: {e}")

    def on_prompts_changed(self, value):
        """Save prompts per video setting"""
        try:
            self.config.set("generation.default_prompts_per_video", value)
            self.config.save_config()
        except Exception as e:
            print(f"Error saving prompts setting: {e}")

    def on_complexity_changed(self, value):
        """Save complexity level setting"""
        try:
            self.config.set("generation.default_complexity_level", value)
            self.config.save_config()
        except Exception as e:
            print(f"Error saving complexity setting: {e}")

    def on_variation_changed(self, value):
        """Save variation level setting"""
        try:
            self.config.set("generation.default_variation_level", value)
            self.config.save_config()
        except Exception as e:
            print(f"Error saving variation setting: {e}")

    def on_aspect_ratio_changed(self, value):
        """Save aspect ratio setting"""
        try:
            self.config.set("generation.default_aspect_ratio", value)
            self.config.save_config()
        except Exception as e:
            print(f"Error saving aspect ratio setting: {e}")

    def show_prompt_context_menu(self, position):
        """Show context menu for prompt table"""
        if self.prompt_table.itemAt(position) is None:
            return

        current_row = self.prompt_table.currentRow()
        if current_row < 0:
            return

        prompt_item = self.prompt_table.item(current_row, 0)
        if not prompt_item:
            return

        prompt_data = prompt_item.data(Qt.UserRole)
        if not prompt_data:
            return

        menu = QMenu(self)
        copy_action = QAction(qta.icon('fa5s.copy'), "Copy Prompt", self)
        copy_action.triggered.connect(lambda: self.copy_single_prompt(prompt_data))
        menu.addAction(copy_action)

        view_action = QAction(qta.icon('fa5s.eye'), "View Full Prompt", self)
        view_action.triggered.connect(lambda: self.view_full_prompt(prompt_data))
        menu.addAction(view_action)

        menu.exec_(self.prompt_table.mapToGlobal(position))

    def copy_single_prompt(self, prompt_data):
        """Copy single prompt to clipboard"""
        try:
            from PySide6.QtWidgets import QApplication, QToolTip
            from PySide6.QtGui import QCursor

            prompt_text = prompt_data.get('prompt_text', '')
            if not prompt_text:
                print("No prompt text available")
                return

            clipboard = QApplication.clipboard()
            clipboard.setText(prompt_text)

            preview = (prompt_text[:100] + "...") if len(prompt_text) > 100 else prompt_text
            QToolTip.showText(QCursor.pos(), f"Copied: {preview}")

            self.db.mark_prompt_copied(prompt_data['id'])

            QTimer.singleShot(300, self.refresh_prompt_table)
            QTimer.singleShot(320, self.update_stats)

        except Exception as e:
            print(f"Error: Failed to copy prompt: {str(e)}")

    def view_full_prompt(self, prompt_data):
        """Show full prompt in dialog"""
        prompt_text = prompt_data.get('prompt_text', '')
        if not prompt_text:
            print("No prompt text available")
            return

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("Full Prompt Text")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setPlainText(prompt_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec_()

    def show_about(self):
        """Show about dialog"""
        about_text = (
            "Video Prompt Generator\n"
            "Version: 1\n"
            "Author: github.com/mudrikam\n\n"
            "License: MIT\n\n"
            "Generate AI prompts from video files using Google GenAI.\n"
            "Built with PySide6 and Google GenAI API.\n"
        )

        print(about_text)

    def closeEvent(self, event):
        """Handle close event"""
        if self.is_generating:
            reply = QMessageBox.question(self, "Close Application",
                                       "Generation is in progress. Stop and close?",
                                       QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.stop_generation()
            else:
                event.ignore()
                return

        self.thread_manager.stop_all_workers()
        event.accept()