from PySide6.QtCore import QThread, Signal, QObject, Qt
from typing import Callable, Any, Optional
import traceback


class WorkerSignals(QObject):
    """Signals untuk worker thread"""
    started = Signal()
    finished = Signal()
    error = Signal(Exception)
    result = Signal(object)
    progress = Signal(int, str)  # progress percentage, message


class Worker(QThread):
    """Generic worker thread untuk background tasks"""
    
    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._is_running = False
    
    def run(self):
        """Execute function dalam thread terpisah"""
        try:
            self._is_running = True
            self.signals.started.emit()
            
            # Execute function dengan progress callback
            # Hanya tambahkan progress_callback jika belum ada
            if 'progress_callback' not in self.kwargs or self.kwargs['progress_callback'] is None:
                self.kwargs['progress_callback'] = self._progress_callback
            
            result = self.func(*self.args, **self.kwargs)
            self.signals.result.emit(result)
            
        except Exception as e:
            self.signals.error.emit(e)
            print(f"Worker error: {e}")
            traceback.print_exc()
        finally:
            self._is_running = False
            self.signals.finished.emit()
    
    def _progress_callback(self, percentage: int, message: str = ""):
        """Internal progress callback"""
        if self._is_running:
            self.signals.progress.emit(percentage, message)
    
    def stop(self):
        """Stop worker thread"""
        self._is_running = False
        if self.isRunning():
            self.terminate()
            self.wait(3000)  # Wait max 3 seconds


class ThreadManager:
    """Manager untuk mengelola multiple threads"""
    
    def __init__(self):
        self.active_workers = {}
        self.worker_counter = 0
    
    def start_worker(self, func: Callable, *args, **kwargs) -> str:
        """
        Start worker thread baru
        Returns worker_id untuk tracking
        """
        worker_id = f"worker_{self.worker_counter}"
        self.worker_counter += 1
        
        # Extract callbacks sebelum pass ke worker
        progress_callback = kwargs.pop('progress_callback', None)
        completion_callback = kwargs.pop('completion_callback', None)
        
        worker = Worker(func, *args, **kwargs)
        worker.signals.finished.connect(lambda: self._cleanup_worker(worker_id))
        
        # Connect progress signal jika ada callback
        if progress_callback:
            worker.signals.progress.connect(
                lambda p, m: progress_callback(p, m), 
                Qt.ConnectionType.QueuedConnection
            )
        
        # Connect completion signal jika ada callback
        if completion_callback:
            worker.signals.result.connect(
                lambda result: completion_callback(True, "Success", result), 
                Qt.ConnectionType.QueuedConnection
            )
            worker.signals.error.connect(
                lambda error: completion_callback(False, str(error), {}), 
                Qt.ConnectionType.QueuedConnection
            )
        
        self.active_workers[worker_id] = worker
        worker.start()
        
        return worker_id
    
    def get_worker(self, worker_id: str) -> Optional[Worker]:
        """Get worker berdasarkan ID"""
        return self.active_workers.get(worker_id)
    
    def stop_worker(self, worker_id: str) -> bool:
        """Stop worker berdasarkan ID"""
        worker = self.active_workers.get(worker_id)
        if worker:
            worker.stop()
            return True
        return False
    
    def stop_all_workers(self):
        """Stop semua active workers"""
        for worker in self.active_workers.values():
            worker.stop()
        self.active_workers.clear()
    
    def _cleanup_worker(self, worker_id: str):
        """Cleanup finished worker"""
        if worker_id in self.active_workers:
            del self.active_workers[worker_id]
    
    def get_active_count(self) -> int:
        """Get jumlah worker yang masih aktif"""
        return len(self.active_workers)
    
    def is_worker_running(self, worker_id: str) -> bool:
        """Check apakah worker masih running"""
        worker = self.active_workers.get(worker_id)
        return worker is not None and worker.isRunning()


# Singleton instance
_thread_manager: Optional[ThreadManager] = None


def get_thread_manager() -> ThreadManager:
    """Get singleton instance dari ThreadManager"""
    global _thread_manager
    if _thread_manager is None:
        _thread_manager = ThreadManager()
    return _thread_manager


# Convenience functions untuk common operations
def run_in_background(func: Callable, *args, **kwargs) -> str:
    """
    Shortcut untuk menjalankan function di background
    Returns worker_id
    """
    return get_thread_manager().start_worker(func, *args, **kwargs)


def stop_background_task(worker_id: str) -> bool:
    """
    Shortcut untuk stop background task
    """
    return get_thread_manager().stop_worker(worker_id)