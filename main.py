import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QObject, Signal, Slot
import qtawesome as qta

# On Windows, set an explicit AppUserModelID so the app groups/appears correctly
# in the Windows taskbar (and uses the correct icon/grouping). This must be
# called before any windows are created.
def set_windows_appusermodelid(appid: str) -> None:
    """Set the current process AppUserModelID on Windows (no-op on other OS).

    appid: a reverse-DNS style identifier, e.g. 'com.mycompany.videoprompt'.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes
        # Use the wide-char API
        func = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        try:
            func.argtypes = [ctypes.c_wchar_p]
        except Exception:
            # Some python builds may not allow argtypes assignment; ignore
            pass
        func.restype = ctypes.HRESULT
        func(appid)
    except Exception as e:
        # Do not crash the app if this fails; just log.
        print(f"Warning: could not set AppUserModelID: {e}")

# Add current directory to path untuk import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from user_interface.main_window import MainWindow
from ai_engine.prompt_generator import get_prompt_generator
from app_utils.config_manager import get_config_manager
from data_manager.database_helper import get_db_helper


class GenerationSignals(QObject):
    """Signals untuk handle generation completion di main thread"""
    completed = Signal(bool, str, dict)  # success, message, stats


class VideoPromptApp:
    """Main application class"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Video Prompt Generator")
        self.app.setApplicationVersion("1.0")
        
        # Set application icon
        self.app.setWindowIcon(qta.icon('fa5s.video'))
        
        # Generation signals untuk thread-safe callback
        self.generation_signals = GenerationSignals()
        self.generation_signals.completed.connect(self.on_generation_completed)
        
        # Initialize components
        self.config = None
        self.db = None
        self.prompt_generator = None
        self.main_window = None
        
        # Setup application
        self.setup_application()
    
    def setup_application(self):
        """Setup application components"""
        try:
            # Initialize config manager
            self.config = get_config_manager()
            print("✓ Configuration loaded")
            
            # Initialize database
            self.db = get_db_helper()
            print("✓ Database initialized")
            
            # Initialize prompt generator
            self.prompt_generator = get_prompt_generator()
            print("✓ Prompt generator ready")
            
            # Create main window
            self.main_window = MainWindow()
            self.connect_signals()
            print("✓ Main window created")
            
            # Check API key pada startup
            self.check_initial_setup()
            
        except Exception as e:
            QMessageBox.critical(None, "Initialization Error", 
                               f"Failed to initialize application: {str(e)}")
            sys.exit(1)
    
    def connect_signals(self):
        """Connect signals antara components"""
        # Connect main window generation request ke prompt generator
        self.main_window.generation_requested.connect(self.start_generation)
        
        # Connect window close event
        self.app.aboutToQuit.connect(self.cleanup)
    
    def start_generation(self, generation_params: dict):
        """Handle generation request dari main window"""
        try:
            # Validate parameters
            is_valid, error_msg = self.prompt_generator.validate_generation_params(generation_params)
            if not is_valid:
                QMessageBox.warning(self.main_window, "Invalid Parameters", error_msg)
                self.main_window.reset_generation_ui()
                return
            
            # Start generation
            worker_id = self.prompt_generator.start_generation(
                generation_params,
                progress_callback=self.main_window.update_generation_progress,
                completion_callback=lambda success, message, stats: 
                    self.generation_signals.completed.emit(success, message, stats)
            )
            
            self.main_window.current_worker_id = worker_id
            
        except Exception as e:
            QMessageBox.critical(self.main_window, "Generation Error", str(e))
            self.main_window.reset_generation_ui()
    
    @Slot(bool, str, dict)
    def on_generation_completed(self, success: bool, message: str, stats: dict):
        """Handle ketika generation selesai - dipanggil dari main thread via signal"""
        # Update main window
        self.main_window.on_generation_finished(success, message)
        
        # Hanya show error dialog, success cukup terlihat di UI
        if not success:
            print(f"Generation failed: {message}")
            QMessageBox.critical(self.main_window, "Generation Failed", message)
        else:
            # Print success ke console, tidak perlu dialog
            print(f"Generation completed successfully! "
                 f"Processed: {stats.get('processed_videos', 0)} videos, "
                 f"Generated: {stats.get('successful_prompts', 0)} prompts, "
                 f"Failed: {stats.get('failed_videos', 0)} videos")
    
    def check_initial_setup(self):
        """Check setup awal aplikasi"""
        try:
            # Check API key from .env
            try:
                api_key = self.config.get_api_key()
            except ValueError:
                api_key = ""
            
            if not api_key or api_key == "your_api_key_here":
                QMessageBox.information(self.main_window, "Welcome", 
                                      "Welcome to Video Prompt Generator!\n\n"
                                      "Please configure your GenAI API key:\n"
                                      "1. Edit .env file in project folder, OR\n"
                                      "2. Go to Settings → API Settings\n\n"
                                      "Your API key will be stored securely in .env file.")
        except Exception:
            pass  # Ignore errors pada startup check
    
    def cleanup(self):
        """Cleanup sebelum aplikasi ditutup"""
        try:
            # Stop any running generation
            if self.prompt_generator and self.prompt_generator.is_generation_active():
                self.prompt_generator.stop_generation()
            
            print("✓ Application cleanup completed")
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def run(self):
        """Run aplikasi"""
        # Show main window
        self.main_window.show()
        
        # Start Qt event loop
        return self.app.exec_()


def main():
    """Entry point aplikasi"""
    print("Starting Video Prompt Generator...")
    
    # Set AppUserModelID on Windows so taskbar grouping/icon works as expected.
    # Assumption: use a stable reverse-DNS identifier for the app.
    set_windows_appusermodelid("com.videoprompt.generator")

    try:
        app = VideoPromptApp()
        exit_code = app.run()
        print("Application closed")
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
