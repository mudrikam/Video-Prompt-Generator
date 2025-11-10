import json
import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import shutil


class ConfigManager:
    """Manager for application configuration from JSON file"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.env_path = ".env"
        self.env_example_path = ".env.example"

        self._ensure_env_file()

        load_dotenv(self.env_path)

        self.load_config()

    def _ensure_env_file(self) -> None:
        """Ensure .env file exists, create from example if not"""
        if not os.path.exists(self.env_path):
            print("⚠️  .env file not found, creating from template...")

            if os.path.exists(self.env_example_path):
                shutil.copy(self.env_example_path, self.env_path)
                print(f"✓ Created {self.env_path} from {self.env_example_path}")
            else:
                with open(self.env_path, 'w', encoding='utf-8') as f:
                    f.write("# Google GenAI API Configuration\n")
                    f.write("GENAI_API_KEY=your_api_key_here\n")
                print(f"✓ Created {self.env_path} with default template")

            print("⚠️  Please edit .env file and add your actual API key!")

    def load_config(self) -> None:
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading config: {e}")

    def save_config(self) -> None:
        """Save configuration to JSON file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            raise RuntimeError(f"Error saving config: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get value from config using dot notation
        Example: get("api.genai_api_key") or get("generation.default_prompts_per_video")
        """
        keys = key_path.split('.')
        value = self._config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            if default is None:
                raise KeyError(f"Config key not found: {key_path}")
            return default

    def set(self, key_path: str, value: Any) -> None:
        """
        Set value in config using dot notation
        Example: set("api.genai_api_key", "your_api_key")
        """
        keys = key_path.split('.')
        config = self._config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value

    def get_api_key(self) -> str:
        """Get GenAI API key from environment variable"""
        api_key = os.getenv("GENAI_API_KEY", "")

        if not api_key:
            api_key = self.get("api.genai_api_key", "")

        if not api_key or api_key == "your_api_key_here":
            raise ValueError("GenAI API key not configured. Please set GENAI_API_KEY in .env file")

        return api_key

    def set_api_key(self, api_key: str) -> None:
        """Set GenAI API key to .env file"""
        os.environ["GENAI_API_KEY"] = api_key

        env_lines = []
        key_found = False

        if os.path.exists(self.env_path):
            with open(self.env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('GENAI_API_KEY='):
                        env_lines.append(f'GENAI_API_KEY={api_key}\n')
                        key_found = True
                    else:
                        env_lines.append(line)

        if not key_found:
            env_lines.append(f'GENAI_API_KEY={api_key}\n')

        with open(self.env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)

        load_dotenv(self.env_path, override=True)

    def get_model_name(self) -> str:
        """Get model name for GenAI"""
        return self.get("api.model_name")

    def get_supported_video_formats(self) -> list:
        """Get list of supported video formats"""
        return self.get("video.supported_formats")

    def get_max_file_size_mb(self) -> int:
        """Get maximum file size in MB"""
        return self.get("video.max_file_size_mb")

    def get_default_prompts_per_video(self) -> int:
        """Get default number of prompts per video"""
        return self.get("generation.default_prompts_per_video")

    def get_max_prompts_per_video(self) -> int:
        """Get maximum number of prompts per video"""
        return self.get("generation.max_prompts_per_video")

    def get_max_prompts_per_batch(self) -> int:
        """Get maximum number of prompts per batch request"""
        return self.get("generation.max_prompts_per_batch")

    def get_complexity_levels(self) -> list:
        """Get list of complexity levels"""
        return self.get("generation.complexity_levels")

    def get_aspect_ratios(self) -> dict:
        """Get dict of aspect ratios"""
        return self.get("generation.aspect_ratios")

    def get_variation_instructions(self) -> dict:
        """Get dict of variation instructions"""
        return self.get("generation.variation_instructions")

    def get_window_size(self) -> tuple:
        """Get default window size"""
        return (self.get("ui.window_width"), self.get("ui.window_height"))

    def get_status_colors(self) -> dict:
        """Get dictionary of status colors"""
        return self.get("ui.status_colors")

    def get_status_qcolors(self) -> dict:
        """Get status colors converted to Qt QColor objects.

        Returns a dict mapping status keys to QColor instances.
        """
        try:
            from PySide6.QtGui import QColor
        except Exception:
            return self.get_status_colors()

        colors = self.get_status_colors() or {}
        qcolors = {}
        for key, hexval in colors.items():
            try:
                qcolors[key] = QColor(hexval)
            except Exception:
                try:
                    parts = [int(p) for p in str(hexval).split(',')]
                    qcolors[key] = QColor(*parts)
                except Exception:
                    qcolors[key] = QColor(0, 0, 0)

        return qcolors

    def get_table_columns(self) -> list:
        """Get table column names"""
        return self.get("ui.table_columns")

    def get_database_filename(self) -> str:
        """Get database filename"""
        return self.get("database.filename")

    def get_available_models(self) -> list:
        """Get list of available models"""
        return self.get("api.available_models")

    def get_available_aspect_ratios(self) -> list:
        """Get list of available aspect ratios"""
        return self.get("generation.available_aspect_ratios")

    def get_prompts_range(self) -> tuple:
        """Get min/max for prompts per video"""
        return (self.get("generation.min_prompts_per_video"), self.get("generation.max_prompts_per_video"))

    def get_complexity_range(self) -> tuple:
        """Get min/max for complexity level"""
        return (self.get("generation.min_complexity_level"), self.get("generation.max_complexity_level"))

    def get_variation_range(self) -> tuple:
        """Get min/max for variation level"""
        return (self.get("generation.min_variation_level"), self.get("generation.max_variation_level"))

    def get_window_size_range(self) -> dict:
        """Get min/max for window size"""
        return {
            'width': (self.get("ui.min_window_width"), self.get("ui.max_window_width")),
            'height': (self.get("ui.min_window_height"), self.get("ui.max_window_height"))
        }

    def get_file_size_range(self) -> tuple:
        """Get min/max for file size"""
        return (self.get("video.min_file_size_mb"), self.get("video.max_file_size_limit"))

    def get_timeout_range(self) -> tuple:
        """Get min/max for upload timeout"""
        return (self.get("video.min_upload_timeout"), self.get("video.max_upload_timeout"))

    def get_progress_interval_range(self) -> tuple:
        """Get min/max for progress update interval"""
        return (self.get("ui.min_progress_interval"), self.get("ui.max_progress_interval"))

    def get_cleanup_days_range(self) -> tuple:
        """Get min/max for cleanup days"""
        return (self.get("database.min_cleanup_days"), self.get("database.max_cleanup_days"))

    def reload(self) -> None:
        """Reload configuration from file"""
        self.load_config()


# Singleton instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get singleton instance of ConfigManager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager