from PySide6.QtWidgets import (QTableWidget, QTableWidgetItem, QMenu, QMessageBox,
                               QHeaderView, QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QAction
import qtawesome as qta
import os
from typing import List, Dict, Any
from app_utils.config_manager import get_config_manager
from data_manager.database_helper import get_db_helper


class VideoTableWidget(QTableWidget):
    """Custom table widget dengan drag-drop support untuk video files"""
    
    # Signals
    video_added = Signal(str)  # filepath
    video_removed = Signal(int)  # video_id
    prompt_copied = Signal(int, int)  # video_id, prompt_id
    
    def __init__(self):
        super().__init__()
        self.config = get_config_manager()
        self.db = get_db_helper()
        self.setup_table()
        self.setup_drag_drop()
        self.setup_context_menu()
        
        # Track copied prompts untuk highlighting
        self.copied_prompts = set()
        
        # Load existing data on startup (simple way)
        self.refresh_table()
        
    def setup_table(self):
        """Setup table properties - hanya Filename dan Char Length"""
        # Simple 2 columns saja
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Filename", "Char Length"])
        
        # Very compact table properties
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        # Show row numbers (indexing) and set compact row height
        # We want numbering visible to users
        self.verticalHeader().setVisible(True)
        self.verticalHeader().setDefaultSectionSize(18)
        
        # Compact header properties
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Filename stretch
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Char length fit
        
    
    
    def setup_drag_drop(self):
        """Setup drag and drop functionality"""
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setDropIndicatorShown(True)
    
    def setup_context_menu(self):
        """Setup context menu untuk right-click"""
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            # Check apakah ada video files
            video_files = self._get_video_files_from_urls(event.mimeData().urls())
            if video_files:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        if event.mimeData().hasUrls():
            video_files = self._get_video_files_from_urls(event.mimeData().urls())
            
            for file_path in video_files:
                self.add_video_file(file_path)
            
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def _get_video_files_from_urls(self, urls: List[QUrl]) -> List[str]:
        """Filter URLs untuk mendapatkan video files yang valid"""
        video_files = []
        supported_formats = self.config.get_supported_video_formats()
        max_size_mb = self.config.get_max_file_size_mb()
        
        for url in urls:
            if url.isLocalFile():
                file_path = url.toLocalFile()
                
                # Check format
                _, ext = os.path.splitext(file_path.lower())
                if ext not in supported_formats:
                    continue
                
                # Check file exists dan size
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    if file_size > max_size_mb * 1024 * 1024:  # Convert MB to bytes
                        QMessageBox.warning(self, "File Too Large", 
                                          f"File {os.path.basename(file_path)} is larger than {max_size_mb}MB")
                        continue
                    
                    video_files.append(file_path)
        
        return video_files
    
    def add_video_file(self, file_path: str) -> bool:
        """Add video file ke table dan database (tanpa alter DB structure)"""
        try:
            # Check apakah sudah ada
            existing_video = self.db.get_video_by_path(file_path)
            if existing_video:
                # Refresh table to show existing data (simple way)
                self.refresh_table()
                QMessageBox.information(self, "File Already Added", 
                                      f"File {os.path.basename(file_path)} already exists in the list")
                return False
            
            # Add ke database (simple insert tanpa alter)
            filename = os.path.basename(file_path)
            filesize = os.path.getsize(file_path)
            
            video_id = self.db.add_video(filename, file_path, filesize)
            
            # Add ke table (simple way)
            self.refresh_table()
            
            # Emit signal
            self.video_added.emit(file_path)
            
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add video file: {str(e)}")
            return False
    
    def refresh_table(self):
        """Refresh table dengan data terbaru - SIMPLE WAY"""
        videos = self.db.get_all_videos()
        
        self.clearContents()
        self.setRowCount(len(videos))
        
        for row, video in enumerate(videos):
            # Filename dengan status color (simple way)
            filename_item = QTableWidgetItem(video['filename'])
            
            # Simple text color for status
            if video['status'] == 'processing':
                filename_item.setData(Qt.ForegroundRole, Qt.GlobalColor.blue)
            elif video['status'] == 'completed':
                filename_item.setData(Qt.ForegroundRole, Qt.GlobalColor.darkGreen)
            elif video['status'] == 'error':
                filename_item.setData(Qt.ForegroundRole, Qt.GlobalColor.red)
            
            self.setItem(row, 0, filename_item)
            
            # Char Length
            prompts = self.db.get_prompts_by_video(video['id'])
            total_chars = sum(len(p['prompt_text']) for p in prompts if p['prompt_text'])
            char_item = QTableWidgetItem(str(total_chars))
            self.setItem(row, 1, char_item)
            
            # Store video_id
            filename_item.setData(Qt.UserRole, video['id'])
    
    def show_context_menu(self, position):
        """Show context menu pada right-click"""
        if self.itemAt(position) is None:
            return
        
        menu = QMenu(self)
        
        # Get selected video
        current_row = self.currentRow()
        if current_row < 0:
            return
        
        video_id_item = self.item(current_row, 0)
        if not video_id_item:
            return
            
        video_id = video_id_item.data(Qt.UserRole)

        # View Prompts action
        view_action = QAction(qta.icon('fa5s.eye'), "View Prompts", self)
        view_action.triggered.connect(lambda: self.view_video_prompts(video_id))
        menu.addAction(view_action)

        menu.addSeparator()

        # Remove Video action
        remove_action = QAction(qta.icon('fa5s.trash'), "Remove Video", self)
        remove_action.triggered.connect(lambda: self.remove_video(video_id))
        menu.addAction(remove_action)

        menu.exec_(self.mapToGlobal(position))
    
    def view_video_prompts(self, video_id: int):
        """Show dialog dengan semua prompts dari video"""
        from user_interface.prompts_dialog import PromptsDialog
        
        try:
            video = self.db.get_video_by_id(video_id)
            prompts = self.db.get_prompts_by_video(video_id)
            
            dialog = PromptsDialog(video, prompts, self)
            # Connect dialog signal to top-level window refresh methods (best-effort)
            try:
                top = self.window()
                # Always refresh video table when prompts change
                if hasattr(top, 'video_table') and callable(getattr(top.video_table, 'refresh_table', None)):
                    dialog.prompts_changed.connect(lambda vid: top.video_table.refresh_table())

                # Refresh prompt table only if the changed prompts belong to the currently selected video
                if hasattr(top, 'refresh_prompt_table_for') and callable(getattr(top, 'refresh_prompt_table_for', None)):
                    dialog.prompts_changed.connect(lambda vid: top.refresh_prompt_table_for(vid))
                elif hasattr(top, 'refresh_prompt_table') and callable(getattr(top, 'refresh_prompt_table', None)):
                    # Fallback: try to call refresh_prompt_table (no video id) when prompts change
                    dialog.prompts_changed.connect(lambda vid: top.refresh_prompt_table())

                # Always update stats when prompts change
                if hasattr(top, 'update_stats') and callable(getattr(top, 'update_stats', None)):
                    dialog.prompts_changed.connect(lambda vid: top.update_stats())
            except Exception:
                pass

            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to view prompts: {str(e)}")
    
    def remove_video(self, video_id: int):
        """Remove video dari table dan database"""
        try:
            video = self.db.get_video_by_id(video_id)
            if not video:
                return
            
            # Confirm removal
            reply = QMessageBox.question(self, "Remove Video", 
                                       f"Are you sure you want to remove '{video['filename']}'?\n"
                                       "This will also delete all generated prompts.",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.db.delete_video(video_id)
                self.refresh_table()
                self.video_removed.emit(video_id)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to remove video: {str(e)}")
    
    def get_selected_video_id(self) -> int:
        """Get ID dari video yang sedang selected"""
        current_row = self.currentRow()
        if current_row < 0:
            return -1
        
        video_id_item = self.item(current_row, 0)
        if not video_id_item:
            return -1
        
        return video_id_item.data(Qt.UserRole)
    
    def clear_all_videos(self):
        """Clear semua video dengan konfirmasi"""
        if self.rowCount() == 0:
            return
        
        reply = QMessageBox.warning(self, "Clear All Videos", 
                                  "Are you sure you want to remove all videos?\n"
                                  "This will delete all videos and prompts from the database.",
                                  QMessageBox.Yes | QMessageBox.No,
                                  QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                self.db.clear_all_data()
                self.refresh_table()
                self.copied_prompts.clear()
                QMessageBox.information(self, "Cleared", "All data has been cleared")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear data: {str(e)}")
    
    def update_video_status(self, video_id: int, status: str):
        """Update status video dan refresh table"""
        try:
            self.db.update_video_status(video_id, status)
            self.refresh_table()
        except Exception as e:
            print(f"Error updating video status: {e}")
    
    def get_pending_videos(self) -> List[Dict[str, Any]]:
        """Get list video yang bisa diproses (semua video untuk generate akumulatif)"""
        all_videos = self.db.get_all_videos()
        return all_videos  # Semua video bisa di-generate akumulatif
    
    def get_selected_videos(self) -> List[Dict[str, Any]]:
        """Get list video yang dipilih (selected rows)"""
        selected_videos = []
        selected_rows = set()
        
        # Get unique selected rows
        for item in self.selectedItems():
            selected_rows.add(item.row())
        
        # Get video data for each selected row
        for row in sorted(selected_rows):
            video_id_item = self.item(row, 0)
            if video_id_item:
                video_id = video_id_item.data(Qt.UserRole)
                video = self.db.get_video_by_id(video_id)
                if video:
                    selected_videos.append(video)
        
        return selected_videos
    
    def get_ungenerated_videos(self) -> List[Dict[str, Any]]:
        """Get list video yang belum punya prompt sama sekali"""
        ungenerated_videos = []
        all_videos = self.db.get_all_videos()
        
        for video in all_videos:
            prompts = self.db.get_prompts_by_video(video['id'])
            if not prompts:  # No prompts generated yet
                ungenerated_videos.append(video)
        
        return ungenerated_videos