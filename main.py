"""Video Prompt Generator application entry point.

Initializes the Qt application, wiring between UI and engine, and starts the
event loop.
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QObject, Signal, Slot
import qtawesome as qta

def set_windows_appusermodelid(appid: str) -> None:
    """Set the current process AppUserModelID on Windows (no-op on other OS).

    Use a reverse-DNS identifier, e.g. 'com.mycompany.videoprompt'. This helps
    Windows group the app correctly on the taskbar. Failure to set this is
    non-fatal and will be logged.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes

        func = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        try:
            func.argtypes = [ctypes.c_wchar_p]
        except Exception:
            pass
        func.restype = ctypes.HRESULT
        func(appid)
    except Exception as e:
        print(f"Warning: could not set AppUserModelID: {e}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from user_interface.main_window import MainWindow
from ai_engine.prompt_generator import get_prompt_generator
from app_utils.config_manager import get_config_manager
from data_manager.database_helper import get_db_helper


class GenerationSignals(QObject):
    """Signals to handle generation completion in main thread"""
    completed = Signal(bool, str, dict)


class VideoPromptApp:
    """Main application class"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Video Prompt Generator")
        self.app.setApplicationVersion("1.0")

        self.app.setWindowIcon(qta.icon("fa5s.video"))

        self.generation_signals = GenerationSignals()
        self.generation_signals.completed.connect(self.on_generation_completed)

        self.config = None
        self.db = None
        self.prompt_generator = None
        self.main_window = None

        self.setup_application()

    def setup_application(self):
        """Initialize components and prepare the main window."""
        try:
            self.config = get_config_manager()

            self.db = get_db_helper()

            self.prompt_generator = get_prompt_generator()

            self.main_window = MainWindow()
            self.connect_signals()

            self.check_initial_setup()

        except Exception as e:
            QMessageBox.critical(None, "Initialization Error",
                                 f"Failed to initialize application: {str(e)}")
            sys.exit(1)

    def connect_signals(self):
        """Wire UI signals to application handlers."""
        self.main_window.generation_requested.connect(self.start_generation)
        self.app.aboutToQuit.connect(self.cleanup)

    def start_generation(self, generation_params: dict):
        """Start a prompt-generation task requested by the UI."""
        try:
            is_valid, error_msg = self.prompt_generator.validate_generation_params(
                generation_params
            )
            if not is_valid:
                QMessageBox.warning(self.main_window, "Invalid Parameters", error_msg)
                self.main_window.reset_generation_ui()
                return

            worker_id = self.prompt_generator.start_generation(
                generation_params,
                progress_callback=self.main_window.update_generation_progress,
                completion_callback=lambda success, message, stats:
                self.generation_signals.completed.emit(success, message, stats),
            )

            self.main_window.current_worker_id = worker_id

        except Exception as e:
            QMessageBox.critical(self.main_window, "Generation Error", str(e))
            self.main_window.reset_generation_ui()

    @Slot(bool, str, dict)
    def on_generation_completed(self, success: bool, message: str, stats: dict):
        """Called in main thread when a generation worker finishes."""
        self.main_window.on_generation_finished(success, message)

        if not success:
            print(f"Generation failed: {message}")
        else:
            print(
                "Generation completed successfully! "
                f"Processed: {stats.get('processed_videos', 0)} videos, "
                f"Generated: {stats.get('successful_prompts', 0)} prompts, "
                f"Failed: {stats.get('failed_videos', 0)} videos"
            )

    def check_initial_setup(self):
        """Verify initial configuration like the API key and notify the user."""
        try:
            try:
                api_key = self.config.get_api_key()
            except ValueError:
                api_key = ""

            if not api_key or api_key == "your_api_key_here":
                QMessageBox.information(
                    self.main_window,
                    "Welcome",
                    "Welcome to Video Prompt Generator!\n\n"
                    "Please configure your GenAI API key:\n"
                    "1. Edit .env file in project folder, OR\n"
                    "2. Go to Settings → API Settings\n\n"
                    "Your API key will be stored securely in .env file.",
                )
        except Exception:
            pass

    def cleanup(self):
        """Perform cleanup before application exit."""
        try:
            if self.prompt_generator and self.prompt_generator.is_generation_active():
                self.prompt_generator.stop_generation()
        except Exception as e:
            print(f"Cleanup error: {e}")

    def run(self):
        """Show the main window and run the Qt event loop."""
        self.main_window.show()
        return self.app.exec_()


def main():
    """Application entry point."""
    set_windows_appusermodelid("com.videoprompt.generator")

    try:
        app = VideoPromptApp()
        exit_code = app.run()
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
