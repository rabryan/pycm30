"""
UI definition for CM30 Control Panel.

This module contains the UI building code that can be hot-reloaded.
Modify this file to see changes reflected in the running application.
"""

import dearpygui.dearpygui as dpg


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
        dpg.add_text("Arrow Keys: Move stage XY")
        dpg.add_text("U/D: Move Z up/down")
        dpg.add_text("+/-: Adjust XY move step")
        dpg.add_text("[/]: Adjust Z step (min 1.5625)")
        dpg.add_text("Shift+X: Set XY reference position")
        dpg.add_text("Shift+R: Set Z reference plane")
        dpg.add_text("H/L: High/Low resolution")
        dpg.add_text("F: Autofocus")
        dpg.add_text("P/O: Preview/Original capture mode")
        dpg.add_text("1/2/0: LED1/LED2/Off")
        dpg.add_text("E: Toggle exposure mode")
        dpg.add_text("Shift+E: Toggle exposure lock")
        dpg.add_text("</> : Adjust shutter speed")
        dpg.add_text("PgUp/PgDn: Adjust ISO")
        dpg.add_text("S: Toggle power saving")
        dpg.add_text("Space: Toggle live capture")
        dpg.add_text("I: Toggle image metadata")
        dpg.add_text("A: Toggle image adjustments")
        dpg.add_text("T: Toggle image statistics")
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

        # Image display container (texture added dynamically)
        with dpg.group(tag="image_container"):
            dpg.add_text("Waiting for first image...")


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
