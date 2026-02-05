"""
UI definition for CM30 Control Panel.

This module contains the UI building code that can be hot-reloaded.
Modify this file to see changes reflected in the running application.
"""

import dearpygui.dearpygui as dpg

# Position overlay configuration
OVERLAY_WIDTH = 200
OVERLAY_HEIGHT = 200
OVERLAY_PADDING = 10
OVERLAY_BG_COLOR = (40, 40, 40, 200)
OVERLAY_BORDER_COLOR = (100, 100, 100, 255)
OVERLAY_RANGE_COLOR = (80, 80, 80, 255)
OVERLAY_FOV_COLOR = (100, 200, 255, 200)
OVERLAY_REF_COLOR = (255, 200, 100, 150)

# Stitch canvas dimensions (slightly smaller to fit within overlay with border)
STITCH_CANVAS_SIZE = 180


def build_status_bar():
    """Build the status bar at the top of the window."""
    with dpg.group(horizontal=True):
        dpg.add_text("X:", color=(150, 150, 150))
        dpg.add_text("0", tag="status_x")
        dpg.add_text("rel:", color=(120, 120, 120))
        dpg.add_text("0", tag="status_x_rel")
        dpg.add_text("Y:", color=(150, 150, 150))
        dpg.add_text("0", tag="status_y")
        dpg.add_text("rel:", color=(120, 120, 120))
        dpg.add_text("0", tag="status_y_rel")
        dpg.add_text("Z:", color=(150, 150, 150))
        dpg.add_text("0", tag="status_z")
        dpg.add_text("rel:", color=(120, 120, 120))
        dpg.add_text("0", tag="status_z_rel")
        dpg.add_spacer(width=10)
        dpg.add_text("XY:", color=(150, 150, 150))
        dpg.add_text("500", tag="status_step")
        dpg.add_text("Z:", color=(150, 150, 150))
        dpg.add_text("1.5625", tag="status_z_step")
        dpg.add_spacer(width=10)
        dpg.add_text("Mode:", color=(150, 150, 150))
        dpg.add_text("full", tag="status_mode")
        dpg.add_text("Light:", color=(150, 150, 150))
        dpg.add_text("off", tag="status_light")
        dpg.add_spacer(width=10)
        dpg.add_text("PwrSave:", color=(150, 150, 150))
        dpg.add_text("OFF", tag="status_power_saving")
        dpg.add_text("Live:", color=(150, 150, 150))
        dpg.add_text("ON", tag="status_capture_enabled")
        dpg.add_spacer(width=10)
        dpg.add_text("Capture:", color=(150, 150, 150))
        dpg.add_text("0 ms", tag="status_capture_time")
        dpg.add_spacer(width=10)
        dpg.add_text("", tag="status_reload", color=(100, 255, 100))


def build_control_buttons(controller):
    """Build the control button rows."""
    with dpg.group(horizontal=True):
        dpg.add_button(label="Autofocus (F)", callback=lambda: controller.do_autofocus())
        dpg.add_button(label="High Res (H)", callback=lambda: controller.set_resolution(True))
        dpg.add_button(label="Low Res (L)", callback=lambda: controller.set_resolution(False))
        dpg.add_button(label="LED1 (1)", callback=lambda: controller.set_light("led1_on"))
        dpg.add_button(label="LED2 (2)", callback=lambda: controller.set_light("led2_on"))
        dpg.add_button(label="LED Off (0)", callback=lambda: controller.set_light("off"))
        dpg.add_button(label="Power Save (S)", callback=lambda: controller.toggle_power_saving())
        dpg.add_button(label="Live (Space)", callback=lambda: controller.toggle_capture())
        dpg.add_button(label="Metadata (I)", callback=lambda: controller.toggle_metadata_panel())
        dpg.add_button(label="Adjustments (A)", callback=lambda: controller.toggle_adjustments_panel())
        dpg.add_button(label="Stats (T)", callback=lambda: controller.toggle_stats_panel())
    with dpg.group(horizontal=True):
        dpg.add_text("Z Step:", color=(150, 150, 150))
        dpg.add_button(label="- ([)", callback=lambda: controller.decrease_z_step(), width=50)
        dpg.add_button(label="+ (])", callback=lambda: controller.increase_z_step(), width=50)
        dpg.add_button(label="1x", callback=lambda: controller.set_z_step_multiplier(1), width=35)
        dpg.add_button(label="2x", callback=lambda: controller.set_z_step_multiplier(2), width=35)
        dpg.add_button(label="4x", callback=lambda: controller.set_z_step_multiplier(4), width=35)
        dpg.add_button(label="8x", callback=lambda: controller.set_z_step_multiplier(8), width=35)
        dpg.add_button(label="16x", callback=lambda: controller.set_z_step_multiplier(16), width=40)
        dpg.add_button(label="32x", callback=lambda: controller.set_z_step_multiplier(32), width=40)
        dpg.add_spacer(width=20)
        dpg.add_text("Ref:", color=(150, 150, 150))
        dpg.add_button(label="XY (Shift+X)", callback=lambda: controller.set_xy_reference())
        dpg.add_button(label="Z (Shift+R)", callback=lambda: controller.set_z_reference())
    # Exposure controls row
    with dpg.group(horizontal=True):
        dpg.add_text("Exposure:", color=(150, 150, 150))
        dpg.add_text("ISO", color=(150, 150, 150))
        dpg.add_button(label="-", callback=lambda: controller.decrease_iso(), width=30)
        dpg.add_text("100", tag="status_iso", color=(200, 200, 255))
        dpg.add_button(label="+", callback=lambda: controller.increase_iso(), width=30)
        dpg.add_spacer(width=10)
        dpg.add_text("Shutter", color=(150, 150, 150))
        dpg.add_button(label="- (<)", callback=lambda: controller.decrease_shutter_speed(), width=45)
        dpg.add_text("1/30", tag="status_shutter", color=(200, 200, 255))
        dpg.add_button(label="+ (>)", callback=lambda: controller.increase_shutter_speed(), width=45)
        dpg.add_spacer(width=10)
        dpg.add_text("Mode:", color=(150, 150, 150))
        dpg.add_button(label="Toggle (E)", tag="btn_exp_mode", callback=lambda: controller.toggle_exposure_mode())
        dpg.add_text("manual", tag="status_exp_mode", color=(200, 200, 255))
        dpg.add_spacer(width=10)
        dpg.add_button(label="Lock (Shift+E)", tag="btn_exp_lock", callback=lambda: controller.toggle_exposure_lock())
        dpg.add_text("unlocked", tag="status_exp_lock", color=(100, 255, 100))


def build_help_section():
    """Build the collapsible help section."""
    with dpg.collapsing_header(label="Keyboard Shortcuts", default_open=False):
        dpg.add_text("-- Movement --", color=(150, 200, 255))
        dpg.add_text("Arrow Keys: Move stage XY")
        dpg.add_text("U/D: Move Z up/down")
        dpg.add_text("+/-: Adjust XY move step")
        dpg.add_text("[/]: Adjust Z step (min 1.5625)")
        dpg.add_text("Shift+X: Set XY reference position")
        dpg.add_text("Shift+R: Set Z reference plane")
        dpg.add_text("-- Overlay/View --", color=(150, 200, 255))
        dpg.add_text("C: Center overlay range on current position")
        dpg.add_text("W: Toggle quality indicators")
        dpg.add_text("-- Stitching --", color=(150, 200, 255))
        dpg.add_text("G: Toggle auto-stitch (Grab tiles as you move)")
        dpg.add_text("B: Capture current position as stitch tile (Build)")
        dpg.add_text("Shift+N: Clear all stitch tiles (New)")
        dpg.add_text("V: Fit view range to captured tiles (View)")
        dpg.add_text("-- Grid Scan --", color=(150, 200, 255))
        dpg.add_text("F5: Start/Pause grid scan")
        dpg.add_text("F6: Cancel grid scan")
        dpg.add_text("-- Z-Stack --", color=(150, 200, 255))
        dpg.add_text("Z: Toggle Z-stack mode")
        dpg.add_text("Shift+Z: Capture Z-stack at current position")
        dpg.add_text("-- Session --", color=(150, 200, 255))
        dpg.add_text("F2: Save session")
        dpg.add_text("F3: Load session")
        dpg.add_text("-- Well Plate --", color=(150, 200, 255))
        dpg.add_text("F7: Scan reference labels")
        dpg.add_text("F8: Compute plate alignment")
        dpg.add_text("F9: Show alignment report")
        dpg.add_text("-- Camera --", color=(150, 200, 255))
        dpg.add_text("H/L: High/Low resolution")
        dpg.add_text("F: Autofocus")
        dpg.add_text("P/O: Preview/Original capture mode")
        dpg.add_text("1/2/0: LED1/LED2/Off")
        dpg.add_text("E: Toggle exposure mode")
        dpg.add_text("Shift+E: Toggle exposure lock")
        dpg.add_text("</> : Adjust shutter speed")
        dpg.add_text("PgUp/PgDn: Adjust ISO")
        dpg.add_text("-- Panels --", color=(150, 200, 255))
        dpg.add_text("S: Toggle power saving")
        dpg.add_text("Space: Toggle live capture")
        dpg.add_text("I: Toggle image metadata")
        dpg.add_text("A: Toggle image adjustments")
        dpg.add_text("T: Toggle image statistics")
        dpg.add_text("-- System --", color=(150, 200, 255))
        dpg.add_text("R: Reload UI (hot reload)")
        dpg.add_text("Q/Esc: Quit")


def build_head_info_section():
    """Build the collapsible head info section."""
    with dpg.collapsing_header(label="Head Info", default_open=False, tag="head_info_header"):
        dpg.add_text("Loading...", tag="head_info_text", wrap=600)


def build_metadata_panel():
    """Build the image metadata panel (initially hidden)."""
    with dpg.group(tag="metadata_panel", show=False):
        dpg.add_separator()
        with dpg.collapsing_header(label="Image Metadata (I)", default_open=True):
            dpg.add_text("No image captured yet", tag="metadata_text", wrap=500)


def build_adjustments_panel(controller):
    """Build the image adjustments panel (initially hidden)."""
    with dpg.group(tag="adjustments_panel", show=False):
        dpg.add_separator()
        with dpg.collapsing_header(label="Image Adjustments (A)", default_open=True):
            # Brightness slider (-1.0 to 1.0, default 0.0)
            with dpg.group(horizontal=True):
                dpg.add_text("Brightness:", color=(150, 150, 150), indent=10)
                dpg.add_slider_float(
                    tag="slider_brightness",
                    default_value=0.0,
                    min_value=-1.0,
                    max_value=1.0,
                    width=200,
                    callback=lambda s, a: controller.set_brightness(a)
                )
                dpg.add_text("0.00", tag="val_brightness")

            # Contrast slider (0.5 to 2.0, default 1.0)
            with dpg.group(horizontal=True):
                dpg.add_text("Contrast:  ", color=(150, 150, 150), indent=10)
                dpg.add_slider_float(
                    tag="slider_contrast",
                    default_value=1.0,
                    min_value=0.5,
                    max_value=2.0,
                    width=200,
                    callback=lambda s, a: controller.set_contrast(a)
                )
                dpg.add_text("1.00", tag="val_contrast")

            # Saturation slider (0.0 to 2.0, default 1.0)
            with dpg.group(horizontal=True):
                dpg.add_text("Saturation:", color=(150, 150, 150), indent=10)
                dpg.add_slider_float(
                    tag="slider_saturation",
                    default_value=1.0,
                    min_value=0.0,
                    max_value=2.0,
                    width=200,
                    callback=lambda s, a: controller.set_saturation(a)
                )
                dpg.add_text("1.00", tag="val_saturation")

            # Gamma slider (0.5 to 2.0, default 1.0)
            with dpg.group(horizontal=True):
                dpg.add_text("Gamma:     ", color=(150, 150, 150), indent=10)
                dpg.add_slider_float(
                    tag="slider_gamma",
                    default_value=1.0,
                    min_value=0.5,
                    max_value=2.0,
                    width=200,
                    callback=lambda s, a: controller.set_gamma(a)
                )
                dpg.add_text("1.00", tag="val_gamma")

            # Reset button
            dpg.add_button(
                label="Reset All",
                callback=lambda: _reset_adjustments(controller)
            )


def _reset_adjustments(controller):
    """Reset all adjustments and update sliders."""
    controller.reset_adjustments()
    # Update sliders to default values
    if dpg.does_item_exist("slider_brightness"):
        dpg.set_value("slider_brightness", 0.0)
    if dpg.does_item_exist("slider_contrast"):
        dpg.set_value("slider_contrast", 1.0)
    if dpg.does_item_exist("slider_saturation"):
        dpg.set_value("slider_saturation", 1.0)
    if dpg.does_item_exist("slider_gamma"):
        dpg.set_value("slider_gamma", 1.0)


def build_stats_panel():
    """Build the image statistics panel (initially hidden)."""
    with dpg.group(tag="stats_panel", show=False):
        dpg.add_separator()
        with dpg.collapsing_header(label="Image Statistics (T)", default_open=True):
            # Brightness section
            dpg.add_text("Brightness", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("  Mean:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_mean")
                dpg.add_text("Median:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_median")
                dpg.add_text("Std:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_std")
            with dpg.group(horizontal=True):
                dpg.add_text("  Min:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_min")
                dpg.add_text("Max:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_max")
                dpg.add_text("Range:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_dynamic_range")

            # Contrast section
            dpg.add_text("Contrast", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("  Michelson:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_michelson")
                dpg.add_text("RMS:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_rms")
                dpg.add_text("Eff. Range (5-95%):", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_eff_range")

            # Focus section
            dpg.add_text("Focus Quality", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("  Laplacian Var:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_laplacian")
                dpg.add_text("Gradient Mean:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_gradient")

            # Histogram section
            dpg.add_text("Histogram Analysis", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("  Entropy:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_entropy")
                dpg.add_text("(bits, max=8)", color=(80, 80, 80))
            with dpg.group(horizontal=True):
                dpg.add_text("  Underexposed:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_underexp")
                dpg.add_text("Overexposed:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_overexp")

            # Distribution section
            dpg.add_text("Distribution", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("  Skewness:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_skewness")
                dpg.add_text("(0=symmetric)", color=(80, 80, 80))
                dpg.add_text("Kurtosis:", color=(120, 120, 120))
                dpg.add_text("--", tag="stat_kurtosis")
                dpg.add_text("(3=normal)", color=(80, 80, 80))


def _on_overlay_click(sender, app_data, user_data):
    """Handle click on the overlay for ROI navigation."""
    controller = user_data
    if not controller or not controller.roi_click_enabled:
        return

    # Get mouse position relative to overlay
    mouse_pos = dpg.get_mouse_pos(local=False)
    item_pos = dpg.get_item_pos("position_overlay")

    if item_pos is None:
        return

    click_x = mouse_pos[0] - item_pos[0]
    click_y = mouse_pos[1] - item_pos[1]

    # Check if click is within overlay bounds
    if 0 <= click_x <= OVERLAY_WIDTH and 0 <= click_y <= OVERLAY_HEIGHT:
        # Account for padding
        effective_x = click_x - OVERLAY_PADDING
        effective_y = click_y - OVERLAY_PADDING
        effective_width = OVERLAY_WIDTH - 2 * OVERLAY_PADDING
        effective_height = OVERLAY_HEIGHT - 2 * OVERLAY_PADDING

        if effective_x >= 0 and effective_y >= 0:
            controller.navigate_to_overlay_position(
                effective_x, effective_y,
                effective_width, effective_height
            )


def build_position_overlay(controller):
    """Build the XY position overlay showing current position within max range."""
    with dpg.group(tag="position_overlay_group"):
        dpg.add_text("XY Position / Stitch Map (click to navigate)", color=(150, 150, 150))
        # Create a drawlist for the position visualization
        with dpg.drawlist(
            width=OVERLAY_WIDTH,
            height=OVERLAY_HEIGHT,
            tag="position_overlay"
        ):
            # Register click handler
            with dpg.item_handler_registry(tag="overlay_click_handler"):
                dpg.add_item_clicked_handler(callback=_on_overlay_click, user_data=controller)
            dpg.bind_item_handler_registry("position_overlay", "overlay_click_handler")
            # Background
            dpg.draw_rectangle(
                (0, 0),
                (OVERLAY_WIDTH, OVERLAY_HEIGHT),
                fill=OVERLAY_BG_COLOR,
                color=OVERLAY_BORDER_COLOR,
                tag="overlay_bg"
            )
            # Range rectangle (inner area representing full XY range)
            dpg.draw_rectangle(
                (OVERLAY_PADDING, OVERLAY_PADDING),
                (OVERLAY_WIDTH - OVERLAY_PADDING, OVERLAY_HEIGHT - OVERLAY_PADDING),
                fill=OVERLAY_RANGE_COLOR,
                color=OVERLAY_BORDER_COLOR,
                tag="overlay_range"
            )
            # Reference position marker (crosshair)
            dpg.draw_line(
                (OVERLAY_WIDTH // 2 - 5, OVERLAY_HEIGHT // 2),
                (OVERLAY_WIDTH // 2 + 5, OVERLAY_HEIGHT // 2),
                color=OVERLAY_REF_COLOR,
                thickness=1,
                tag="overlay_ref_h"
            )
            dpg.draw_line(
                (OVERLAY_WIDTH // 2, OVERLAY_HEIGHT // 2 - 5),
                (OVERLAY_WIDTH // 2, OVERLAY_HEIGHT // 2 + 5),
                color=OVERLAY_REF_COLOR,
                thickness=1,
                tag="overlay_ref_v"
            )
            # Current position / FOV rectangle (will be updated dynamically)
            dpg.draw_rectangle(
                (OVERLAY_WIDTH // 2 - 10, OVERLAY_HEIGHT // 2 - 10),
                (OVERLAY_WIDTH // 2 + 10, OVERLAY_HEIGHT // 2 + 10),
                fill=OVERLAY_FOV_COLOR,
                color=(150, 220, 255, 255),
                thickness=2,
                tag="overlay_fov"
            )
        # Overlay controls
        with dpg.group(horizontal=True):
            dpg.add_button(label="Center (C)", callback=lambda: controller.center_xy_range(), width=70)
            dpg.add_button(label="Zoom+", callback=lambda: controller.zoom_xy_range(0.5), width=50)
            dpg.add_button(label="Zoom-", callback=lambda: controller.zoom_xy_range(2.0), width=50)
        # Position info text
        with dpg.group(horizontal=True):
            dpg.add_text("Range:", color=(100, 100, 100))
            dpg.add_text("--", tag="overlay_range_text", color=(150, 150, 150))

        # Stitch controls section
        dpg.add_separator()
        dpg.add_text("Stitching", color=(150, 150, 150))
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Auto",
                tag="btn_auto_stitch",
                callback=lambda: controller.toggle_auto_stitch(),
                width=45
            )
            dpg.add_text("OFF", tag="status_auto_stitch", color=(150, 150, 150))
            dpg.add_button(
                label="Capture",
                callback=lambda: controller.capture_stitch_tile(),
                width=55
            )
            dpg.add_button(
                label="Clear",
                callback=lambda: controller.clear_stitch_tiles(),
                width=45
            )
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Fit",
                callback=lambda: controller.fit_range_to_tiles(),
                width=35
            )
            dpg.add_button(
                label="Export",
                callback=lambda: controller.export_stitch_preview(),
                width=50
            )
            dpg.add_button(
                label="Quality",
                callback=lambda: controller.toggle_quality_display(),
                width=55
            )
        with dpg.group(horizontal=True):
            dpg.add_text("Tiles:", color=(100, 100, 100))
            dpg.add_text("0", tag="stitch_tile_count", color=(150, 200, 255))

        # Grid Scan section
        dpg.add_separator()
        dpg.add_text("Grid Scan", color=(150, 150, 150))
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Start (F5)",
                tag="btn_grid_start",
                callback=lambda: controller.start_grid_scan(),
                width=70
            )
            dpg.add_button(
                label="Pause",
                tag="btn_grid_pause",
                callback=lambda: controller.pause_grid_scan(),
                width=50
            )
            dpg.add_button(
                label="Cancel (F6)",
                callback=lambda: controller.cancel_grid_scan(),
                width=75
            )
        with dpg.group(horizontal=True):
            dpg.add_text("Progress:", color=(100, 100, 100))
            dpg.add_text("--", tag="scan_progress", color=(150, 200, 255))
            dpg.add_text("ETA:", color=(100, 100, 100))
            dpg.add_text("--", tag="scan_eta", color=(150, 200, 255))

        # Z-Stack section
        dpg.add_separator()
        dpg.add_text("Z-Stack", color=(150, 150, 150))
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Z-Stack (Z)",
                callback=lambda: controller.toggle_z_stack(),
                width=80
            )
            dpg.add_text("OFF", tag="status_z_stack", color=(150, 150, 150))
            dpg.add_button(
                label="Capture (Shift+Z)",
                callback=lambda: controller.capture_z_stack(),
                width=110
            )

        # Session section
        dpg.add_separator()
        dpg.add_text("Session", color=(150, 150, 150))
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Save (F2)",
                callback=lambda: controller.save_session(),
                width=70
            )
            dpg.add_button(
                label="Load (F3)",
                callback=lambda: controller.load_session(),
                width=70
            )

        # Well Plate section
        dpg.add_separator()
        dpg.add_text("Well Plate (96)", color=(150, 150, 150))
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Scan Labels (F7)",
                callback=lambda: controller.scan_all_pending_labels(),
                width=100
            )
            dpg.add_button(
                label="Align (F8)",
                callback=lambda: controller.compute_plate_alignment(),
                width=70
            )
        with dpg.group(horizontal=True):
            dpg.add_text("Label:", color=(100, 100, 100))
            dpg.add_text("--", tag="status_label_scan", color=(150, 150, 150))
        with dpg.group(horizontal=True):
            dpg.add_text("Well:", color=(100, 100, 100))
            dpg.add_text("--", tag="status_current_well", color=(150, 200, 255))


def build_main_window(controller):
    """Build the main application window."""
    with dpg.window(label="CM30 Control Panel", tag="main_window"):
        build_status_bar()
        dpg.add_separator()
        build_control_buttons(controller)
        dpg.add_separator()
        build_help_section()
        build_head_info_section()
        build_metadata_panel()
        build_adjustments_panel(controller)
        build_stats_panel()
        dpg.add_separator()

        # Position overlay and image display in a horizontal group
        with dpg.group(horizontal=True):
            # Position overlay on the left
            build_position_overlay(controller)
            dpg.add_spacer(width=20)
            # Image display container (texture added dynamically)
            with dpg.group(tag="image_container"):
                dpg.add_text("Waiting for first image...")


def update_position_overlay(controller):
    """Update the XY position overlay to show current position within range."""
    if not dpg.does_item_exist("position_overlay"):
        return

    # Get range values from controller
    x_min, x_max = controller.xy_range_x
    y_min, y_max = controller.xy_range_y

    # Calculate drawable area
    draw_x_min = OVERLAY_PADDING
    draw_x_max = OVERLAY_WIDTH - OVERLAY_PADDING
    draw_y_min = OVERLAY_PADDING
    draw_y_max = OVERLAY_HEIGHT - OVERLAY_PADDING
    draw_width = draw_x_max - draw_x_min
    draw_height = draw_y_max - draw_y_min

    # Calculate scale factors
    range_x = x_max - x_min if x_max > x_min else 1
    range_y = y_max - y_min if y_max > y_min else 1
    scale_x = draw_width / range_x
    scale_y = draw_height / range_y

    # Calculate FOV size in stage units (approximate based on image dimensions)
    # These are rough estimates - adjust based on actual microscope FOV
    fov_width = controller.fov_width
    fov_height = controller.fov_height

    # Convert current position to overlay coordinates
    pos_x = draw_x_min + (controller.stage_x - x_min) * scale_x
    pos_y = draw_y_min + (controller.stage_y - y_min) * scale_y

    # Convert FOV size to overlay coordinates
    fov_w = fov_width * scale_x
    fov_h = fov_height * scale_y

    # Ensure minimum visible size
    fov_w = max(fov_w, 4)
    fov_h = max(fov_h, 4)

    # Update FOV rectangle position (centered on current position)
    fov_x1 = pos_x - fov_w / 2
    fov_y1 = pos_y - fov_h / 2
    fov_x2 = pos_x + fov_w / 2
    fov_y2 = pos_y + fov_h / 2

    # Update the FOV rectangle
    if dpg.does_item_exist("overlay_fov"):
        dpg.configure_item("overlay_fov", pmin=(fov_x1, fov_y1), pmax=(fov_x2, fov_y2))

    # Update reference position marker
    ref_x = draw_x_min + (controller.x_ref - x_min) * scale_x
    ref_y = draw_y_min + (controller.y_ref - y_min) * scale_y

    if dpg.does_item_exist("overlay_ref_h"):
        dpg.configure_item("overlay_ref_h",
                           p1=(ref_x - 5, ref_y),
                           p2=(ref_x + 5, ref_y))
    if dpg.does_item_exist("overlay_ref_v"):
        dpg.configure_item("overlay_ref_v",
                           p1=(ref_x, ref_y - 5),
                           p2=(ref_x, ref_y + 5))

    # Update range text
    if dpg.does_item_exist("overlay_range_text"):
        dpg.set_value("overlay_range_text",
                      f"X:[{x_min}-{x_max}] Y:[{y_min}-{y_max}]")

    # Update stitch status
    update_stitch_status(controller)


def update_stitch_status(controller):
    """Update the stitch status display."""
    # Update auto-stitch status
    if dpg.does_item_exist("status_auto_stitch"):
        if controller.auto_stitch:
            dpg.set_value("status_auto_stitch", "ON")
            dpg.configure_item("status_auto_stitch", color=(100, 255, 100))
        else:
            dpg.set_value("status_auto_stitch", "OFF")
            dpg.configure_item("status_auto_stitch", color=(150, 150, 150))

    # Update tile count
    if dpg.does_item_exist("stitch_tile_count"):
        dpg.set_value("stitch_tile_count", str(controller.tile_manager.tile_count))

    # Update grid scan status
    if dpg.does_item_exist("scan_progress"):
        if controller.scan_in_progress:
            dpg.set_value("scan_progress", f"{controller.scan_progress:.1f}%")
            dpg.configure_item("scan_progress", color=(100, 255, 100))
        else:
            dpg.set_value("scan_progress", "--")
            dpg.configure_item("scan_progress", color=(150, 150, 150))

    if dpg.does_item_exist("scan_eta"):
        if controller.scan_in_progress:
            dpg.set_value("scan_eta", controller.scan_eta)
        else:
            dpg.set_value("scan_eta", "--")

    # Update Z-stack status
    if dpg.does_item_exist("status_z_stack"):
        if controller.z_stack_enabled:
            dpg.set_value("status_z_stack", f"ON ({controller.z_stack_steps}p)")
            dpg.configure_item("status_z_stack", color=(100, 255, 100))
        else:
            dpg.set_value("status_z_stack", "OFF")
            dpg.configure_item("status_z_stack", color=(150, 150, 150))

    # Update well plate status
    if dpg.does_item_exist("status_label_scan"):
        if controller.label_scan_in_progress:
            progress = controller.get_label_scan_progress()
            label = controller.current_label_scan or "?"
            dpg.set_value("status_label_scan", f"{label} {progress:.0f}%")
            dpg.configure_item("status_label_scan", color=(100, 255, 100))
        else:
            pending = len(controller.plate_manager.get_pending_labels())
            scanned = len(controller.plate_manager.get_scanned_labels())
            dpg.set_value("status_label_scan", f"{scanned}/{scanned + pending} labels")
            dpg.configure_item("status_label_scan", color=(150, 150, 150))

    if dpg.does_item_exist("status_current_well"):
        well = controller.get_current_well()
        if well:
            dpg.set_value("status_current_well", well)
            dpg.configure_item("status_current_well", color=(150, 200, 255))
        else:
            dpg.set_value("status_current_well", "--")
            dpg.configure_item("status_current_well", color=(150, 150, 150))


def update_stitch_canvas_texture(controller):
    """Update the stitch canvas texture in the overlay.

    This renders stitched tiles as a background in the position overlay.
    Called from the main render loop when tiles exist.
    """
    if controller.tile_manager.tile_count == 0:
        # No tiles, use default background
        if dpg.does_item_exist("overlay_range"):
            dpg.configure_item("overlay_range", fill=OVERLAY_RANGE_COLOR)
        return

    # Get the rendered stitch canvas
    stitch_data = controller.get_stitch_canvas_data()

    # Create or update the stitch texture
    if not dpg.does_item_exist("stitch_texture"):
        # Create texture on first use
        with dpg.texture_registry():
            dpg.add_dynamic_texture(
                width=controller.stitch_canvas.width,
                height=controller.stitch_canvas.height,
                default_value=stitch_data.flatten(),
                tag="stitch_texture"
            )

        # Add image to the overlay drawlist
        if dpg.does_item_exist("position_overlay"):
            # Draw the stitch texture as background
            dpg.draw_image(
                "stitch_texture",
                pmin=(OVERLAY_PADDING, OVERLAY_PADDING),
                pmax=(OVERLAY_WIDTH - OVERLAY_PADDING, OVERLAY_HEIGHT - OVERLAY_PADDING),
                parent="position_overlay",
                tag="stitch_bg_image",
                before="overlay_ref_h"  # Draw behind the reference crosshair
            )
    else:
        # Update existing texture
        dpg.set_value("stitch_texture", stitch_data.flatten())


def update_status(controller):
    """Update the status display with current values."""
    dpg.set_value("status_x", f"{controller.stage_x}")
    dpg.set_value("status_y", f"{controller.stage_y}")
    dpg.set_value("status_z", f"{controller.stage_z:.2f}")

    # Show x_rel with sign and color coding
    x_rel = controller.x_rel
    if x_rel >= 0:
        dpg.set_value("status_x_rel", f"+{x_rel}")
        dpg.configure_item("status_x_rel", color=(100, 200, 255))  # Blue for positive
    else:
        dpg.set_value("status_x_rel", f"{x_rel}")
        dpg.configure_item("status_x_rel", color=(255, 200, 100))  # Orange for negative

    # Show y_rel with sign and color coding
    y_rel = controller.y_rel
    if y_rel >= 0:
        dpg.set_value("status_y_rel", f"+{y_rel}")
        dpg.configure_item("status_y_rel", color=(100, 200, 255))  # Blue for positive
    else:
        dpg.set_value("status_y_rel", f"{y_rel}")
        dpg.configure_item("status_y_rel", color=(255, 200, 100))  # Orange for negative

    # Show z_rel with sign and color coding
    z_rel = controller.z_rel
    if z_rel >= 0:
        dpg.set_value("status_z_rel", f"+{z_rel:.2f}")
        dpg.configure_item("status_z_rel", color=(100, 200, 255))  # Blue for positive
    else:
        dpg.set_value("status_z_rel", f"{z_rel:.2f}")
        dpg.configure_item("status_z_rel", color=(255, 200, 100))  # Orange for negative
    dpg.set_value("status_step", str(controller.move_step))
    dpg.set_value("status_z_step", f"{controller.z_step:.4f}")
    dpg.set_value("status_mode", controller.capture_mode)
    dpg.set_value("status_light", controller.light_mode)
    dpg.set_value("status_capture_time", f"{controller.last_capture_time_ms} ms")

    # Power saving status with color
    if controller.power_saving:
        dpg.set_value("status_power_saving", "ON")
        dpg.configure_item("status_power_saving", color=(255, 200, 100))
    else:
        dpg.set_value("status_power_saving", "OFF")
        dpg.configure_item("status_power_saving", color=(100, 255, 100))

    # Capture enabled status with color
    if controller.capture_enabled:
        dpg.set_value("status_capture_enabled", "ON")
        dpg.configure_item("status_capture_enabled", color=(100, 255, 100))
    else:
        dpg.set_value("status_capture_enabled", "OFF")
        dpg.configure_item("status_capture_enabled", color=(255, 100, 100))

    # Update exposure settings display
    update_exposure_display(controller)

    # Update head info text
    if controller.head_info:
        head_info_lines = format_head_info(controller.head_info)
        dpg.set_value("head_info_text", head_info_lines)

    # Update metadata panel visibility and content
    update_metadata_panel(controller)

    # Update adjustments panel visibility and values
    update_adjustments_panel(controller)

    # Update stats panel visibility and values
    update_stats_panel(controller)

    # Update position overlay
    update_position_overlay(controller)


def update_exposure_display(controller):
    """Update the exposure settings display."""
    # ISO
    if dpg.does_item_exist("status_iso"):
        dpg.set_value("status_iso", str(controller.iso))

    # Shutter speed
    if dpg.does_item_exist("status_shutter"):
        dpg.set_value("status_shutter", f"1/{controller.shutter_speed_denominator}")

    # Exposure mode
    if dpg.does_item_exist("status_exp_mode"):
        dpg.set_value("status_exp_mode", controller.exposure_mode)
        if controller.exposure_mode == "manual":
            dpg.configure_item("status_exp_mode", color=(200, 200, 255))
        else:
            dpg.configure_item("status_exp_mode", color=(255, 255, 100))

    # Exposure lock status
    if dpg.does_item_exist("status_exp_lock"):
        if controller.exposure_locked:
            dpg.set_value("status_exp_lock", "LOCKED")
            dpg.configure_item("status_exp_lock", color=(255, 100, 100))
        else:
            dpg.set_value("status_exp_lock", "unlocked")
            dpg.configure_item("status_exp_lock", color=(100, 255, 100))


def update_metadata_panel(controller):
    """Update the metadata panel visibility and content."""
    # Toggle panel visibility
    if dpg.does_item_exist("metadata_panel"):
        dpg.configure_item("metadata_panel", show=controller.show_metadata_panel)

    # Update metadata text if panel is visible and we have metadata
    if controller.show_metadata_panel and controller.image_metadata:
        metadata_text = format_metadata(controller.image_metadata)
        if dpg.does_item_exist("metadata_text"):
            dpg.set_value("metadata_text", metadata_text)


def update_adjustments_panel(controller):
    """Update the adjustments panel visibility and value labels."""
    # Toggle panel visibility
    if dpg.does_item_exist("adjustments_panel"):
        dpg.configure_item("adjustments_panel", show=controller.show_adjustments_panel)

    # Update value labels
    if controller.show_adjustments_panel:
        if dpg.does_item_exist("val_brightness"):
            dpg.set_value("val_brightness", f"{controller.brightness:.2f}")
        if dpg.does_item_exist("val_contrast"):
            dpg.set_value("val_contrast", f"{controller.contrast:.2f}")
        if dpg.does_item_exist("val_saturation"):
            dpg.set_value("val_saturation", f"{controller.saturation:.2f}")
        if dpg.does_item_exist("val_gamma"):
            dpg.set_value("val_gamma", f"{controller.gamma:.2f}")


def update_stats_panel(controller):
    """Update the image statistics panel visibility and values."""
    # Toggle panel visibility
    if dpg.does_item_exist("stats_panel"):
        dpg.configure_item("stats_panel", show=controller.show_stats_panel)

    # Update stat values if panel is visible and we have stats
    if controller.show_stats_panel and controller.image_stats:
        stats = controller.image_stats

        # Brightness stats
        _set_stat("stat_mean", stats.get("mean"), "{:.1f}")
        _set_stat("stat_median", stats.get("median"), "{:.1f}")
        _set_stat("stat_std", stats.get("std"), "{:.1f}")
        _set_stat("stat_min", stats.get("min"), "{:.0f}")
        _set_stat("stat_max", stats.get("max"), "{:.0f}")
        _set_stat("stat_dynamic_range", stats.get("dynamic_range"), "{:.0f}")

        # Contrast stats
        _set_stat("stat_michelson", stats.get("michelson_contrast"), "{:.3f}")
        _set_stat("stat_rms", stats.get("rms_contrast"), "{:.3f}")
        _set_stat("stat_eff_range", stats.get("effective_range"), "{:.1f}")

        # Focus stats
        _set_stat("stat_laplacian", stats.get("laplacian_var"), "{:.1f}")
        _set_stat("stat_gradient", stats.get("gradient_mean"), "{:.2f}")

        # Histogram stats
        _set_stat("stat_entropy", stats.get("entropy"), "{:.2f}")
        _set_stat("stat_underexp", stats.get("pct_underexposed"), "{:.1f}%")
        _set_stat("stat_overexp", stats.get("pct_overexposed"), "{:.1f}%")

        # Distribution stats
        _set_stat("stat_skewness", stats.get("skewness"), "{:.2f}")
        _set_stat("stat_kurtosis", stats.get("kurtosis"), "{:.2f}")

        # Color code exposure warnings
        if stats.get("pct_underexposed", 0) > 5:
            dpg.configure_item("stat_underexp", color=(255, 150, 100))
        else:
            dpg.configure_item("stat_underexp", color=(100, 255, 100))

        if stats.get("pct_overexposed", 0) > 5:
            dpg.configure_item("stat_overexp", color=(255, 150, 100))
        else:
            dpg.configure_item("stat_overexp", color=(100, 255, 100))

        # Color code focus quality (higher is better)
        laplacian = stats.get("laplacian_var", 0)
        if laplacian > 500:
            dpg.configure_item("stat_laplacian", color=(100, 255, 100))  # Good focus
        elif laplacian > 100:
            dpg.configure_item("stat_laplacian", color=(255, 255, 100))  # Moderate
        else:
            dpg.configure_item("stat_laplacian", color=(255, 150, 100))  # Poor focus


def _set_stat(tag: str, value, fmt: str):
    """Helper to set a stat value with formatting."""
    if dpg.does_item_exist(tag):
        if value is not None:
            if fmt.endswith("%"):
                dpg.set_value(tag, fmt.format(value))
            else:
                dpg.set_value(tag, fmt.format(value))
        else:
            dpg.set_value(tag, "--")


def format_metadata(metadata: dict) -> str:
    """Format image metadata dictionary for display."""
    if not metadata:
        return "No metadata available"

    lines = []

    # Priority keys to show first
    priority_keys = ["size", "mode", "format", "Make", "Model", "DateTime",
                     "ExposureTime", "FNumber", "ISOSpeedRatings", "FocalLength",
                     "ShutterSpeedValue", "ApertureValue", "BrightnessValue"]

    # Show priority keys first
    for key in priority_keys:
        if key in metadata:
            value = metadata[key]
            lines.append(f"{key}: {value}")

    # Then show remaining keys
    for key, value in sorted(metadata.items()):
        if key not in priority_keys:
            # Truncate long values
            str_value = str(value)
            if len(str_value) > 80:
                str_value = str_value[:77] + "..."
            lines.append(f"{key}: {str_value}")

    return "\n".join(lines) if lines else "No metadata available"


def format_head_info(head_info: dict) -> str:
    """Format head info dictionary for display."""
    if not isinstance(head_info, dict):
        return str(head_info)

    lines = []
    for key, value in sorted(head_info.items()):
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for k2, v2 in sorted(value.items()):
                lines.append(f"  {k2}: {v2}")
        elif isinstance(value, list):
            lines.append(f"{key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def show_reload_message(message: str = "Reloaded!"):
    """Show a reload notification in the status bar."""
    try:
        dpg.set_value("status_reload", message)
    except Exception:
        pass
