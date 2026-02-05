#!/usr/bin/env python3
"""
CM30 Control Panel - DearPyGUI Implementation with Hot Reload

A real-time control panel for the Olympus CM30 incubation monitor.

Keyboard Controls:
    Arrow Keys  - Move stage in X/Y direction
    U / D       - Move Z up / down
    + / -       - Increase / decrease XY move step
    [ / ]       - Decrease / increase Z step (multiples of 1.5625)
    H / L       - Set high / low resolution
    F           - Autofocus
    P           - Switch to preview mode (faster, lower quality)
    O           - Switch to full capture mode (slower, higher quality)
    1           - LED 1 on
    2           - LED 2 on
    0           - LEDs off
    E           - Toggle exposure mode (manual/continuous)
    Shift+E     - Toggle exposure lock
    < / >       - Decrease / increase shutter speed
    PgUp / PgDn - Increase / decrease ISO
    S           - Toggle power saving mode
    Space       - Toggle continuous image capture
    I           - Toggle image metadata panel
    A           - Toggle image adjustments panel
    T           - Toggle image statistics panel
    Shift+X     - Set current XY as reference position
    Shift+R     - Set current Z as reference plane
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
from typing import Optional, Tuple

import numpy as np
import dearpygui.dearpygui as dpg

from pycm30 import cm30_api as api
from tools.controller import ui
from tools.controller.hot_reload import HotReloader
from tools.controller.stitching import (
    TileManager, StitchCanvas, GridScanner, GridScanConfig,
    ZStackManager, StitchSession, PyramidExporter, ScanState
)
from tools.controller.well_plate import (
    PlateScanManager, LabelScanConfig, LabelScanState,
    PlateGridScanConfig, LabelReference
)


class CM30Controller:
    """Controller for CM30 with DearPyGUI interface."""

    # Z step minimum - all z_step values must be multiples of this
    Z_STEP_MIN = 1.5625

    def __init__(self, hostname: str = "localhost", port: int = 8080):
        self.hostname = hostname
        self.port = port
        self.move_step = 500
        self.z_step = self.Z_STEP_MIN  # Default to minimum step
        self.image_capture_fun = api.get_image
        self.capture_mode = "full"
        self.running = True
        self.image_queue = deque(maxlen=2)
        self.current_image: np.ndarray | None = None
        self.image_width = 2048
        self.image_height = 1536
        self.last_capture_time_ms = 0
        self.stage_x = 0
        self.stage_y = 0
        self.stage_z = 0
        self.x_ref = 0  # Reference X position for relative positioning
        self.y_ref = 0  # Reference Y position for relative positioning
        self.z_ref = 0.0  # Reference Z plane for relative positioning
        self.light_mode = "off"
        self.power_saving = False
        self.capture_enabled = True  # Continuous capture on/off
        self._capture_ready = threading.Event()
        self._capture_ready.set()  # Start ready - clear during movement/autofocus
        self.head_info = {}
        self.head_info_update_interval = 2.0  # seconds
        self.last_head_info_update = 0
        self.image_metadata = {}  # EXIF/metadata from captured image
        self.show_metadata_panel = False

        # Exposure settings
        self.exposure_mode = "manual"  # 'manual' or 'continuous'
        self.iso = 100
        self.shutter_speed_denominator = 30  # 1/30 second
        self.exposure_locked = False

        # Valid values for exposure settings (from API)
        self.VALID_SS_DENOMINATORS = [
            8, 10, 13, 15, 20, 25, 30, 40, 50, 60, 80, 100, 125, 160, 200,
            250, 320, 400, 500, 640, 800, 1000, 1250, 1600, 2000, 2500,
            3200, 4000, 5000, 6400, 8000
        ]
        self.VALID_ISO = [100, 125, 160, 200, 250, 320, 400, 500, 640, 800]

        # Image adjustment settings (display only, not camera)
        self.show_adjustments_panel = False
        self.brightness = 0.0  # -1.0 to 1.0
        self.contrast = 1.0    # 0.5 to 2.0
        self.saturation = 1.0  # 0.0 to 2.0
        self.gamma = 1.0       # 0.5 to 2.0

        # Image statistics panel
        self.show_stats_panel = False
        self.image_stats = {}  # Computed image statistics

        # XY range for position overlay (stage units)
        # These define the full travel range of the stage
        self.x_min = 0
        self.x_max = 65535
        self.y_min = 0
        self.y_max = 65535

        # Field of view size in stage units (approximate)
        # These represent how much area the camera sees at current position
        self.fov_width = 3000   # Approximate FOV width
        self.fov_height = 2250  # Approximate FOV height (4:3 aspect)

        # Stitching system
        self.tile_manager = TileManager()
        self.tile_manager.fov_width = self.fov_width
        self.tile_manager.fov_height = self.fov_height
        self.stitch_canvas = StitchCanvas(width=180, height=180)  # Fit in overlay
        self.auto_stitch = False  # Auto-capture tiles as we move
        self.stitch_save_full_res = False  # Save full-res tiles to disk
        self.last_stitch_position = (0, 0)  # Last position where we captured a tile
        self.stitch_position_threshold = 2000  # Min movement before auto-capturing new tile

        # Grid scanning
        self.grid_scanner: GridScanner | None = None
        self.scan_in_progress = False

        # Z-stack support
        self.z_stack_manager = ZStackManager(self.tile_manager)
        self.z_stack_enabled = False
        self.z_stack_range = 50.0  # Total Z range
        self.z_stack_steps = 5  # Number of Z planes

        # Session persistence
        self.session_manager = StitchSession(str(Path.home() / ".pycm30" / "sessions"))

        # ROI navigation (click-to-move)
        self.roi_click_enabled = True

        # Well plate scanning
        self.plate_manager = PlateScanManager(
            fov_width=self.fov_width,
            fov_height=self.fov_height
        )
        self.label_scan_in_progress = False
        self.current_label_scan: str | None = None

        # Initialize API connection
        print(f"Connecting to {hostname}:{port}")
        api.init(hostname, port)
        api.set_power_saving(False)
        api.set_light_params("off")
        api.set_resolution(self.image_width, self.image_height)

        # Get initial stage position, head info, and exposure settings
        self._update_stage_position()
        self._update_head_info()
        self._update_exposure_settings()
        
            
        # Set references to current position on startup
        self.set_xy_reference()
        self.set_z_reference()

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
        self._capture_ready.clear()
        try:
            api.xy_move(new_x, new_y)
            self.stage_x = new_x
            self.stage_y = new_y
            self._wait_for_xy_move()
        except Exception as e:
            print(f"Move error: {e}")
        finally:
            self._capture_ready.set()

    def move_z_rel(self, dz: float):
        """Move Z axis relative to current position."""
        z_info = api.get_stage_z()
        self.stage_z = z_info.get("z", 0)
        new_z = self.stage_z + dz
        print(f"Moving Z to {new_z:.4f}")
        self._capture_ready.clear()
        try:
            api.z_move(new_z)
            self._wait_for_z_move()
        except Exception as e:
            print(f"Z move error: {e}")
        finally:
            self._capture_ready.set()

    def _wait_for_z_move(self, poll_interval: float = 0.05):
        """Wait for Z movement to complete, updating stage_z while moving."""
        while True:
            try:
                z_info = api.get_stage_z()
                self.stage_z = z_info.get("z", self.stage_z)
                if not z_info.get("is_moving", False):
                    break
                time.sleep(poll_interval)
            except Exception as e:
                print(f"Error polling Z position: {e}")
                break

    def _wait_for_xy_move(self, poll_interval: float = 0.05):
        """Wait for XY movement to complete, updating stage position while moving."""
        while True:
            try:
                xy_info = api.get_stage_xy()
                self.stage_x = xy_info.get("x", self.stage_x)
                self.stage_y = xy_info.get("y", self.stage_y)
                if not xy_info.get("is_moving", False):
                    break
                time.sleep(poll_interval)
            except Exception as e:
                print(f"Error polling XY position: {e}")
                break

    @property
    def x_rel(self) -> int:
        """Get X position relative to reference."""
        return self.stage_x - self.x_ref

    @property
    def y_rel(self) -> int:
        """Get Y position relative to reference."""
        return self.stage_y - self.y_ref

    @property
    def z_rel(self) -> float:
        """Get Z position relative to reference plane."""
        return self.stage_z - self.z_ref

    @property
    def xy_range_x(self) -> tuple:
        """Get X axis range as (min, max) tuple."""
        return (self.x_min, self.x_max)

    @property
    def xy_range_y(self) -> tuple:
        """Get Y axis range as (min, max) tuple."""
        return (self.y_min, self.y_max)

    def set_xy_range(self, x_min: int, x_max: int, y_min: int, y_max: int):
        """Set the XY range for the position overlay."""
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        print(f"XY range set to X:[{x_min}-{x_max}] Y:[{y_min}-{y_max}]")

    def set_fov_size(self, width: int, height: int):
        """Set the field of view size in stage units."""
        self.fov_width = width
        self.fov_height = height
        print(f"FOV size set to {width}x{height}")

    def center_xy_range(self, span: int = 10000):
        """Center the XY range on current position with given span."""
        half_span = span // 2
        self.x_min = self.stage_x - half_span
        self.x_max = self.stage_x + half_span
        self.y_min = self.stage_y - half_span
        self.y_max = self.stage_y + half_span
        print(f"XY range centered on ({self.stage_x}, {self.stage_y}) with span {span}")

    def zoom_xy_range(self, factor: float):
        """Zoom the XY range by a factor (< 1 zooms in, > 1 zooms out)."""
        # Calculate current center
        center_x = (self.x_min + self.x_max) // 2
        center_y = (self.y_min + self.y_max) // 2

        # Calculate current span and apply zoom factor
        span_x = self.x_max - self.x_min
        span_y = self.y_max - self.y_min
        new_span_x = int(span_x * factor)
        new_span_y = int(span_y * factor)

        # Limit minimum and maximum span
        new_span_x = max(1000, min(100000, new_span_x))
        new_span_y = max(1000, min(100000, new_span_y))

        # Apply new range centered on current center
        self.x_min = center_x - new_span_x // 2
        self.x_max = center_x + new_span_x // 2
        self.y_min = center_y - new_span_y // 2
        self.y_max = center_y + new_span_y // 2
        print(f"XY range zoomed to span {new_span_x}x{new_span_y}")

    # === Stitching Methods ===

    def toggle_auto_stitch(self):
        """Toggle automatic tile capture as we move."""
        self.auto_stitch = not self.auto_stitch
        print(f"Auto-stitch: {'ON' if self.auto_stitch else 'OFF'}")

    def capture_stitch_tile(self, image: np.ndarray | None = None):
        """Manually capture current position as a stitch tile.

        Args:
            image: Image to use, or None to use current_image
        """
        if image is None:
            image = self.current_image
        if image is None:
            print("No image available for stitch tile")
            return

        tile = self.tile_manager.add_tile(
            x=self.stage_x,
            y=self.stage_y,
            z=self.stage_z,
            image=image,
            save_full_res=self.stitch_save_full_res
        )
        if tile:
            self.last_stitch_position = (self.stage_x, self.stage_y)
            print(f"Captured stitch tile at ({self.stage_x}, {self.stage_y}), total: {self.tile_manager.tile_count}")

    def maybe_auto_capture_tile(self, image: np.ndarray):
        """Auto-capture a tile if we've moved enough (called during image capture)."""
        if not self.auto_stitch:
            return

        # Check if we've moved enough from last capture
        dx = abs(self.stage_x - self.last_stitch_position[0])
        dy = abs(self.stage_y - self.last_stitch_position[1])

        if dx > self.stitch_position_threshold or dy > self.stitch_position_threshold:
            self.capture_stitch_tile(image)

    def clear_stitch_tiles(self):
        """Clear all captured stitch tiles."""
        self.tile_manager.clear()
        self.stitch_canvas.clear()
        self.last_stitch_position = (self.stage_x, self.stage_y)
        print("Stitch tiles cleared")

    def fit_range_to_tiles(self):
        """Set the XY range to fit all captured tiles."""
        if self.tile_manager.tile_count == 0:
            print("No tiles to fit")
            return

        bounds = self.tile_manager.get_bounds()
        x_min, y_min, x_max, y_max = bounds

        # Add some padding
        pad_x = (x_max - x_min) * 0.1
        pad_y = (y_max - y_min) * 0.1

        self.x_min = int(x_min - pad_x)
        self.x_max = int(x_max + pad_x)
        self.y_min = int(y_min - pad_y)
        self.y_max = int(y_max + pad_y)

        print(f"Range fit to tiles: X[{self.x_min}-{self.x_max}] Y[{self.y_min}-{self.y_max}]")

    def export_stitch_preview(self, output_path: str | None = None):
        """Export a preview image of the stitched tiles."""
        from tools.controller.stitching import StitchExporter

        if output_path is None:
            output_path = f"stitch_preview_{int(time.time())}.png"

        if StitchExporter.export_preview(self.tile_manager, output_path):
            print(f"Exported stitch preview to {output_path}")
        else:
            print("Export failed (no tiles?)")

    def get_stitch_canvas_data(self) -> np.ndarray:
        """Get the stitched canvas data for the overlay."""
        # Update canvas view to match current overlay range
        self.stitch_canvas.set_view(self.x_min, self.y_min, self.x_max, self.y_max)
        return self.stitch_canvas.render(self.tile_manager)

    # === Grid Scanning Methods ===

    def setup_grid_scan(self, x_min: int = None, y_min: int = None,
                        x_max: int = None, y_max: int = None,
                        overlap_pct: float = 10.0):
        """Set up a grid scan with the given parameters.

        If bounds are not specified, uses current overlay range.
        """
        if x_min is None:
            x_min = self.x_min
        if y_min is None:
            y_min = self.y_min
        if x_max is None:
            x_max = self.x_max
        if y_max is None:
            y_max = self.y_max

        config = GridScanConfig(
            x_min=x_min, y_min=y_min,
            x_max=x_max, y_max=y_max,
            overlap_pct=overlap_pct,
            z_stack_enabled=self.z_stack_enabled,
            z_stack_range=self.z_stack_range,
            z_stack_steps=self.z_stack_steps,
            autofocus_interval=0 #autfocus never
        )

        self.grid_scanner = GridScanner(
            config,
            fov_width=self.fov_width,
            fov_height=self.fov_height
        )

        print(f"Grid scan configured: {self.grid_scanner.total_positions} positions, "
              f"{self.grid_scanner.total_captures} total captures")

    def start_grid_scan(self):
        """Start or resume the grid scan."""
        if not self.grid_scanner:
            # Set up with default parameters
            self.setup_grid_scan()

        if self.grid_scanner:
            self.grid_scanner.start()
            self.scan_in_progress = True
            print("Grid scan started")

    def pause_grid_scan(self):
        """Pause the grid scan."""
        if self.grid_scanner:
            self.grid_scanner.pause()
            self.scan_in_progress = False
            print("Grid scan paused")

    def cancel_grid_scan(self):
        """Cancel the grid scan."""
        if self.grid_scanner:
            self.grid_scanner.cancel()
            self.scan_in_progress = False
            print("Grid scan cancelled")

    def process_grid_scan_step(self):
        """Process one step of the grid scan. Called from main loop."""
        if not self.grid_scanner or not self.scan_in_progress:
            return

        if self.grid_scanner.state != ScanState.RUNNING:
            self.scan_in_progress = False
            if self.grid_scanner.state == ScanState.COMPLETED:
                print(f"Grid scan completed: {self.grid_scanner.tiles_captured} tiles captured")
            return

        # Get next position
        next_pos = self.grid_scanner.get_next_position()
        if not next_pos:
            return

        x, y, z_offsets = next_pos

        self._capture_ready.clear()
        try:
            # Check if autofocus needed
            if self.grid_scanner.should_autofocus():
                api.autofocus()
                self._wait_for_z_move()

            # Move to position and wait for completion
            api.xy_move(x, y)
            self.stage_x = x
            self.stage_y = y
            self._wait_for_xy_move()

            # Capture at each Z offset (Z-stack)
            if len(z_offsets) > 1:
                stack_id = self.z_stack_manager.start_stack(x, y)
                for z_idx, z_offset in enumerate(z_offsets):
                    z_target = self.stage_z + z_offset
                    api.z_move(z_target)
                    self._wait_for_z_move()

                    # Capture image
                    img = self.capture_image()
                    if img is not None:
                        self.z_stack_manager.add_to_stack(
                            x, y, z_target, img, z_idx,
                            save_full_res=self.stitch_save_full_res
                        )
                self.z_stack_manager.end_stack()
            else:
                # Single plane capture
                img = self.capture_image()
                if img is not None:
                    self.tile_manager.add_tile(
                        x, y, self.stage_z, img,
                        save_full_res=self.stitch_save_full_res
                    )
        finally:
            self._capture_ready.set()

        # Advance scanner
        self.grid_scanner.advance(success=True)

    @property
    def scan_progress(self) -> float:
        """Get grid scan progress (0-100)."""
        if self.grid_scanner:
            return self.grid_scanner.progress
        return 0.0

    @property
    def scan_eta(self) -> str:
        """Get formatted ETA for grid scan."""
        if not self.grid_scanner:
            return "--"
        eta_sec = self.grid_scanner.eta_seconds
        if eta_sec <= 0:
            return "--"
        minutes = int(eta_sec // 60)
        seconds = int(eta_sec % 60)
        return f"{minutes}:{seconds:02d}"

    # === Z-Stack Methods ===

    def toggle_z_stack(self):
        """Toggle Z-stack capture mode."""
        self.z_stack_enabled = not self.z_stack_enabled
        print(f"Z-stack: {'ON' if self.z_stack_enabled else 'OFF'} "
              f"({self.z_stack_steps} planes, {self.z_stack_range}um range)")

    def set_z_stack_params(self, range_um: float = None, steps: int = None):
        """Set Z-stack parameters."""
        if range_um is not None:
            self.z_stack_range = range_um
        if steps is not None:
            self.z_stack_steps = max(2, steps)
        print(f"Z-stack params: {self.z_stack_steps} planes, {self.z_stack_range}um range")

    def capture_z_stack(self):
        """Capture a Z-stack at the current position."""
        z_offsets = np.linspace(
            -self.z_stack_range / 2,
            self.z_stack_range / 2,
            self.z_stack_steps
        )

        center_z = self.stage_z
        stack_id = self.z_stack_manager.start_stack(self.stage_x, self.stage_y)

        print(f"Capturing Z-stack: {self.z_stack_steps} planes...")
        self._capture_ready.clear()
        try:
            for z_idx, z_offset in enumerate(z_offsets):
                z_target = center_z + z_offset
                api.z_move(z_target)
                self._wait_for_z_move()

                img = self.capture_image()
                if img is not None:
                    self.z_stack_manager.add_to_stack(
                        self.stage_x, self.stage_y, z_target, img, z_idx,
                        save_full_res=self.stitch_save_full_res
                    )
                print(f"  Plane {z_idx + 1}/{self.z_stack_steps}")

            # Return to center
            api.z_move(center_z)
            self._wait_for_z_move()
        finally:
            self._capture_ready.set()

        self.z_stack_manager.end_stack()
        print(f"Z-stack captured: {stack_id}")
        return stack_id

    def compute_edf(self, stack_id: str = None) -> np.ndarray | None:
        """Compute Extended Depth of Field for a Z-stack."""
        if stack_id is None:
            # Find most recent stack
            stacks = set(t.z_stack_id for t in self.tile_manager.tiles.values()
                        if t.z_stack_id)
            if not stacks:
                print("No Z-stacks available")
                return None
            stack_id = max(stacks)

        edf = self.z_stack_manager.compute_edf(stack_id)
        if edf is not None:
            print(f"EDF computed for {stack_id}")
        return edf

    # === Session Management ===

    def save_session(self, name: str = "session"):
        """Save current session to disk."""
        self.session_manager.save(self.tile_manager, name)

    def load_session(self, name: str = "session"):
        """Load a session from disk."""
        loaded = self.session_manager.load(name)
        if loaded:
            self.tile_manager = loaded
            self.tile_manager.fov_width = self.fov_width
            self.tile_manager.fov_height = self.fov_height
            self.z_stack_manager.tile_manager = self.tile_manager
            self.stitch_canvas.clear()
            print(f"Session '{name}' loaded with {self.tile_manager.tile_count} tiles")

    def list_sessions(self) -> list:
        """List available sessions."""
        sessions = self.session_manager.list_sessions()
        print(f"Available sessions: {sessions}")
        return sessions

    # === ROI Navigation (Click to Move) ===

    def navigate_to_overlay_position(self, click_x: float, click_y: float,
                                     overlay_width: int, overlay_height: int):
        """Navigate to a position based on click coordinates on the overlay.

        Args:
            click_x, click_y: Click position in overlay coordinates
            overlay_width, overlay_height: Overlay dimensions
        """
        if not self.roi_click_enabled:
            return

        # Convert click to stage coordinates
        range_x = self.x_max - self.x_min
        range_y = self.y_max - self.y_min

        stage_x = int(self.x_min + (click_x / overlay_width) * range_x)
        stage_y = int(self.y_min + (click_y / overlay_height) * range_y)

        print(f"Navigating to ({stage_x}, {stage_y})")
        self._capture_ready.clear()
        try:
            api.xy_move(stage_x, stage_y)
            self.stage_x = stage_x
            self.stage_y = stage_y
            self._wait_for_xy_move()
        except Exception as e:
            print(f"Navigation error: {e}")
        finally:
            self._capture_ready.set()

    # === Export Methods ===

    def export_deep_zoom(self, output_dir: str = None):
        """Export stitched image as Deep Zoom format."""
        if output_dir is None:
            output_dir = f"deepzoom_{int(time.time())}"

        exporter = PyramidExporter(self.tile_manager)

        def progress_cb(pct):
            print(f"Export progress: {pct:.1f}%")

        if exporter.export_deep_zoom(output_dir, progress_callback=progress_cb):
            print(f"Deep Zoom export complete: {output_dir}")
        else:
            print("Export failed")

    def export_tiff_pyramid(self, output_path: str = None):
        """Export stitched image as pyramidal TIFF."""
        if output_path is None:
            output_path = f"stitch_{int(time.time())}.tiff"

        exporter = PyramidExporter(self.tile_manager)

        def progress_cb(pct):
            print(f"Export progress: {pct:.1f}%")

        if exporter.export_tiff_pyramid(output_path, progress_callback=progress_cb):
            print(f"TIFF export complete: {output_path}")
        else:
            print("Export failed")

    def toggle_quality_display(self):
        """Toggle quality indicator display on stitch canvas."""
        self.stitch_canvas.show_quality = not self.stitch_canvas.show_quality
        print(f"Quality display: {'ON' if self.stitch_canvas.show_quality else 'OFF'}")

    # === Well Plate Scanning Methods ===

    def add_label_reference(self, well_name: str, approx_x: int = None, approx_y: int = None):
        """Add a reference label for plate alignment.

        If coordinates not specified, uses current stage position.
        """
        if approx_x is None:
            approx_x = self.stage_x
        if approx_y is None:
            approx_y = self.stage_y

        self.plate_manager.add_reference_label(well_name, approx_x, approx_y)

    def start_label_scan(self, well_name: str = None):
        """Start scanning a reference label.

        Args:
            well_name: Label to scan (e.g., "B12"). If None, scans next pending label.
        """
        if well_name is None:
            pending = self.plate_manager.get_pending_labels()
            if not pending:
                print("No pending labels to scan")
                return
            well_name = pending[0]

        if self.plate_manager.start_label_scan(well_name):
            self.label_scan_in_progress = True
            self.current_label_scan = well_name

            # Configure for low-res if specified
            if self.plate_manager.label_scanner.config.use_low_res:
                self.set_resolution(high=False)

            print(f"Started label scan for {well_name}")

    def process_label_scan_step(self):
        """Process one step of label scanning. Called from main loop."""
        if not self.label_scan_in_progress:
            return

        scanner = self.plate_manager.label_scanner

        if scanner.is_complete:
            self.label_scan_in_progress = False
            return

        # Get next position
        next_pos = scanner.get_next_position()
        if next_pos is None:
            # Finalize and stitch
            result = scanner.finalize_scan()
            if result:
                print(f"Label {result.well_name} scanned: "
                      f"({result.measured_x}, {result.measured_y}), z={result.measured_z}")
            self.label_scan_in_progress = False
            return

        x, y = next_pos
        scanner.state = LabelScanState.MOVING

        self._capture_ready.clear()
        try:
            # Move to position and wait for completion
            api.xy_move(x, y)
            self.stage_x = x
            self.stage_y = y
            self._wait_for_xy_move()

            # Autofocus if enabled
            if scanner.config.autofocus_enabled:
                scanner.state = LabelScanState.FOCUSING
                api.autofocus()
                self._wait_for_z_move()

            # Capture
            scanner.state = LabelScanState.CAPTURING
            img = self.capture_image()
            if img is not None:
                scanner.add_capture(x, y, self.stage_z, img)
        finally:
            self._capture_ready.set()

        scanner.advance()

    def scan_all_pending_labels(self):
        """Queue scanning of all pending reference labels."""
        pending = self.plate_manager.get_pending_labels()
        if pending:
            print(f"Will scan {len(pending)} labels: {pending}")
            self.start_label_scan(pending[0])
        else:
            print("No pending labels")

    def compute_plate_alignment(self):
        """Compute plate alignment from scanned labels."""
        if self.plate_manager.compute_plate_alignment():
            print("Plate alignment computed successfully")
            print(self.plate_manager.get_alignment_report())
        else:
            print("Failed to compute alignment - need more scanned labels")

    def navigate_to_well(self, well_name: str):
        """Navigate to a specific well.

        Args:
            well_name: Well name (e.g., "A1", "H12")
        """
        pos = self.plate_manager.get_well_position(well_name)
        if pos:
            x, y = pos
            print(f"Moving to well {well_name} at ({x}, {y})")
            self._capture_ready.clear()
            try:
                api.xy_move(x, y)
                self.stage_x = x
                self.stage_y = y
                self._wait_for_xy_move()
            except Exception as e:
                print(f"Well navigation error: {e}")
            finally:
                self._capture_ready.set()
        else:
            print(f"Invalid well name or plate not aligned: {well_name}")

    def setup_plate_scan(self, wells: list = None, row: str = None, column: int = None):
        """Set up a well plate scan.

        Args:
            wells: List of well names to scan, or None for all wells
            row: Scan a single row (e.g., "A", "B")
            column: Scan a single column (e.g., 1, 12)
        """
        if row:
            config = PlateGridScanConfig.row(row)
        elif column:
            config = PlateGridScanConfig.column(column)
        elif wells:
            config = PlateGridScanConfig(wells=wells)
        else:
            config = PlateGridScanConfig.all_wells()

        self.plate_manager.setup_well_scan(config)

    def start_plate_scan(self):
        """Start the plate well scan."""
        if self.plate_manager.grid_scanner:
            self.plate_manager.grid_scanner.start()
            print("Plate scan started")

    def get_label_scan_progress(self) -> float:
        """Get current label scan progress."""
        return self.plate_manager.label_scanner.progress

    def get_plate_alignment_report(self) -> str:
        """Get plate alignment status report."""
        return self.plate_manager.get_alignment_report()

    def export_label_images(self, output_dir: str = None):
        """Export captured label images."""
        if output_dir is None:
            output_dir = f"labels_{int(time.time())}"
        self.plate_manager.export_label_images(output_dir)

    def get_current_well(self) -> str | None:
        """Get the well name at current stage position."""
        return self.plate_manager.plate.stage_to_well(self.stage_x, self.stage_y)

    def set_xy_reference(self):
        """Set current XY position as the reference."""
        self.x_ref = self.stage_x
        self.y_ref = self.stage_y
        print(f"XY reference set to ({self.x_ref}, {self.y_ref}) (x_rel, y_rel now 0)")

    def set_z_reference(self):
        """Set current Z position as the reference plane."""
        self.z_ref = self.stage_z
        print(f"Z reference set to {self.z_ref:.4f} (z_rel now 0)")

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
        """Perform autofocus and wait for completion."""
        print("Autofocusing...")
        self._capture_ready.clear()
        try:
            api.autofocus()
            self._wait_for_z_move()
            print(f"Autofocus complete at Z={self.stage_z:.4f}")
        except Exception as e:
            print(f"Autofocus error: {e}")
        finally:
            self._capture_ready.set()

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

    def increase_z_step(self):
        """Increase Z step by one minimum step unit."""
        self.z_step += self.Z_STEP_MIN
        # Round to avoid floating point errors
        self.z_step = round(self.z_step / self.Z_STEP_MIN) * self.Z_STEP_MIN
        print(f"Z step: {self.z_step:.4f}")

    def decrease_z_step(self):
        """Decrease Z step by one minimum step unit (minimum is Z_STEP_MIN)."""
        new_step = self.z_step - self.Z_STEP_MIN
        if new_step >= self.Z_STEP_MIN:
            self.z_step = round(new_step / self.Z_STEP_MIN) * self.Z_STEP_MIN
        else:
            self.z_step = self.Z_STEP_MIN
        print(f"Z step: {self.z_step:.4f}")

    def set_z_step_multiplier(self, multiplier: int):
        """Set Z step to a specific multiple of the minimum step."""
        if multiplier >= 1:
            self.z_step = self.Z_STEP_MIN * multiplier
            print(f"Z step: {self.z_step:.4f} ({multiplier}x)")

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

    def _update_exposure_settings(self):
        """Fetch current exposure settings from API."""
        try:
            settings = api.get_exposure_settings()
            if isinstance(settings, dict):
                self.exposure_mode = settings.get("mode", "manual")
                self.iso = settings.get("iso_sensitivity", 100)
                self.shutter_speed_denominator = settings.get("shutter_speed_denominator", 30)
                self.exposure_locked = settings.get("is_locked", False)
        except Exception as e:
            print(f"Error getting exposure settings: {e}")

    def set_exposure(self, iso: Optional[int] = None, shutter_speed: Optional[int] = None, mode: Optional[str] = None):
        """Set exposure settings."""
        if iso is not None:
            self.iso = iso
        if shutter_speed is not None:
            self.shutter_speed_denominator = shutter_speed
        if mode is not None:
            self.exposure_mode = mode

        try:
            api.set_exposure_settings(
                iso=self.iso,
                shutter_speed_denominator=self.shutter_speed_denominator,
                mode=self.exposure_mode
            )
            print(f"Exposure: ISO {self.iso}, 1/{self.shutter_speed_denominator}s, mode={self.exposure_mode}")
        except Exception as e:
            print(f"Error setting exposure: {e}")

    def increase_iso(self):
        """Increase ISO to next valid value."""
        try:
            idx = self.VALID_ISO.index(self.iso)
            if idx < len(self.VALID_ISO) - 1:
                self.set_exposure(iso=self.VALID_ISO[idx + 1])
        except ValueError:
            # Current ISO not in list, set to first valid
            self.set_exposure(iso=self.VALID_ISO[0])

    def decrease_iso(self):
        """Decrease ISO to previous valid value."""
        try:
            idx = self.VALID_ISO.index(self.iso)
            if idx > 0:
                self.set_exposure(iso=self.VALID_ISO[idx - 1])
        except ValueError:
            self.set_exposure(iso=self.VALID_ISO[0])

    def increase_shutter_speed(self):
        """Increase shutter speed (shorter exposure, higher denominator)."""
        try:
            idx = self.VALID_SS_DENOMINATORS.index(self.shutter_speed_denominator)
            if idx < len(self.VALID_SS_DENOMINATORS) - 1:
                self.set_exposure(shutter_speed=self.VALID_SS_DENOMINATORS[idx + 1])
        except ValueError:
            self.set_exposure(shutter_speed=self.VALID_SS_DENOMINATORS[0])

    def decrease_shutter_speed(self):
        """Decrease shutter speed (longer exposure, lower denominator)."""
        try:
            idx = self.VALID_SS_DENOMINATORS.index(self.shutter_speed_denominator)
            if idx > 0:
                self.set_exposure(shutter_speed=self.VALID_SS_DENOMINATORS[idx - 1])
        except ValueError:
            self.set_exposure(shutter_speed=self.VALID_SS_DENOMINATORS[0])

    def toggle_exposure_mode(self):
        """Toggle between manual and continuous exposure mode."""
        new_mode = "continuous" if self.exposure_mode == "manual" else "manual"
        self.set_exposure(mode=new_mode)

    def toggle_exposure_lock(self):
        """Toggle exposure lock."""
        try:
            if self.exposure_locked:
                api.exposure_unlock()
                self.exposure_locked = False
                print("Exposure unlocked")
            else:
                api.exposure_lock()
                self.exposure_locked = True
                print("Exposure locked")
        except Exception as e:
            print(f"Error toggling exposure lock: {e}")

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

            # Store for manual stitch capture and auto-stitch
            self.current_image = img_array

            # Auto-capture tile if enabled and moved enough
            self.maybe_auto_capture_tile(img_array)

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

    def toggle_adjustments_panel(self):
        """Toggle the image adjustments panel visibility."""
        self.show_adjustments_panel = not self.show_adjustments_panel
        print(f"Adjustments panel: {'visible' if self.show_adjustments_panel else 'hidden'}")

    def toggle_stats_panel(self):
        """Toggle the image statistics panel visibility."""
        self.show_stats_panel = not self.show_stats_panel
        print(f"Stats panel: {'visible' if self.show_stats_panel else 'hidden'}")

    def compute_image_stats(self, img_array: np.ndarray):
        """Compute statistics for a grayscale microscope image.

        Computes metrics useful for microscopy:
        - Brightness stats (mean, median, std, min, max)
        - Contrast metrics (Michelson, RMS, dynamic range)
        - Focus quality (Laplacian variance, gradient magnitude)
        - Histogram analysis (entropy, percentiles, saturation)
        - Distribution shape (skewness, kurtosis)
        """
        # Convert to grayscale (0-255 range for stats)
        if img_array.shape[2] >= 3:
            # Use luminance weights for grayscale conversion
            gray = (0.299 * img_array[:, :, 0] +
                    0.587 * img_array[:, :, 1] +
                    0.114 * img_array[:, :, 2])
        else:
            gray = img_array[:, :, 0]

        # Convert to 0-255 range for intuitive values
        gray_255 = (gray * 255).astype(np.float32)
        flat = gray_255.flatten()

        stats = {}

        # === Brightness Statistics ===
        stats["mean"] = float(np.mean(flat))
        stats["median"] = float(np.median(flat))
        stats["std"] = float(np.std(flat))
        stats["min"] = float(np.min(flat))
        stats["max"] = float(np.max(flat))

        # === Percentiles (useful for effective dynamic range) ===
        stats["p5"] = float(np.percentile(flat, 5))
        stats["p95"] = float(np.percentile(flat, 95))
        stats["effective_range"] = stats["p95"] - stats["p5"]

        # === Contrast Metrics ===
        # Dynamic range
        stats["dynamic_range"] = stats["max"] - stats["min"]

        # Michelson contrast: (max - min) / (max + min)
        if (stats["max"] + stats["min"]) > 0:
            stats["michelson_contrast"] = (stats["max"] - stats["min"]) / (stats["max"] + stats["min"])
        else:
            stats["michelson_contrast"] = 0.0

        # RMS contrast (normalized std)
        stats["rms_contrast"] = stats["std"] / 255.0

        # === Saturation Detection ===
        stats["pct_underexposed"] = float(np.sum(flat < 5) / len(flat) * 100)
        stats["pct_overexposed"] = float(np.sum(flat > 250) / len(flat) * 100)

        # === Entropy (information content) ===
        # Higher entropy = more detail/texture
        hist, _ = np.histogram(flat, bins=256, range=(0, 256))
        hist = hist / hist.sum()  # Normalize to probabilities
        hist = hist[hist > 0]  # Remove zeros for log
        stats["entropy"] = float(-np.sum(hist * np.log2(hist)))

        # === Focus/Sharpness Metrics ===
        # Laplacian variance - higher = sharper/more in focus
        # Use simple 3x3 Laplacian kernel
        laplacian_kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
        # Convolve manually (simple implementation)
        h, w = gray_255.shape
        if h > 4 and w > 4:
            # Pad and convolve
            padded = np.pad(gray_255, 1, mode='edge')
            laplacian = np.zeros_like(gray_255)
            for i in range(3):
                for j in range(3):
                    laplacian += laplacian_kernel[i, j] * padded[i:i+h, j:j+w]
            stats["laplacian_var"] = float(np.var(laplacian))
            stats["focus_measure"] = float(np.var(laplacian))  # Alias for clarity
        else:
            stats["laplacian_var"] = 0.0
            stats["focus_measure"] = 0.0

        # Gradient magnitude (edge strength) - Sobel-like
        if h > 2 and w > 2:
            gx = gray_255[:, 2:] - gray_255[:, :-2]  # Horizontal gradient
            gy = gray_255[2:, :] - gray_255[:-2, :]  # Vertical gradient
            # Match dimensions
            gx = gx[1:-1, :]
            gy = gy[:, 1:-1]
            gradient_mag = np.sqrt(gx**2 + gy**2)
            stats["gradient_mean"] = float(np.mean(gradient_mag))
            stats["gradient_std"] = float(np.std(gradient_mag))
        else:
            stats["gradient_mean"] = 0.0
            stats["gradient_std"] = 0.0

        # === Distribution Shape ===
        # Skewness (asymmetry: 0=symmetric, >0=right tail, <0=left tail)
        if stats["std"] > 0:
            stats["skewness"] = float(np.mean(((flat - stats["mean"]) / stats["std"]) ** 3))
            # Kurtosis (peakedness: 3=normal, >3=peaked, <3=flat)
            stats["kurtosis"] = float(np.mean(((flat - stats["mean"]) / stats["std"]) ** 4))
        else:
            stats["skewness"] = 0.0
            stats["kurtosis"] = 0.0

        self.image_stats = stats

    def set_brightness(self, value: float):
        """Set brightness adjustment (-1.0 to 1.0)."""
        self.brightness = max(-1.0, min(1.0, value))

    def set_contrast(self, value: float):
        """Set contrast adjustment (0.5 to 2.0)."""
        self.contrast = max(0.5, min(2.0, value))

    def set_saturation(self, value: float):
        """Set saturation adjustment (0.0 to 2.0)."""
        self.saturation = max(0.0, min(2.0, value))

    def set_gamma(self, value: float):
        """Set gamma adjustment (0.5 to 2.0)."""
        self.gamma = max(0.5, min(2.0, value))

    def reset_adjustments(self):
        """Reset all image adjustments to defaults."""
        self.brightness = 0.0
        self.contrast = 1.0
        self.saturation = 1.0
        self.gamma = 1.0
        print("Image adjustments reset")

    def apply_adjustments(self, img_array: np.ndarray) -> np.ndarray:
        """Apply brightness, contrast, saturation, and gamma adjustments to image."""
        # Skip if all defaults
        if (self.brightness == 0.0 and self.contrast == 1.0 and
            self.saturation == 1.0 and self.gamma == 1.0):
            return img_array

        result = img_array.copy()

        # Separate RGB and alpha
        rgb = result[:, :, :3]
        alpha = result[:, :, 3:4] if result.shape[2] == 4 else None

        # Apply brightness (add to all channels)
        if self.brightness != 0.0:
            rgb = rgb + self.brightness

        # Apply contrast (scale around 0.5 midpoint)
        if self.contrast != 1.0:
            rgb = (rgb - 0.5) * self.contrast + 0.5

        # Apply saturation (blend with grayscale)
        if self.saturation != 1.0:
            gray = np.mean(rgb, axis=2, keepdims=True)
            rgb = gray + self.saturation * (rgb - gray)

        # Apply gamma correction
        if self.gamma != 1.0:
            rgb = np.clip(rgb, 0, 1)
            rgb = np.power(rgb, 1.0 / self.gamma)

        # Clamp values and recombine
        rgb = np.clip(rgb, 0, 1)
        if alpha is not None:
            result = np.concatenate([rgb, alpha], axis=2)
        else:
            result = rgb

        return result.astype(np.float32)

    def image_capture_thread(self):
        """Background thread for continuous image capture.

        Skips capture when the stage is moving or autofocus is in progress
        (signalled by _capture_ready being cleared).
        """
        while self.running:
            if self.capture_enabled and self._capture_ready.is_set():
                img_array = self.capture_image()
                if img_array is not None:
                    self.image_queue.append(img_array)
                time.sleep(0.05)  # Small delay between captures
            else:
                time.sleep(0.1)  # Longer sleep when paused or stage busy


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
        # XY Step size
        elif key == dpg.mvKey_Plus or key == dpg.mvKey_Add:
            controller.move_step += 100
            print(f"Move step: {controller.move_step}")
        elif key == dpg.mvKey_Minus:
            controller.move_step = max(10, controller.move_step - 100)
            print(f"Move step: {controller.move_step}")
        # Z Step size ([ and ] keys)
        elif key == dpg.mvKey_Open_Brace:
            controller.decrease_z_step()
        elif key == dpg.mvKey_Close_Brace:
            controller.increase_z_step()
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
        # Exposure controls
        elif key == dpg.mvKey_E:
            shift = dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)
            if shift:
                controller.toggle_exposure_lock()
            else:
                controller.toggle_exposure_mode()
        elif key == dpg.mvKey_Comma:  # < key (decrease shutter speed = longer exposure)
            controller.decrease_shutter_speed()
        elif key == dpg.mvKey_Period:  # > key (increase shutter speed = shorter exposure)
            controller.increase_shutter_speed()
        elif key == dpg.mvKey_Prior:  # Page Up (increase ISO)
            controller.increase_iso()
        elif key == dpg.mvKey_Next:  # Page Down (decrease ISO)
            controller.decrease_iso()
        # Power saving
        elif key == dpg.mvKey_S:
            controller.toggle_power_saving()
        # Toggle continuous capture
        elif key == dpg.mvKey_Spacebar:
            controller.toggle_capture()
        # Toggle metadata panel
        elif key == dpg.mvKey_I:
            controller.toggle_metadata_panel()
        # Toggle adjustments panel
        elif key == dpg.mvKey_A:
            controller.toggle_adjustments_panel()
        # Toggle stats panel
        elif key == dpg.mvKey_T:
            controller.toggle_stats_panel()
        # Set XY reference (Shift+X)
        elif key == dpg.mvKey_X:
            shift = dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)
            if shift:
                controller.set_xy_reference()
        # Set Z reference (Shift+R)
        elif key == dpg.mvKey_R:
            shift = dpg.is_key_down(dpg.mvKey_LShift)
            if shift:
                controller.set_z_reference()
            else:
                # Hot reload (just R)
                print("[hot-reload] Manual reload triggered")
                self.hot_reloader.trigger_reload()
        # Center XY range overlay on current position
        elif key == dpg.mvKey_C:
            controller.center_xy_range()
        # Stitch controls
        elif key == dpg.mvKey_G:
            # G for "Grab" - toggle auto-stitch
            controller.toggle_auto_stitch()
        elif key == dpg.mvKey_B:
            # B for "Build" - manually capture current tile
            controller.capture_stitch_tile()
        elif key == dpg.mvKey_N:
            # N for "New" - clear tiles
            shift = dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)
            if shift:
                controller.clear_stitch_tiles()
        elif key == dpg.mvKey_V:
            # V for "View" - fit range to tiles
            controller.fit_range_to_tiles()
        # Grid scan controls
        elif key == dpg.mvKey_F5:
            # F5 - Start/pause grid scan
            if controller.scan_in_progress:
                controller.pause_grid_scan()
            else:
                controller.start_grid_scan()
        elif key == dpg.mvKey_F6:
            # F6 - Cancel grid scan
            controller.cancel_grid_scan()
        # Z-stack controls
        elif key == dpg.mvKey_Z:
            shift = dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)
            if shift:
                # Shift+Z - Capture Z-stack at current position
                controller.capture_z_stack()
            else:
                # Z - Toggle Z-stack mode
                controller.toggle_z_stack()
        # Session controls
        elif key == dpg.mvKey_F2:
            # F2 - Save session
            controller.save_session()
        elif key == dpg.mvKey_F3:
            # F3 - Load session
            controller.load_session()
        # Quality display toggle
        elif key == dpg.mvKey_W:
            controller.toggle_quality_display()
        # Well plate operations
        elif key == dpg.mvKey_F7:
            # F7 - Start label scan (scan pending labels)
            controller.scan_all_pending_labels()
        elif key == dpg.mvKey_F8:
            # F8 - Compute plate alignment
            controller.compute_plate_alignment()
        elif key == dpg.mvKey_F9:
            # F9 - Show alignment report
            print(controller.get_plate_alignment_report())
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

            # Apply image adjustments (brightness, contrast, etc.)
            adjusted_array = controller.apply_adjustments(img_array)
            gui_manager.create_or_update_texture(adjusted_array)

            # Compute image statistics if panel is visible
            if controller.show_stats_panel:
                controller.compute_image_stats(img_array)

        # Periodically update head info
        controller.maybe_update_head_info()

        # Process grid scan step if active
        if controller.scan_in_progress:
            controller.process_grid_scan_step()

        # Process label scan step if active
        if controller.label_scan_in_progress:
            controller.process_label_scan_step()

        # Update status display
        try:
            ui.update_status(controller)
            # Update stitch canvas if we have tiles
            if controller.tile_manager.tile_count > 0:
                ui.update_stitch_canvas_texture(controller)
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
