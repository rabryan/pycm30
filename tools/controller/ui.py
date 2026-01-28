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
