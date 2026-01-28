"""
Hot reload support for CM30 Control Panel.

Watches for file changes and triggers UI reload.
"""

import importlib
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional

# Try to import watchdog, fall back to polling if not available
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object


class JsonWatchHandler(FileSystemEventHandler):
    """Handle file system events for hot reload."""

    def __init__(self, callback: Callable[[], None], watch_patterns: tuple = (".py",)):
        super().__init__()
        self.callback = callback
        self.watch_patterns = watch_patterns
        self.last_reload = 0
        self.debounce_seconds = 0.5

    def on_modified(self, event):
        if event.is_directory:
            return

        # Check if this is a file we care about
        if not any(event.src_path.endswith(p) for p in self.watch_patterns):
            return

        # Debounce rapid changes
        now = time.time()
        if now - self.last_reload < self.debounce_seconds:
            return
        self.last_reload = now

        print(f"[hot-reload] Detected change in: {event.src_path}")
        self.callback()


class PollingWatcher:
    """Fallback file watcher using polling (when watchdog is not available)."""

    def __init__(self, path: Path, callback: Callable[[], None], watch_patterns: tuple = (".py",)):
        self.path = path
        self.callback = callback
        self.watch_patterns = watch_patterns
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.file_mtimes: Dict[str, float] = {}
        self.poll_interval = 1.0

    def start(self):
        """Start the polling watcher."""
        self.running = True
        self._scan_files()  # Initial scan
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the polling watcher."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _scan_files(self) -> Dict[str, float]:
        """Scan directory for watched files and their modification times."""
        mtimes = {}
        for pattern in self.watch_patterns:
            for filepath in self.path.rglob(f"*{pattern}"):
                try:
                    mtimes[str(filepath)] = filepath.stat().st_mtime
                except OSError:
                    pass
        return mtimes

    def _poll_loop(self):
        """Main polling loop."""
        while self.running:
            time.sleep(self.poll_interval)
            if not self.running:
                break

            new_mtimes = self._scan_files()

            # Check for changes
            for filepath, mtime in new_mtimes.items():
                old_mtime = self.file_mtimes.get(filepath)
                if old_mtime is not None and mtime > old_mtime:
                    print(f"[hot-reload] Detected change in: {filepath}")
                    self.callback()
                    break

            self.file_mtimes = new_mtimes


class HotReloader:
    """Manages hot reloading of Python modules."""

    def __init__(self, watch_path: Optional[Path] = None):
        self.watch_path = watch_path or Path(__file__).parent
        self.reload_requested = threading.Event()
        self.observer = None
        self.polling_watcher = None
        self.modules_to_reload = [
            "tools.controller.ui",
        ]

    def start_watching(self):
        """Start watching for file changes."""
        if WATCHDOG_AVAILABLE:
            self._start_watchdog()
        else:
            print("[hot-reload] watchdog not installed, using polling fallback")
            print("[hot-reload] Install watchdog for better performance: pip install watchdog")
            self._start_polling()

    def _start_watchdog(self):
        """Start watchdog-based file watching."""
        handler = JsonWatchHandler(callback=self._on_file_changed)
        self.observer = Observer()
        self.observer.schedule(handler, str(self.watch_path), recursive=True)
        self.observer.start()
        print(f"[hot-reload] Watching {self.watch_path} for changes")

    def _start_polling(self):
        """Start polling-based file watching."""
        self.polling_watcher = PollingWatcher(
            path=self.watch_path,
            callback=self._on_file_changed,
        )
        self.polling_watcher.start()
        print(f"[hot-reload] Polling {self.watch_path} for changes")

    def stop_watching(self):
        """Stop watching for file changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2.0)
            self.observer = None
        if self.polling_watcher:
            self.polling_watcher.stop()
            self.polling_watcher = None

    def _on_file_changed(self):
        """Called when a watched file changes."""
        self.reload_requested.set()

    def check_reload(self) -> bool:
        """Check if a reload was requested and clear the flag."""
        if self.reload_requested.is_set():
            self.reload_requested.clear()
            return True
        return False

    def trigger_reload(self):
        """Manually trigger a reload."""
        self.reload_requested.set()

    def reload_modules(self) -> bool:
        """
        Reload the watched modules.
        Returns True if successful, False otherwise.
        """
        success = True
        for module_name in self.modules_to_reload:
            if module_name in sys.modules:
                try:
                    module = sys.modules[module_name]
                    importlib.reload(module)
                    print(f"[hot-reload] Reloaded: {module_name}")
                except Exception as e:
                    print(f"[hot-reload] Error reloading {module_name}: {e}")
                    success = False
        return success
