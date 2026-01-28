"""
pycm30 - Python library for interfacing with the Olympus CM30 incubation monitor.

This library provides a Python interface to the CM30 HTTP API for controlling
the microscope stage, capturing images, and performing automated scans.
"""

__version__ = "0.1.0"
__author__ = "Richard Bryan"

from pycm30.cm30_api import (
    init,
    get_image,
    get_image_preview,
    xy_move,
    z_move,
    get_stage_xy,
    get_stage_z,
    autofocus,
    get_head_info,
    set_head_info,
    get_light_params,
    set_light_params,
    set_exposure_settings,
    exposure_lock,
    exposure_unlock,
    set_resolution,
    set_highres,
    is_moving,
    is_z_moving,
)

__all__ = [
    "__version__",
    "__author__",
    "init",
    "get_image",
    "get_image_preview",
    "xy_move",
    "z_move",
    "get_stage_xy",
    "get_stage_z",
    "autofocus",
    "get_head_info",
    "set_head_info",
    "get_light_params",
    "set_light_params",
    "set_exposure_settings",
    "exposure_lock",
    "exposure_unlock",
    "set_resolution",
    "set_highres",
    "is_moving",
    "is_z_moving",
]
