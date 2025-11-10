import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from app_utils.config_manager import get_config_manager


class DatabaseHelper:
    """Helper for SQLite database management"""

    def __init__(self):
        self.config = get_config_manager()
        self.db_path = self.config.get_database_filename()
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database and create tables if not exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL UNIQUE,
                    filesize INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    prompt_text TEXT NOT NULL,
                    complexity_level INTEGER NOT NULL,
                    aspect_ratio TEXT NOT NULL,
                    variation_level INTEGER NOT NULL,
                    status TEXT DEFAULT 'generated',
                    is_copied BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompts_video_id ON prompts(video_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompts_status ON prompts(status)")

            conn.commit()

    def add_video(self, filename: str, filepath: str, filesize: int = 0) -> int:
        """Add new video to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO videos (filename, filepath, filesize, status)
                VALUES (?, ?, ?, 'pending')
            """, (filename, filepath, filesize))
            return cursor.lastrowid

    def get_video_by_path(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Get video by filepath"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE filepath = ?", (filepath,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_video_status(self, video_id: int, status: str) -> None:
        """Update video status with updated_at timestamp"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE videos
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, video_id))

    def get_all_videos(self) -> List[Dict[str, Any]]:
        """Get all videos from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.*, COUNT(p.id) as prompt_count,
                       COUNT(CASE WHEN p.is_copied = 1 THEN 1 END) as copied_count
                FROM videos v
                LEFT JOIN prompts p ON v.id = p.video_id
                GROUP BY v.id
                ORDER BY v.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def delete_video(self, video_id: int) -> None:
        """Delete video and all related prompts"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))

    def add_prompt(self, video_id: int, prompt_text: str, complexity_level: int,
                   aspect_ratio: str, variation_level: int) -> int:
        """Add new prompt to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO prompts (video_id, prompt_text, complexity_level,
                                   aspect_ratio, variation_level)
                VALUES (?, ?, ?, ?, ?)
            """, (video_id, prompt_text, complexity_level, aspect_ratio, variation_level))
            return cursor.lastrowid

    def get_prompts_by_video(self, video_id: int) -> List[Dict[str, Any]]:
        """Get all prompts for specific video"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM prompts
                WHERE video_id = ?
                ORDER BY created_at DESC
            """, (video_id,))
            return [dict(row) for row in cursor.fetchall()]

    def mark_prompt_copied(self, prompt_id: int) -> None:
        """Mark prompt as copied"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE prompts
                SET is_copied = 1
                WHERE id = ?
            """, (prompt_id,))

    def get_video_with_prompts(self, video_id: int) -> Optional[Dict[str, Any]]:
        """Get video with all prompts"""
        video = self.get_video_by_id(video_id)
        if video:
            video['prompts'] = self.get_prompts_by_video(video_id)
        return video

    def get_video_by_id(self, video_id: int) -> Optional[Dict[str, Any]]:
        """Get video by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_stats(self) -> Dict[str, int]:
        """Get application statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM prompts")
            total_prompts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM prompts WHERE is_copied = 1")
            copied_prompts = cursor.fetchone()[0]

            cursor.execute("""
                SELECT status, COUNT(*)
                FROM videos
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())

            return {
                'total_videos': total_videos,
                'total_prompts': total_prompts,
                'copied_prompts': copied_prompts,
                'pending_videos': status_counts.get('pending', 0),
                'processing_videos': status_counts.get('processing', 0),
                'completed_videos': status_counts.get('completed', 0),
                'error_videos': status_counts.get('error', 0)
            }

    def clear_all_data(self) -> None:
        """Clear all data from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM prompts")
            cursor.execute("DELETE FROM videos")
            conn.commit()

    def backup_database(self, backup_path: str) -> None:
        """Backup database to another file"""
        import shutil
        shutil.copy2(self.db_path, backup_path)

    def cleanup_old_data(self, days: int = 30) -> int:
        """Cleanup old data based on days"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM videos
                WHERE created_at < datetime('now', '-{} days')
                AND status IN ('completed', 'error')
            """.format(days))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def set_app_setting(self, key: str, value: str) -> None:
        """Set application setting"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))

    def get_app_setting(self, key: str) -> str:
        """Get application setting"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else ""


# Singleton instance
_db_helper: Optional[DatabaseHelper] = None


def get_db_helper() -> DatabaseHelper:
    """Get singleton instance of DatabaseHelper"""
    global _db_helper
    if _db_helper is None:
        _db_helper = DatabaseHelper()
    return _db_helper