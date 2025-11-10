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
    """Main window aplikasi Video Prompt Generator"""
    
    # Signals
    generation_requested = Signal(dict)  # generation parameters
    
    def __init__(self):
        super().__init__()
        self.config = get_config_manager()
        self.db = get_db_helper()
        self.thread_manager = get_thread_manager()
        
        # Current generation state
        self.is_generating = False
        self.current_worker_id = None
        
        # Stats tracking
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(5000)  # Update every 5 seconds
        
        self.setup_ui()
        self.setup_menu()
        self.setup_connections()
        self.update_stats()
    
    def setup_ui(self):
        """Setup main UI"""
        # Window properties
        width, height = self.config.get_window_size()
        self.setWindowTitle("Video Prompt Generator")
        self.setMinimumSize(width, height)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - efficient spacing
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)  # Reasonable margins
        main_layout.setSpacing(8)  # Good spacing
        
        # Control panel (natural height) - hanya ambil ruang yang diperlukan
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Main content splitter (horizontal untuk 2 tabel) - dominan
        content_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(content_splitter, 1)  # stretch factor 1 = dominan
        
        # Left: Video table
        self.video_table = VideoTableWidget()
        content_splitter.addWidget(self.video_table)
        
        # Right: Prompt table
        self.prompt_table = self.create_prompt_table()
        content_splitter.addWidget(self.prompt_table)
        
        # Set splitter sizes (tabel sama lebar)
        content_splitter.setSizes([500, 500])
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Stats label di status bar
        self.stats_label = QLabel("Ready")
        self.status_bar.addWidget(self.stats_label)
    
    def create_control_panel(self) -> QWidget:
        """Create compact but readable control panel dengan settings dan buttons"""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 5, 8, 5)  # Comfortable margins
        layout.setSpacing(12)  # Good spacing between groups
        
        # Generation settings group
        settings_group = self.create_settings_group()
        layout.addWidget(settings_group)
        
        # Actions group
        actions_group = self.create_actions_group()
        layout.addWidget(actions_group)
        # Note: Stats moved to the status bar to reduce clutter in the control panel
        # (self.stats_label in the status bar is updated by update_stats()).
        
        return panel
    
    def create_settings_group(self) -> QGroupBox:
        """Create compact but readable generation settings group"""
        group = QGroupBox("Settings")
        layout = QGridLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)  # Reasonable margins
        layout.setSpacing(5)  # Good spacing
        
        # Normal readable font size
        
        # Prompts per video
        prompts_label = QLabel("Prompts:")
        layout.addWidget(prompts_label, 0, 0)
        self.prompts_spinbox = QSpinBox()
        self.prompts_spinbox.setMinimumHeight(25)  # Normal height
        min_prompts, max_prompts = self.config.get_prompts_range()
        self.prompts_spinbox.setRange(min_prompts, max_prompts)
        self.prompts_spinbox.setValue(self.config.get_default_prompts_per_video())
        # Tooltip explaining batching behavior: user requests total prompts per video,
        # the system will automatically split into batches of size `generation.max_prompts_per_batch`.
        try:
            max_batch = self.config.get("generation.max_prompts_per_batch")
        except Exception:
            max_batch = 5
        self.prompts_spinbox.setToolTip(
            f"Total prompts per video. Large requests are auto-split into batches "
            f"of up to {max_batch} prompts to avoid token limits."
        )
        layout.addWidget(self.prompts_spinbox, 0, 1)
        
        # Complexity level
        complexity_label = QLabel("Complexity:")
        layout.addWidget(complexity_label, 1, 0)
        self.complexity_slider = QSlider(Qt.Horizontal)
        self.complexity_slider.setMinimumHeight(25)  # Normal height
        min_complexity, max_complexity = self.config.get_complexity_range()
        self.complexity_slider.setRange(min_complexity, max_complexity)
        self.complexity_slider.setValue(self.config.get("generation.default_complexity_level"))
        layout.addWidget(self.complexity_slider, 1, 1)
        
        self.complexity_label = QLabel("3")
        layout.addWidget(self.complexity_label, 1, 2)
        
        # Variation level (di bawah complexity)
        variation_label = QLabel("Variation:")
        layout.addWidget(variation_label, 2, 0)
        self.variation_slider = QSlider(Qt.Horizontal)
        self.variation_slider.setMinimumHeight(25)  # Normal height
        min_variation, max_variation = self.config.get_variation_range()
        self.variation_slider.setRange(min_variation, max_variation)
        self.variation_slider.setValue(self.config.get("generation.default_variation_level"))
        layout.addWidget(self.variation_slider, 2, 1)
        
        self.variation_label = QLabel("3")
        layout.addWidget(self.variation_label, 2, 2)
        
        # Aspect ratio (pindah ke baris 3)
        aspect_label = QLabel("Ratio:")
        layout.addWidget(aspect_label, 3, 0)
        self.aspect_ratio_combo = QComboBox()
        self.aspect_ratio_combo.setMinimumHeight(25)  # Normal height
        aspect_ratios = self.config.get_available_aspect_ratios()
        self.aspect_ratio_combo.addItems(aspect_ratios)
        default_ratio = self.config.get("generation.default_aspect_ratio")
        self.aspect_ratio_combo.setCurrentText(default_ratio)
        layout.addWidget(self.aspect_ratio_combo, 3, 1)
        
        # Connect slider value changes
        self.complexity_slider.valueChanged.connect(
            lambda v: self.complexity_label.setText(str(v)))
        self.variation_slider.valueChanged.connect(
            lambda v: self.variation_label.setText(str(v)))
        
        return group
    
    def create_actions_group(self) -> QGroupBox:
        """Create compact actions group dengan buttons horizontal"""
        group = QGroupBox("Actions")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)  # Reasonable margins
        layout.setSpacing(8)  # Good spacing
        
        # (Mode selector moved below the Generate button for cleaner layout)
        # Single Start/Stop button (bergantian)
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
        
        # Generation mode selector (moved under the main Generate button)
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Mode:")
        mode_layout.addWidget(mode_label)
        
        self.generation_mode_combo = QComboBox()
        self.generation_mode_combo.addItems([
            "Selected Videos",
            "All Videos", 
            "Ungenerated Only"
        ])
        self.generation_mode_combo.setCurrentIndex(2)  # Default: Ungenerated Only
        self.generation_mode_combo.setMinimumHeight(25)
        mode_layout.addWidget(self.generation_mode_combo, 1)
        layout.addLayout(mode_layout)
        
        # Horizontal layout untuk Clear dan Settings buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(qta.icon('fa5s.sync'))
        self.refresh_btn.clicked.connect(self.refresh_data)
        buttons_layout.addWidget(self.refresh_btn)
        
        # Clear button dengan dropdown options
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setIcon(qta.icon('fa5s.trash'))
        self.clear_btn.clicked.connect(self.show_clear_options)
        buttons_layout.addWidget(self.clear_btn)
        
        # Settings button
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setIcon(qta.icon('fa5s.cog'))
        self.settings_btn.clicked.connect(self.show_settings)
        buttons_layout.addWidget(self.settings_btn)
        
        layout.addLayout(buttons_layout)
        
        return group
    # Stats group removed: stats are shown in the status bar via self.stats_label
    
    def create_prompt_table(self) -> QTableWidget:
        """Create prompt table - Prompt, Char Length, dan Copy Button"""
        table = QTableWidget()
        table.setColumnCount(3)  # Tambah kolom copy
        table.setHorizontalHeaderLabels(["Prompt", "Char Length", "Copy"])
        
        # Table properties
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        # Show row numbers to make numbering visible to users
        table.verticalHeader().setVisible(True)
        
        # Header
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Prompt stretch
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Char length fit
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Copy button fixed width
        header.resizeSection(2, 50)  # Copy column width 50px
        
        # Normal row height
        table.verticalHeader().setDefaultSectionSize(28)  # Slightly taller for button
        
        # Context menu for additional actions (proper way, no painting overhead)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show_prompt_context_menu)
        
        return table
    
    def on_video_selection_changed(self):
        """Handle ketika video selection berubah"""
        self.refresh_prompt_table()
    
    def on_prompt_selected(self):
        """Handle ketika prompt dipilih (future use)"""
        pass
    
    def refresh_prompt_table(self):
        """Refresh prompt table berdasarkan selected video - SIMPLE WAY"""
        selected_video_id = self.video_table.get_selected_video_id()
        
        if selected_video_id <= 0:
            self.prompt_table.setRowCount(0)
            return
        
        prompts = self.db.get_prompts_by_video(selected_video_id)
        self.prompt_table.setRowCount(len(prompts))
        
        for row, prompt in enumerate(prompts):
            # Prompt text
            prompt_text = prompt['prompt_text'] if prompt['prompt_text'] else ""
            display_text = (prompt_text[:100] + "...") if len(prompt_text) > 100 else prompt_text
            prompt_item = QTableWidgetItem(display_text)
            
            # Yellow/orange text (foreground) for prompts that were copied
            if prompt.get('is_copied', False):
                try:
                    qcolors = self.config.get_status_qcolors()
                    copied_color = qcolors.get('copied', QColor(255, 195, 42))
                except Exception:
                    copied_color = QColor(255, 195, 42)
                prompt_item.setData(Qt.ForegroundRole, copied_color)
            
            self.prompt_table.setItem(row, 0, prompt_item)
            
            # Character length
            char_len = len(prompt_text)
            char_item = QTableWidgetItem(str(char_len))
            
            # Yellow/orange text (foreground) for prompts that were copied
            if prompt.get('is_copied', False):
                try:
                    qcolors = self.config.get_status_qcolors()
                    copied_color = qcolors.get('copied', QColor(255, 195, 42))
                except Exception:
                    copied_color = QColor(255, 195, 42)
                char_item.setData(Qt.ForegroundRole, copied_color)
                
            self.prompt_table.setItem(row, 1, char_item)
            
            # Copy button yang benar-benar tombol (menggunakan QPushButton)
            copy_btn = QPushButton()
            # Icon-only, no text to keep it compact and look like a small button
            copy_btn.setText("")
            copy_btn.setIcon(qta.icon('fa5s.copy'))
            # Make it square and compact (platform-native look preserved)
            copy_btn.setFixedSize(28, 28)
            copy_btn.setIconSize(QSize(14, 14))
            copy_btn.setFlat(False)
            copy_btn.setToolTip("Copy prompt")

            if prompt.get('is_copied', False):
                # Show check icon for copied prompts. Do NOT change button color.
                copy_btn.setIcon(qta.icon('fa5s.check'))
                copy_btn.setToolTip("Already copied")

            # Connect button click dengan lambda yang proper
            copy_btn.clicked.connect(lambda checked, p=prompt: self.copy_single_prompt(p))

            # Wrap button in a small container to center it in the cell
            container = QWidget()
            hl = QHBoxLayout(container)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(0)
            hl.addStretch()
            hl.addWidget(copy_btn)
            hl.addStretch()
            # Set the container as the cell widget so the button appears centered
            self.prompt_table.setCellWidget(row, 2, container)
            
            # Store prompt data in items for easy access
            prompt_item.setData(Qt.UserRole, prompt)
            char_item.setData(Qt.UserRole, prompt)

    def refresh_prompt_table_for(self, video_id: int):
        """Refresh prompt table if the given video_id matches the currently selected video.

        This ensures dialog-driven updates refresh the visible prompt table only when
        the user is currently viewing the same video's prompts.
        """
        try:
            selected_video_id = self.video_table.get_selected_video_id()
            # Always refresh video table and stats so counts update globally
            self.video_table.refresh_table()
            self.update_stats()

            if selected_video_id == video_id:
                # If the currently selected video matches, refresh the prompt table shown on the right
                self.refresh_prompt_table()
        except Exception:
            # Best-effort only
            pass
    
    def setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        # Settings action
        settings_action = QAction(qta.icon('fa5s.cog'), "Settings", self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)

        # Import single/multiple files action
        import_files_action = QAction(qta.icon('fa5s.file-import'), "Import Video(s)...", self)
        import_files_action.triggered.connect(self.import_videos_from_files)
        file_menu.addAction(import_files_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction(qta.icon('fa5s.sign-out-alt'), "Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Import from folder action (recursively import videos including subfolders)
        import_action = QAction(qta.icon('fa5s.folder-open'), "Import Videos from Folder", self)
        import_action.triggered.connect(self.import_videos_from_folder)
        file_menu.insertAction(exit_action, import_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        # Clear data action
        clear_action = QAction(qta.icon('fa5s.trash'), "Clear All Data", self)
        clear_action.triggered.connect(self.clear_all_data)
        tools_menu.addAction(clear_action)
        
        # Refresh action
        refresh_action = QAction(qta.icon('fa5s.sync'), "Refresh", self)
        refresh_action.triggered.connect(self.refresh_data)
        tools_menu.addAction(refresh_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        # About action
        about_action = QAction(qta.icon('fa5s.info-circle'), "About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_connections(self):
        """Setup signal connections"""
        # Video table signals
        self.video_table.video_added.connect(self.on_video_added)
        self.video_table.video_removed.connect(self.on_video_removed)
        self.video_table.prompt_copied.connect(self.on_prompt_copied)
        
        # Video selection change
        self.video_table.itemSelectionChanged.connect(self.on_video_selection_changed)
        
        # Load existing videos on startup (simple way)
        self.video_table.refresh_table()

    def import_videos_from_folder(self):
        """Import all supported video files from a chosen folder (including subfolders)."""
        try:
            folder = QFileDialog.getExistingDirectory(self, "Select folder to import videos", os.path.expanduser("~"))
            if not folder:
                return

            supported_formats = set(self.config.get_supported_video_formats())
            imported = 0

            # Walk through the folder recursively
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
                            # best-effort: skip files that fail
                            pass

            # Refresh views and stats
            self.video_table.refresh_table()
            self.update_stats()

            QMessageBox.information(self, "Import Complete",
                                    f"Imported {imported} new video(s) from:\n{folder}")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import videos: {e}")

    def import_videos_from_files(self):
        """Import one or more selected video files via file picker."""
        try:
            # Build a file filter from supported formats (e.g. "*.mp4 *.mov")
            supported = self.config.get_supported_video_formats()
            if not supported:
                supported = ['.mp4', '.mov', '.mkv']

            # Create filter string for QFileDialog (extensions without dot)
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

            QMessageBox.information(self, "Import Complete", f"Imported {imported} new video(s)")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import videos: {e}")
    
    def get_generation_parameters(self) -> Dict[str, Any]:
        """Get current generation parameters"""
        return {
            'prompts_per_video': self.prompts_spinbox.value(),
            'complexity_level': self.complexity_slider.value(),
            'aspect_ratio': self.aspect_ratio_combo.currentText(),
            'variation_level': self.variation_slider.value()
        }
    
    def toggle_generation(self):
        """Toggle antara start dan stop generation"""
        if self.is_generating:
            self.stop_generation()
        else:
            self.start_generation()
    
    def start_generation(self):
        """Start generation process"""
        # Get videos based on selected mode
        generation_mode = self.generation_mode_combo.currentText()
        
        if generation_mode == "Selected Videos":
            # Get selected video(s)
            videos = self.video_table.get_selected_videos()
            if not videos:
                QMessageBox.information(self, "No Selection", 
                                      "Please select one or more videos to process.")
                return
        elif generation_mode == "All Videos":
            # Get all videos
            videos = self.db.get_all_videos()
            if not videos:
                QMessageBox.information(self, "No Videos", 
                                      "No videos found. Please add videos first.")
                return
        else:  # Ungenerated Only
            # Get videos without prompts
            videos = self.video_table.get_ungenerated_videos()
            if not videos:
                QMessageBox.information(self, "No Videos", 
                                      "No ungenerated videos found. All videos already have prompts.")
                return
        
        # Check API key
        try:
            self.config.get_api_key()
        except ValueError:
            QMessageBox.warning(self, "API Key Missing", 
                              "Please configure your GenAI API key in Settings first.")
            self.show_settings()
            return
        
        # Update UI state
        self.is_generating = True
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
        
        # Get parameters
        params = self.get_generation_parameters()
        params['videos'] = videos
        
        # Emit signal untuk memulai generation
        self.generation_requested.emit(params)
        
        self.status_bar.showMessage(f"Generation started for {len(videos)} video(s)...")
    
    def stop_generation(self):
        """Stop generation process"""
        if self.current_worker_id:
            self.thread_manager.stop_worker(self.current_worker_id)
        
        self.reset_generation_ui()
        self.status_bar.showMessage("Generation stopped")
    
    def reset_generation_ui(self):
        """Reset UI state setelah generation selesai"""
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
        # Simple direct refresh
        self.video_table.refresh_table()
        self.refresh_prompt_table()
    
    @Slot(int, str)
    def update_generation_progress(self, percentage: int, message: str = ""):
        """Update progress bar dan status"""
        self.progress_bar.setValue(percentage)
        if message:
            self.status_bar.showMessage(message)
    
    @Slot(bool, str)
    def on_generation_finished(self, success: bool, message: str = ""):
        """Handle ketika generation selesai"""
        self.reset_generation_ui()
        
        if success:
            self.status_bar.showMessage("Generation completed successfully")
        else:
            self.status_bar.showMessage(f"Generation failed: {message}")
            QMessageBox.critical(self, "Generation Error", message)
        
        self.update_stats()
    
    def update_stats(self):
        """Update statistics display - SIMPLE WAY"""
        try:
            stats = self.db.get_stats()
            # Compose concise status text for the status bar
            total_videos = stats.get('total_videos', 0)
            total_prompts = stats.get('total_prompts', 0)
            copied_prompts = stats.get('copied_prompts', 0)

            # Calculate success rate safely
            success_rate = 0.0
            if total_prompts:
                success_rate = (copied_prompts / total_prompts) * 100

            # Update legacy labels if they exist (keeps compatibility during refactor)
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
                # Ignore UI update errors for optional legacy widgets
                pass

            # Update concise stats in the status bar so UI is not cluttered
            if hasattr(self, 'stats_label') and self.stats_label is not None:
                self.stats_label.setText(
                    f"Videos: {total_videos} | Prompts: {total_prompts} | Copied: {copied_prompts} | {success_rate:.1f}%"
                )
            
        except Exception as e:
            print(f"Error updating stats: {e}")
    
    def on_video_added(self, filepath: str):
        """Handle ketika video ditambahkan"""
        self.update_stats()
        self.status_bar.showMessage(f"Added: {filepath}")
    
    def on_video_removed(self, video_id: int):
        """Handle ketika video dihapus"""
        self.update_stats()
        self.status_bar.showMessage("Video removed")
    
    def on_prompt_copied(self, video_id: int, prompt_count: int):
        """Handle ketika prompt di-copy"""
        self.update_stats()
        self.status_bar.showMessage(f"Copied {prompt_count} prompts")
    
    def show_clear_options(self):
        """Show clear options menu"""
        menu = QMenu(self)
        
        # Clear prompts from selected video
        selected_video_id = self.video_table.get_selected_video_id()
        if selected_video_id > 0:
            video = self.db.get_video_by_id(selected_video_id)
            if video:
                clear_video_action = QAction(f"Clear prompts from '{video['filename']}'", self)
                clear_video_action.triggered.connect(lambda: self.clear_video_prompts(selected_video_id))
                menu.addAction(clear_video_action)
        
        # Clear all prompts
        clear_all_prompts_action = QAction("Clear all prompts from all videos", self)
        clear_all_prompts_action.triggered.connect(self.clear_all_prompts)
        menu.addAction(clear_all_prompts_action)
        
        menu.addSeparator()
        
        # Clear all videos and prompts
        clear_all_action = QAction("Clear all videos and prompts", self)
        clear_all_action.triggered.connect(self.clear_all_data)
        menu.addAction(clear_all_action)
        
        # Show menu at button position
        menu.exec_(self.clear_btn.mapToGlobal(self.clear_btn.rect().bottomLeft()))
    
    def clear_video_prompts(self, video_id: int):
        """Clear prompts dari video tertentu"""
        video = self.db.get_video_by_id(video_id)
        if not video:
            return
        
        reply = QMessageBox.question(self, "Clear Video Prompts", 
                                   f"Clear all prompts from '{video['filename']}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Delete prompts for this video (tanpa alter DB structure)
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
        """Clear semua prompts dari semua video"""
        reply = QMessageBox.question(self, "Clear All Prompts", 
                                   "Clear all prompts from all videos?\n"
                                   "Videos will remain but all generated prompts will be deleted.",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Delete all prompts (tanpa alter DB structure)
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
        """Clear semua data dengan konfirmasi"""
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
            # Reload config after settings change
            self.config.reload()
            self.status_bar.showMessage("Settings updated")
    
    def show_prompt_context_menu(self, position):
        """Show context menu untuk prompt table"""
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
        # Copy Prompt action
        copy_action = QAction(qta.icon('fa5s.copy'), "Copy Prompt", self)
        copy_action.triggered.connect(lambda: self.copy_single_prompt(prompt_data))
        menu.addAction(copy_action)

        # View Full Prompt action
        view_action = QAction(qta.icon('fa5s.eye'), "View Full Prompt", self)
        view_action.triggered.connect(lambda: self.view_full_prompt(prompt_data))
        menu.addAction(view_action)

        menu.exec_(self.prompt_table.mapToGlobal(position))
    
    def copy_single_prompt(self, prompt_data):
        """Copy single prompt ke clipboard"""
        try:
            from PySide6.QtWidgets import QApplication, QToolTip
            from PySide6.QtGui import QCursor

            prompt_text = prompt_data.get('prompt_text', '')
            if not prompt_text:
                print("No prompt text available")
                return

            # Copy ke clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText(prompt_text)

            # Show tooltip immediately (anchor to cursor) BEFORE rebuilding the table.
            preview = (prompt_text[:100] + "...") if len(prompt_text) > 100 else prompt_text
            QToolTip.showText(QCursor.pos(), f"Copied: {preview}")

            # Mark sebagai copied di database right away so the state is ready for refresh
            self.db.mark_prompt_copied(prompt_data['id'])

            # Delay refresh and stats update slightly so the tooltip remains visible briefly
            QTimer.singleShot(300, self.refresh_prompt_table)
            QTimer.singleShot(320, self.update_stats)
            
        except Exception as e:
            print(f"Failed to copy prompt: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to copy prompt: {str(e)}")
    
    def view_full_prompt(self, prompt_data):
        """Show full prompt dalam dialog"""
        prompt_text = prompt_data.get('prompt_text', '')
        if not prompt_text:
            QMessageBox.information(self, "No Prompt", "No prompt text available")
            return
        
        # Use QDialog instead of QMessageBox for better text display
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
        # Provide concise about information including license, author and version
        about_text = (
            "Video Prompt Generator\n"
            "Version: 1\n"
            "Author: github.com/mudrikam\n\n"
            "License: MIT\n\n"
            "Generate AI prompts from video files using Google GenAI.\n"
            "Built with PySide6 and Google GenAI API.\n"
        )

        QMessageBox.about(self, "About", about_text)
    
    def closeEvent(self, event):
        """Handle close event"""
        # Stop any running generation
        if self.is_generating:
            reply = QMessageBox.question(self, "Close Application", 
                                       "Generation is in progress. Stop and close?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.stop_generation()
            else:
                event.ignore()
                return
        
        # Stop all workers
        self.thread_manager.stop_all_workers()
        event.accept()