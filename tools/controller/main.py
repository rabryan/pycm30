#!/usr/bin/env python3
"""
CM30 Control Panel - DearPyGUI Implementation

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
    Q / Escape  - Quit

Usage:
    python -m tools.controller.main [hostname]
    python tools/controller/main.py [hostname]
"""

import time
import threading
import argparse
from collections import deque

import numpy as np
import dearpygui.dearpygui as dpg

from pycm30 import cm30_api as api


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

        # Initialize API connection
        print(f"Connecting to {hostname}:{port}")
        api.init(hostname, port)
        api.set_power_saving(False)
        api.set_light_params("off")
        api.set_resolution(self.image_width, self.image_height)

        # Get initial stage position
        self._update_stage_position()

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

    def capture_image(self):
        """Capture a single image and return as numpy array."""
        try:
            tstart = time.time()
            img = self.image_capture_fun()
            self.last_capture_time_ms = int(1000 * (time.time() - tstart))

            # Convert PIL image to numpy array (RGBA format for DearPyGUI)
            img_rgba = img.convert("RGBA")
            img_array = np.array(img_rgba, dtype=np.float32) / 255.0
            return img_array
        except Exception as e:
            print(f"Capture error: {e}")
            return None

    def image_capture_thread(self):
        """Background thread for continuous image capture."""
        while self.running:
            img_array = self.capture_image()
            if img_array is not None:
                self.image_queue.append(img_array)
            time.sleep(0.05)  # Small delay between captures


def create_gui(controller: CM30Controller):
    """Create and run the DearPyGUI interface."""
    dpg.create_context()

    # Texture will be created lazily when first image arrives
    texture_created = False
    current_tex_width = 0
    current_tex_height = 0

    def create_or_update_texture(img_array):
        """Create texture on first call, update dimensions if needed."""
        nonlocal texture_created, current_tex_width, current_tex_height

        h, w = img_array.shape[:2]
        flat_data = img_array.flatten()

        if not texture_created:
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
            texture_created = True
            current_tex_width = w
            current_tex_height = h
        elif w != current_tex_width or h != current_tex_height:
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
            current_tex_width = w
            current_tex_height = h
        else:
            # Same size: just update the texture data
            dpg.set_value("live_texture", flat_data)

    # Key handler
    def on_key_press(_sender, app_data):
        key = app_data

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
        elif key == dpg.mvKey_Plus:# FIXMNE not a valid dpg key:  key == dpg.mvKey_Equal:
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
        # Quit
        elif key == dpg.mvKey_Q or key == dpg.mvKey_Escape:
            controller.running = False
            dpg.stop_dearpygui()

    with dpg.handler_registry():
        dpg.add_key_press_handler(callback=on_key_press)

    # Main window
    with dpg.window(label="CM30 Control Panel", tag="main_window"):
        # Status bar
        with dpg.group(horizontal=True):
            dpg.add_text("Position:", color=(150, 150, 150))
            dpg.add_text("X: 0", tag="status_x")
            dpg.add_text("Y: 0", tag="status_y")
            dpg.add_text("Z: 0", tag="status_z")
            dpg.add_spacer(width=20)
            dpg.add_text("Step:", color=(150, 150, 150))
            dpg.add_text("500", tag="status_step")
            dpg.add_spacer(width=20)
            dpg.add_text("Mode:", color=(150, 150, 150))
            dpg.add_text("full", tag="status_mode")
            dpg.add_spacer(width=20)
            dpg.add_text("Light:", color=(150, 150, 150))
            dpg.add_text("off", tag="status_light")
            dpg.add_spacer(width=20)
            dpg.add_text("Capture:", color=(150, 150, 150))
            dpg.add_text("0 ms", tag="status_capture_time")

        dpg.add_separator()

        # Control buttons
        with dpg.group(horizontal=True):
            dpg.add_button(label="Autofocus (F)", callback=lambda: controller.do_autofocus())
            dpg.add_button(label="High Res (H)", callback=lambda: controller.set_resolution(True))
            dpg.add_button(label="Low Res (L)", callback=lambda: controller.set_resolution(False))
            dpg.add_button(label="LED1 (1)", callback=lambda: controller.set_light("led1_on"))
            dpg.add_button(label="LED2 (2)", callback=lambda: controller.set_light("led2_on"))
            dpg.add_button(label="LED Off (0)", callback=lambda: controller.set_light("off"))

        dpg.add_separator()

        # Help text
        with dpg.collapsing_header(label="Keyboard Shortcuts", default_open=False):
            dpg.add_text("Arrow Keys: Move stage XY")
            dpg.add_text("U/D: Move Z up/down")
            dpg.add_text("+/-: Adjust move step")
            dpg.add_text("H/L: High/Low resolution")
            dpg.add_text("F: Autofocus")
            dpg.add_text("P/O: Preview/Original capture mode")
            dpg.add_text("1/2/0: LED1/LED2/Off")
            dpg.add_text("Q/Esc: Quit")

        dpg.add_separator()

        # Image display container (texture added dynamically)
        with dpg.group(tag="image_container"):
            dpg.add_text("Waiting for first image...")

    # Configure viewport
    dpg.create_viewport(title="CM30 Control Panel", width=1920, height=1200)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)

    # Start image capture thread
    capture_thread = threading.Thread(target=controller.image_capture_thread, daemon=True)
    capture_thread.start()

    # Track if we've removed the placeholder text
    placeholder_removed = False

    # Main render loop
    while dpg.is_dearpygui_running() and controller.running:
        # Update image if available
        if controller.image_queue:
            img_array = controller.image_queue.popleft()

            # Remove placeholder text on first image
            if not placeholder_removed:
                for child in dpg.get_item_children("image_container", 1) or []:
                    dpg.delete_item(child)
                placeholder_removed = True

            create_or_update_texture(img_array)

        # Update status display
        dpg.set_value("status_x", f"X: {controller.stage_x}")
        dpg.set_value("status_y", f"Y: {controller.stage_y}")
        dpg.set_value("status_z", f"Z: {controller.stage_z}")
        dpg.set_value("status_step", str(controller.move_step))
        dpg.set_value("status_mode", controller.capture_mode)
        dpg.set_value("status_light", controller.light_mode)
        dpg.set_value("status_capture_time", f"{controller.last_capture_time_ms} ms")

        dpg.render_dearpygui_frame()

    controller.running = False
    dpg.destroy_context()


def main():
    parser = argparse.ArgumentParser(description="CM30 Control Panel")
    parser.add_argument("hostname", nargs="?", default="localhost", help="CM30 API server hostname")
    parser.add_argument("--port", type=int, default=8001, help="CM30 API server port")
    args = parser.parse_args()

    controller = CM30Controller(hostname=args.hostname, port=args.port)
    create_gui(controller)


if __name__ == "__main__":
    main()
