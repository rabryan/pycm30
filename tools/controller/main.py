#!/usr/bin/env python3
"""
CM30 Control Panel - DearPyGUI Implementation with Hot Reload

A real-time control panel for the Olympus CM30 incubation monitor.

Keyboard Controls:
    Arrow Keys  - Move stage in X/Y direction
    U / D       - Move Z up / down
    + / -       - Increase / decrease move step
    H / L       - Set high / low resolution
    F           - Autofocus
    P           - Switch to preview mode (faster, lower quality)
    O           - Switch to full capture mode (slower, higher quality)
    1           - LED 1 on
    2           - LED 2 on
    0           - LEDs off
    S           - Toggle power saving mode
    Space       - Toggle continuous image capture
    I           - Toggle image metadata panel
    R           - Reload UI (hot reload)
    Q / Escape  - Quit

Hot Reload:
    The UI is automatically reloaded when ui.py is modified.
    Press 'R' to manually trigger a reload.
    Modify tools/controller/ui.py to customize the interface.

Usage:
    python -m tools.controller.main [hostname]
    python tools/controller/main.py [hostname]
"""

import time
import threading
import argparse
from collections import deque
from pathlib import Path

import numpy as np
import dearpygui.dearpygui as dpg

from pycm30 import cm30_api as api
from tools.controller import ui
from tools.controller.hot_reload import HotReloader


class CM30Controller:
    """Controller for CM30 with DearPyGUI interface."""

    def __init__(self, hostname: str = "localhost", port: int = 8080):
        self.hostname = hostname
        self.port = port
        self.move_step = 500
        self.z_step = 10
        self.image_capture_fun = api.get_image
        self.capture_mode = "full"
        self.running = True
        self.image_queue = deque(maxlen=2)
        self.current_image = None
        self.image_width = 2048
        self.image_height = 1536
        self.last_capture_time_ms = 0
        self.stage_x = 0
        self.stage_y = 0
        self.stage_z = 0
        self.light_mode = "off"
        self.power_saving = False
        self.capture_enabled = True  # Continuous capture on/off
        self.head_info = {}
        self.head_info_update_interval = 2.0  # seconds
        self.last_head_info_update = 0
        self.image_metadata = {}  # EXIF/metadata from captured image
        self.show_metadata_panel = False

        # Initialize API connection
        print(f"Connecting to {hostname}:{port}")
        api.init(hostname, port)
        api.set_power_saving(False)
        api.set_light_params("off")
        api.set_resolution(self.image_width, self.image_height)

        # Get initial stage position and head info
        self._update_stage_position()
        self._update_head_info()

    def _update_stage_position(self):
        """Update cached stage position."""
        try:
            xy = api.get_stage_xy()
            self.stage_x = xy.get("x", 0)
            self.stage_y = xy.get("y", 0)
            z_info = api.get_stage_z()
            self.stage_z = z_info.get("z", 0)
        except Exception as e:
            print(f"Error getting stage position: {e}")

    def move_rel(self, dx: int, dy: int):
        """Move stage relative to current position."""
        new_x = self.stage_x + dx
        new_y = self.stage_y + dy
        print(f"Moving to {new_x}, {new_y}")
        try:
            api.xy_move(new_x, new_y)
            self.stage_x = new_x
            self.stage_y = new_y
        except Exception as e:
            print(f"Move error: {e}")

    def move_z_rel(self, dz: int):
        """Move Z axis relative to current position."""
        new_z = self.stage_z + dz
        print(f"Moving Z to {new_z}")
        try:
            api.z_move(new_z)
            self.stage_z = new_z
        except Exception as e:
            print(f"Z move error: {e}")

    def set_resolution(self, high: bool):
        """Set image resolution."""
        if high:
            self.image_width, self.image_height = 2048, 1536
        else:
            self.image_width, self.image_height = 640, 480
        api.set_resolution(self.image_width, self.image_height)
        print(f"Resolution set to {self.image_width}x{self.image_height}")

    def set_capture_mode(self, preview: bool):
        """Set capture mode (preview or full)."""
        if preview:
            self.image_capture_fun = api.get_image_preview
            self.capture_mode = "preview"
        else:
            self.image_capture_fun = api.get_image
            self.capture_mode = "full"
        print(f"Capture mode: {self.capture_mode}")

    def set_light(self, mode: str):
        """Set light mode."""
        api.set_light_params(mode)
        self.light_mode = mode
        print(f"Light mode: {mode}")

    def do_autofocus(self):
        """Perform autofocus."""
        print("Autofocusing...")
        try:
            api.autofocus()
            self._update_stage_position()
            print(f"Focused at Z={self.stage_z}")
        except Exception as e:
            print(f"Autofocus error: {e}")

    def toggle_power_saving(self):
        """Toggle power saving mode."""
        self.power_saving = not self.power_saving
        try:
            api.set_power_saving(self.power_saving)
            print(f"Power saving: {'ON' if self.power_saving else 'OFF'}")
        except Exception as e:
            print(f"Power saving error: {e}")
            self.power_saving = not self.power_saving  # Revert on error

    def toggle_capture(self):
        """Toggle continuous image capture on/off."""
        self.capture_enabled = not self.capture_enabled
        print(f"Continuous capture: {'ON' if self.capture_enabled else 'OFF'}")

    def _update_head_info(self):
        """Update head info from API."""
        try:
            self.head_info = api.get_head_info()
            # Sync power_saving state from head info
            if isinstance(self.head_info, dict):
                self.power_saving = self.head_info.get("power_saving", False)
        except Exception as e:
            print(f"Error getting head info: {e}")

    def maybe_update_head_info(self):
        """Update head info if enough time has passed."""
        now = time.time()
        if now - self.last_head_info_update > self.head_info_update_interval:
            self._update_head_info()
            self.last_head_info_update = now

    def capture_image(self):
        """Capture a single image and return as numpy array."""
        try:
            tstart = time.time()
            img = self.image_capture_fun()
            self.last_capture_time_ms = int(1000 * (time.time() - tstart))

            # Extract image metadata
            self._extract_image_metadata(img)

            # Convert PIL image to numpy array (RGBA format for DearPyGUI)
            img_rgba = img.convert("RGBA")
            img_array = np.array(img_rgba, dtype=np.float32) / 255.0
            return img_array
        except Exception as e:
            print(f"Capture error: {e}")
            return None

    def _extract_image_metadata(self, img):
        """Extract EXIF and other metadata from PIL Image."""
        from PIL.ExifTags import TAGS
        metadata = {}

        # Basic image info
        metadata["size"] = f"{img.width} x {img.height}"
        metadata["mode"] = img.mode
        metadata["format"] = img.format or "N/A"

        # Try to get EXIF data
        try:
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    # Skip binary/large data
                    if isinstance(value, bytes) and len(value) > 100:
                        value = f"<{len(value)} bytes>"
                    elif isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8", errors="replace")
                        except Exception:
                            value = f"<{len(value)} bytes>"
                    metadata[tag] = value
        except Exception:
            pass

        # Try getexif() for newer PIL versions
        try:
            exif = img.getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag not in metadata:
                        if isinstance(value, bytes) and len(value) > 100:
                            value = f"<{len(value)} bytes>"
                        elif isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8", errors="replace")
                            except Exception:
                                value = f"<{len(value)} bytes>"
                        metadata[tag] = value
        except Exception:
            pass

        # Get any other info from img.info dict
        if hasattr(img, "info") and img.info:
            for key, value in img.info.items():
                if key not in metadata:
                    if isinstance(value, bytes) and len(value) > 100:
                        value = f"<{len(value)} bytes>"
                    elif isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8", errors="replace")
                        except Exception:
                            value = f"<{len(value)} bytes>"
                    metadata[f"info.{key}"] = value

        self.image_metadata = metadata

    def toggle_metadata_panel(self):
        """Toggle the metadata info panel visibility."""
        self.show_metadata_panel = not self.show_metadata_panel
        print(f"Metadata panel: {'visible' if self.show_metadata_panel else 'hidden'}")

    def image_capture_thread(self):
        """Background thread for continuous image capture."""
        while self.running:
            if self.capture_enabled:
                img_array = self.capture_image()
                if img_array is not None:
                    self.image_queue.append(img_array)
                time.sleep(0.05)  # Small delay between captures
            else:
                time.sleep(0.1)  # Longer sleep when paused


class GUIManager:
    """Manages the DearPyGUI interface with hot reload support."""

    def __init__(self, controller: CM30Controller, hot_reloader: HotReloader):
        self.controller = controller
        self.hot_reloader = hot_reloader
        self.texture_created = False
        self.current_tex_width = 0
        self.current_tex_height = 0
        self.placeholder_removed = False

    def create_or_update_texture(self, img_array):
        """Create texture on first call, update dimensions if needed."""
        h, w = img_array.shape[:2]
        flat_data = img_array.flatten()

        if not self.texture_created:
            # First time: create the texture
            with dpg.texture_registry():
                dpg.add_dynamic_texture(
                    width=w,
                    height=h,
                    default_value=flat_data,
                    tag="live_texture",
                )
            # Add image widget to display area
            dpg.add_image("live_texture", parent="image_container", tag="live_image")
            self.texture_created = True
            self.current_tex_width = w
            self.current_tex_height = h
        elif w != self.current_tex_width or h != self.current_tex_height:
            # Resolution changed: recreate texture
            dpg.delete_item("live_image")
            dpg.delete_item("live_texture")
            with dpg.texture_registry():
                dpg.add_dynamic_texture(
                    width=w,
                    height=h,
                    default_value=flat_data,
                    tag="live_texture",
                )
            dpg.add_image("live_texture", parent="image_container", tag="live_image")
            self.current_tex_width = w
            self.current_tex_height = h
        else:
            # Same size: just update the texture data
            dpg.set_value("live_texture", flat_data)

    def rebuild_ui(self):
        """Rebuild the UI after a hot reload."""
        try:
            # Store texture state
            had_texture = self.texture_created

            # Delete existing main window contents (but preserve texture)
            if dpg.does_item_exist("main_window"):
                dpg.delete_item("main_window")

            # Rebuild window using (potentially reloaded) ui module
            ui.build_main_window(self.controller)

            # Re-add image to new container if we had one
            if had_texture and dpg.does_item_exist("live_texture"):
                if dpg.does_item_exist("image_container"):
                    # Clear placeholder
                    for child in dpg.get_item_children("image_container", 1) or []:
                        dpg.delete_item(child)
                    dpg.add_image("live_texture", parent="image_container", tag="live_image")

            dpg.set_primary_window("main_window", True)
            ui.show_reload_message("UI Reloaded!")
            print("[hot-reload] UI rebuilt successfully")
            return True
        except Exception as e:
            print(f"[hot-reload] Error rebuilding UI: {e}")
            return False

    def on_key_press(self, _sender, app_data):
        """Handle key press events."""
        key = app_data
        controller = self.controller

        # Arrow keys
        if key == dpg.mvKey_Up:
            controller.move_rel(0, -controller.move_step)
        elif key == dpg.mvKey_Down:
            controller.move_rel(0, controller.move_step)
        elif key == dpg.mvKey_Left:
            controller.move_rel(-controller.move_step, 0)
        elif key == dpg.mvKey_Right:
            controller.move_rel(controller.move_step, 0)
        # Z movement
        elif key == dpg.mvKey_U:
            controller.move_z_rel(controller.z_step)
        elif key == dpg.mvKey_D:
            controller.move_z_rel(-controller.z_step)
        # Step size
        elif key == dpg.mvKey_Plus:
            controller.move_step += 100
            print(f"Move step: {controller.move_step}")
        elif key == dpg.mvKey_Minus:
            controller.move_step = max(10, controller.move_step - 100)
            print(f"Move step: {controller.move_step}")
        # Resolution
        elif key == dpg.mvKey_H:
            controller.set_resolution(high=True)
        elif key == dpg.mvKey_L:
            controller.set_resolution(high=False)
        # Autofocus
        elif key == dpg.mvKey_F:
            controller.do_autofocus()
        # Capture mode
        elif key == dpg.mvKey_P:
            controller.set_capture_mode(preview=True)
        elif key == dpg.mvKey_O:
            controller.set_capture_mode(preview=False)
        # Lighting
        elif key == dpg.mvKey_1:
            controller.set_light("led1_on")
        elif key == dpg.mvKey_2:
            controller.set_light("led2_on")
        elif key == dpg.mvKey_0:
            controller.set_light("off")
        # Power saving
        elif key == dpg.mvKey_S:
            controller.toggle_power_saving()
        # Toggle continuous capture
        elif key == dpg.mvKey_Spacebar:
            controller.toggle_capture()
        # Toggle metadata panel
        elif key == dpg.mvKey_I:
            controller.toggle_metadata_panel()
        # Hot reload
        elif key == dpg.mvKey_R:
            print("[hot-reload] Manual reload triggered")
            self.hot_reloader.trigger_reload()
        # Quit
        elif key == dpg.mvKey_Q or key == dpg.mvKey_Escape:
            controller.running = False
            dpg.stop_dearpygui()


def create_gui(controller: CM30Controller, enable_hot_reload: bool = True):
    """Create and run the DearPyGUI interface."""
    dpg.create_context()

    # Set up hot reload
    watch_path = Path(__file__).parent.parent.parent
    print(watch_path)
    hot_reloader = HotReloader(watch_path)
    gui_manager = GUIManager(controller, hot_reloader)

    # Set up key handler
    with dpg.handler_registry():
        dpg.add_key_press_handler(callback=gui_manager.on_key_press)

    # Build initial UI
    ui.build_main_window(controller)

    # Configure viewport
    dpg.create_viewport(title="CM30 Control Panel", width=1920, height=1200)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)

    # Start image capture thread
    capture_thread = threading.Thread(target=controller.image_capture_thread, daemon=True)
    capture_thread.start()

    # Start hot reload watcher
    if enable_hot_reload:
        hot_reloader.start_watching()

    # Clear reload message after a delay
    reload_message_time = 0

    # Main render loop
    while dpg.is_dearpygui_running() and controller.running:
        # Check for hot reload
        if hot_reloader.check_reload():
            if hot_reloader.reload_modules():
                # Re-import ui module to get fresh reference
                import importlib
                import tools.controller.ui
                importlib.reload(tools.controller.ui)
                from tools.controller import ui as ui_fresh
                globals()['ui'] = ui_fresh

                gui_manager.rebuild_ui()
                reload_message_time = time.time()

        # Clear reload message after 2 seconds
        if reload_message_time and time.time() - reload_message_time > 2.0:
            try:
                dpg.set_value("status_reload", "")
            except Exception:
                pass
            reload_message_time = 0

        # Update image if available
        if controller.image_queue:
            img_array = controller.image_queue.popleft()

            # Remove placeholder text on first image
            if not gui_manager.placeholder_removed:
                if dpg.does_item_exist("image_container"):
                    for child in dpg.get_item_children("image_container", 1) or []:
                        dpg.delete_item(child)
                gui_manager.placeholder_removed = True

            gui_manager.create_or_update_texture(img_array)

        # Periodically update head info
        controller.maybe_update_head_info()

        # Update status display
        try:
            ui.update_status(controller)
        except Exception:
            pass  # UI might be rebuilding

        dpg.render_dearpygui_frame()

    # Cleanup
    controller.running = False
    hot_reloader.stop_watching()
    dpg.destroy_context()


def main():
    parser = argparse.ArgumentParser(description="CM30 Control Panel")
    parser.add_argument("hostname", nargs="?", default="localhost", help="CM30 API server hostname")
    parser.add_argument("--port", type=int, default=8001, help="CM30 API server port")
    parser.add_argument("--no-hot-reload", action="store_true", help="Disable hot reload")
    args = parser.parse_args()

    controller = CM30Controller(hostname=args.hostname, port=args.port)
    create_gui(controller, enable_hot_reload=not args.no_hot_reload)


if __name__ == "__main__":
    main()
