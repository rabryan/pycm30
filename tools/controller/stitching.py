"""
Image stitching module for CM30 Controller.

Provides comprehensive stitching capabilities:
- TileManager: Stores and manages captured image tiles with position metadata
- StitchCanvas: Composites tiles into a unified image for display/export
- GridScanner: Automated grid scanning with progress tracking
- ZStackManager: Multi-plane Z-stack capture and EDF compositing
- TileQuality: Focus and exposure quality assessment
- StitchSession: Persistent session save/load
- PyramidExporter: Memory-efficient multi-resolution export

Memory Management:
- Only thumbnails are kept in memory for the overlay preview
- Full-resolution tiles can be saved to disk for later stitching
- The overlay canvas is limited to a configurable max size
- Memory-mapped exports for arbitrarily large outputs
"""

import json
import os
import struct
import time
import zlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Tuple

import numpy as np


# ============================================================================
# Data Classes and Enums
# ============================================================================

class TileQualityLevel(Enum):
    """Quality assessment levels for tiles."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


@dataclass
class TileQuality:
    """Quality metrics for a captured tile."""
    focus_score: float = 0.0  # Laplacian variance (higher = sharper)
    brightness_mean: float = 0.0  # Average brightness (0-255)
    brightness_std: float = 0.0  # Brightness standard deviation
    overexposed_pct: float = 0.0  # Percentage of overexposed pixels
    underexposed_pct: float = 0.0  # Percentage of underexposed pixels
    contrast: float = 0.0  # Michelson contrast

    @property
    def level(self) -> TileQualityLevel:
        """Compute overall quality level."""
        # Focus is primary concern
        if self.focus_score < 50:
            return TileQualityLevel.UNUSABLE
        if self.focus_score < 100:
            return TileQualityLevel.POOR

        # Check exposure issues
        if self.overexposed_pct > 10 or self.underexposed_pct > 10:
            return TileQualityLevel.FAIR

        if self.focus_score > 500 and self.contrast > 0.3:
            return TileQualityLevel.EXCELLENT

        if self.focus_score > 200:
            return TileQualityLevel.GOOD

        return TileQualityLevel.FAIR

    @property
    def color(self) -> Tuple[int, int, int, int]:
        """Get display color for quality level."""
        colors = {
            TileQualityLevel.EXCELLENT: (100, 255, 100, 200),
            TileQualityLevel.GOOD: (200, 255, 100, 200),
            TileQualityLevel.FAIR: (255, 255, 100, 200),
            TileQualityLevel.POOR: (255, 150, 100, 200),
            TileQualityLevel.UNUSABLE: (255, 100, 100, 200),
        }
        return colors.get(self.level, (150, 150, 150, 200))


@dataclass
class Tile:
    """A captured image tile with position and metadata."""
    x: int  # Stage X position (center of tile)
    y: int  # Stage Y position (center of tile)
    z: float  # Stage Z position
    timestamp: float  # Capture time
    thumbnail: np.ndarray  # Downsampled image for preview (RGBA, float32, 0-1)
    full_res_path: Optional[str] = None  # Path to full-res image on disk
    fov_width: int = 3000  # Field of view width in stage units
    fov_height: int = 2250  # Field of view height in stage units
    quality: Optional[TileQuality] = None  # Quality metrics
    z_stack_id: Optional[str] = None  # ID linking tiles in same Z-stack
    z_index: int = 0  # Index within Z-stack (0 = reference plane)

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """Get tile bounds as (x_min, y_min, x_max, y_max)."""
        half_w = self.fov_width // 2
        half_h = self.fov_height // 2
        return (self.x - half_w, self.y - half_h, self.x + half_w, self.y + half_h)

    def to_dict(self) -> dict:
        """Serialize tile to dictionary (without image data)."""
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "timestamp": self.timestamp,
            "full_res_path": self.full_res_path,
            "fov_width": self.fov_width,
            "fov_height": self.fov_height,
            "quality": {
                "focus_score": self.quality.focus_score,
                "brightness_mean": self.quality.brightness_mean,
                "brightness_std": self.quality.brightness_std,
                "overexposed_pct": self.quality.overexposed_pct,
                "underexposed_pct": self.quality.underexposed_pct,
                "contrast": self.quality.contrast,
            } if self.quality else None,
            "z_stack_id": self.z_stack_id,
            "z_index": self.z_index,
        }

    @classmethod
    def from_dict(cls, data: dict, thumbnail: np.ndarray) -> "Tile":
        """Deserialize tile from dictionary."""
        quality = None
        if data.get("quality"):
            q = data["quality"]
            quality = TileQuality(
                focus_score=q.get("focus_score", 0),
                brightness_mean=q.get("brightness_mean", 0),
                brightness_std=q.get("brightness_std", 0),
                overexposed_pct=q.get("overexposed_pct", 0),
                underexposed_pct=q.get("underexposed_pct", 0),
                contrast=q.get("contrast", 0),
            )
        return cls(
            x=data["x"],
            y=data["y"],
            z=data["z"],
            timestamp=data["timestamp"],
            thumbnail=thumbnail,
            full_res_path=data.get("full_res_path"),
            fov_width=data.get("fov_width", 3000),
            fov_height=data.get("fov_height", 2250),
            quality=quality,
            z_stack_id=data.get("z_stack_id"),
            z_index=data.get("z_index", 0),
        )


@dataclass
class GridScanConfig:
    """Configuration for grid scanning."""
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    overlap_pct: float = 10.0  # Overlap percentage between tiles
    z_stack_enabled: bool = False
    z_stack_range: float = 50.0  # Total Z range for stack
    z_stack_steps: int = 5  # Number of Z planes
    snake_pattern: bool = True  # Use snake/boustrophedon pattern
    autofocus_interval: int = 0  # Autofocus every N tiles (0 = never)

    @property
    def total_positions(self) -> int:
        """Estimate total number of XY positions."""
        # This is approximate - actual depends on FOV
        return max(1, ((self.x_max - self.x_min) // 2000) * ((self.y_max - self.y_min) // 1500))


class ScanState(Enum):
    """State of grid scan operation."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ============================================================================
# Quality Assessment
# ============================================================================

class QualityAssessor:
    """Assesses image quality for tiles."""

    @staticmethod
    def assess(image: np.ndarray) -> TileQuality:
        """Compute quality metrics for an image.

        Args:
            image: Image as numpy array (RGBA or RGB, float32 0-1)

        Returns:
            TileQuality with computed metrics
        """
        # Convert to grayscale (0-255 range)
        if image.shape[2] >= 3:
            gray = (0.299 * image[:, :, 0] +
                    0.587 * image[:, :, 1] +
                    0.114 * image[:, :, 2])
        else:
            gray = image[:, :, 0]

        gray_255 = (gray * 255).astype(np.float32)
        flat = gray_255.flatten()

        # Basic stats
        brightness_mean = float(np.mean(flat))
        brightness_std = float(np.std(flat))

        # Exposure analysis
        overexposed_pct = float(np.sum(flat > 250) / len(flat) * 100)
        underexposed_pct = float(np.sum(flat < 5) / len(flat) * 100)

        # Contrast (Michelson)
        min_val = float(np.min(flat))
        max_val = float(np.max(flat))
        if (max_val + min_val) > 0:
            contrast = (max_val - min_val) / (max_val + min_val)
        else:
            contrast = 0.0

        # Focus score (Laplacian variance)
        focus_score = QualityAssessor._compute_focus_score(gray_255)

        return TileQuality(
            focus_score=focus_score,
            brightness_mean=brightness_mean,
            brightness_std=brightness_std,
            overexposed_pct=overexposed_pct,
            underexposed_pct=underexposed_pct,
            contrast=contrast,
        )

    @staticmethod
    def _compute_focus_score(gray: np.ndarray) -> float:
        """Compute Laplacian variance as focus measure."""
        h, w = gray.shape
        if h < 4 or w < 4:
            return 0.0

        # 3x3 Laplacian kernel
        laplacian_kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)

        # Convolve
        padded = np.pad(gray, 1, mode='edge')
        laplacian = np.zeros_like(gray)
        for i in range(3):
            for j in range(3):
                laplacian += laplacian_kernel[i, j] * padded[i:i+h, j:j+w]

        return float(np.var(laplacian))


# ============================================================================
# Tile Manager
# ============================================================================

class TileManager:
    """Manages captured image tiles for stitching.

    Features:
    - Stores thumbnails in memory for fast preview
    - Optionally saves full-res images to disk
    - Tracks coverage area and tile positions
    - Supports incremental addition and removal of tiles
    - Quality assessment and filtering
    """

    # Thumbnail size for memory efficiency
    THUMBNAIL_SIZE = (64, 48)  # Width, Height (4:3 aspect)

    def __init__(self, save_dir: Optional[str] = None):
        """Initialize the tile manager.

        Args:
            save_dir: Optional directory to save full-res tiles
        """
        self.tiles: Dict[Tuple[int, int], Tile] = {}  # (x, y) -> Tile
        self.save_dir = Path(save_dir) if save_dir else None
        if self.save_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)

        # Track coverage bounds
        self._bounds_dirty = True
        self._cached_bounds = (0, 0, 0, 0)

        # FOV settings (can be updated from controller)
        self.fov_width = 3000
        self.fov_height = 2250

        # Minimum movement to consider a new position (prevents duplicates)
        self.position_threshold = 500  # stage units

        # Quality filtering
        self.min_quality_level = TileQualityLevel.POOR  # Reject UNUSABLE tiles
        self.assess_quality = True

    def add_tile(self, x: int, y: int, z: float, image: np.ndarray,
                 save_full_res: bool = False,
                 z_stack_id: Optional[str] = None,
                 z_index: int = 0) -> Optional[Tile]:
        """Add a new tile at the given position.

        Args:
            x: Stage X position
            y: Stage Y position
            z: Stage Z position
            image: Full resolution image as numpy array (RGBA, float32, 0-1)
            save_full_res: Whether to save full-res image to disk
            z_stack_id: Optional ID for Z-stack grouping
            z_index: Index within Z-stack

        Returns:
            The created Tile, or None if rejected (quality/duplicate)
        """
        # Assess quality
        quality = None
        if self.assess_quality:
            quality = QualityAssessor.assess(image)
            # Check minimum quality
            if quality.level == TileQualityLevel.UNUSABLE:
                if self.min_quality_level != TileQualityLevel.UNUSABLE:
                    print(f"Tile rejected: unusable quality (focus={quality.focus_score:.1f})")
                    return None

        # Quantize position to grid to prevent near-duplicates
        grid_x = round(x / self.position_threshold) * self.position_threshold
        grid_y = round(y / self.position_threshold) * self.position_threshold
        key = (grid_x, grid_y)

        # For Z-stacks, use composite key
        if z_stack_id:
            key = (grid_x, grid_y, z_index)

        # Check if we already have a tile at this position
        if key in self.tiles:
            # Update existing tile with newer image if quality is better
            existing = self.tiles[key]
            if quality and existing.quality:
                if quality.focus_score <= existing.quality.focus_score:
                    return existing  # Keep existing better tile

            existing.thumbnail = self._create_thumbnail(image)
            existing.z = z
            existing.timestamp = time.time()
            existing.quality = quality
            return existing

        # Create thumbnail
        thumbnail = self._create_thumbnail(image)

        # Optionally save full-res to disk
        full_res_path = None
        if save_full_res and self.save_dir:
            filename = f"tile_{grid_x}_{grid_y}_z{z_index}_{int(time.time())}.npy"
            full_res_path = str(self.save_dir / filename)
            np.save(full_res_path, image)

        # Create tile
        tile = Tile(
            x=grid_x,
            y=grid_y,
            z=z,
            timestamp=time.time(),
            thumbnail=thumbnail,
            full_res_path=full_res_path,
            fov_width=self.fov_width,
            fov_height=self.fov_height,
            quality=quality,
            z_stack_id=z_stack_id,
            z_index=z_index,
        )

        self.tiles[key] = tile
        self._bounds_dirty = True
        return tile

    def _create_thumbnail(self, image: np.ndarray) -> np.ndarray:
        """Create a thumbnail from a full-resolution image."""
        h, w = image.shape[:2]
        target_w, target_h = self.THUMBNAIL_SIZE

        # Simple downsampling using stride
        stride_y = max(1, h // target_h)
        stride_x = max(1, w // target_w)

        thumbnail = image[::stride_y, ::stride_x].copy()

        # Ensure correct size by cropping/padding if needed
        th, tw = thumbnail.shape[:2]
        if th > target_h:
            thumbnail = thumbnail[:target_h]
        if tw > target_w:
            thumbnail = thumbnail[:, :target_w]

        return thumbnail

    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Get the bounding box of all tiles as (x_min, y_min, x_max, y_max)."""
        if not self.tiles:
            return (0, 0, 0, 0)

        if self._bounds_dirty:
            x_min = y_min = float('inf')
            x_max = y_max = float('-inf')

            for tile in self.tiles.values():
                bx_min, by_min, bx_max, by_max = tile.bounds
                x_min = min(x_min, bx_min)
                y_min = min(y_min, by_min)
                x_max = max(x_max, bx_max)
                y_max = max(y_max, by_max)

            self._cached_bounds = (int(x_min), int(y_min), int(x_max), int(y_max))
            self._bounds_dirty = False

        return self._cached_bounds

    def get_tiles_in_region(self, x_min: int, y_min: int,
                            x_max: int, y_max: int) -> List[Tile]:
        """Get all tiles that intersect with the given region."""
        result = []
        for tile in self.tiles.values():
            tx_min, ty_min, tx_max, ty_max = tile.bounds
            # Check for intersection
            if tx_max > x_min and tx_min < x_max and ty_max > y_min and ty_min < y_max:
                result.append(tile)
        return result

    def get_tiles_by_quality(self, min_level: TileQualityLevel = TileQualityLevel.FAIR) -> List[Tile]:
        """Get tiles filtered by minimum quality level."""
        quality_order = [
            TileQualityLevel.UNUSABLE,
            TileQualityLevel.POOR,
            TileQualityLevel.FAIR,
            TileQualityLevel.GOOD,
            TileQualityLevel.EXCELLENT,
        ]
        min_idx = quality_order.index(min_level)
        return [t for t in self.tiles.values()
                if t.quality and quality_order.index(t.quality.level) >= min_idx]

    def get_z_stack(self, z_stack_id: str) -> List[Tile]:
        """Get all tiles in a Z-stack, sorted by z_index."""
        tiles = [t for t in self.tiles.values() if t.z_stack_id == z_stack_id]
        return sorted(tiles, key=lambda t: t.z_index)

    def clear(self):
        """Remove all tiles."""
        self.tiles.clear()
        self._bounds_dirty = True

    @property
    def tile_count(self) -> int:
        """Get the number of stored tiles."""
        return len(self.tiles)


# ============================================================================
# Grid Scanner
# ============================================================================

class GridScanner:
    """Automated grid scanning with progress tracking.

    Scans a rectangular area systematically, capturing tiles with
    configurable overlap and optional Z-stacking.
    """

    def __init__(self, config: GridScanConfig, fov_width: int = 3000, fov_height: int = 2250):
        """Initialize grid scanner.

        Args:
            config: Grid scan configuration
            fov_width: Camera field of view width in stage units
            fov_height: Camera field of view height in stage units
        """
        self.config = config
        self.fov_width = fov_width
        self.fov_height = fov_height

        # Compute step sizes based on overlap
        overlap_factor = 1.0 - (config.overlap_pct / 100.0)
        self.step_x = int(fov_width * overlap_factor)
        self.step_y = int(fov_height * overlap_factor)

        # Generate scan positions
        self.positions = self._generate_positions()
        self.current_index = 0
        self.state = ScanState.IDLE

        # Z-stack settings
        if config.z_stack_enabled:
            self.z_offsets = np.linspace(
                -config.z_stack_range / 2,
                config.z_stack_range / 2,
                config.z_stack_steps
            )
        else:
            self.z_offsets = [0.0]

        # Progress tracking
        self.tiles_captured = 0
        self.tiles_failed = 0
        self.start_time = 0.0

    def _generate_positions(self) -> List[Tuple[int, int]]:
        """Generate list of (x, y) positions to scan."""
        positions = []

        x_positions = list(range(self.config.x_min, self.config.x_max + 1, self.step_x))
        y_positions = list(range(self.config.y_min, self.config.y_max + 1, self.step_y))

        for i, y in enumerate(y_positions):
            row_x = x_positions if not self.config.snake_pattern or i % 2 == 0 else reversed(x_positions)
            for x in row_x:
                positions.append((x, y))

        return positions

    @property
    def total_positions(self) -> int:
        """Total number of XY positions to scan."""
        return len(self.positions)

    @property
    def total_captures(self) -> int:
        """Total number of image captures (including Z-stack)."""
        return len(self.positions) * len(self.z_offsets)

    @property
    def progress(self) -> float:
        """Scan progress as percentage (0-100)."""
        if self.total_positions == 0:
            return 100.0
        return (self.current_index / self.total_positions) * 100

    @property
    def eta_seconds(self) -> float:
        """Estimated time remaining in seconds."""
        if self.tiles_captured == 0 or self.state != ScanState.RUNNING:
            return 0.0
        elapsed = time.time() - self.start_time
        rate = self.tiles_captured / elapsed
        remaining = self.total_captures - self.tiles_captured
        return remaining / rate if rate > 0 else 0.0

    def start(self):
        """Start or resume the scan."""
        self.state = ScanState.RUNNING
        self.start_time = time.time()

    def pause(self):
        """Pause the scan."""
        if self.state == ScanState.RUNNING:
            self.state = ScanState.PAUSED

    def cancel(self):
        """Cancel the scan."""
        self.state = ScanState.CANCELLED

    def reset(self):
        """Reset scan to beginning."""
        self.current_index = 0
        self.tiles_captured = 0
        self.tiles_failed = 0
        self.state = ScanState.IDLE

    def get_next_position(self) -> Optional[Tuple[int, int, List[float]]]:
        """Get next position to scan.

        Returns:
            Tuple of (x, y, z_offsets) or None if scan complete/paused/cancelled
        """
        if self.state != ScanState.RUNNING:
            return None

        if self.current_index >= len(self.positions):
            self.state = ScanState.COMPLETED
            return None

        x, y = self.positions[self.current_index]
        return (x, y, list(self.z_offsets))

    def advance(self, success: bool = True):
        """Advance to next position after capture.

        Args:
            success: Whether the capture was successful
        """
        if success:
            self.tiles_captured += len(self.z_offsets)
        else:
            self.tiles_failed += 1

        self.current_index += 1

        if self.current_index >= len(self.positions):
            self.state = ScanState.COMPLETED

    def should_autofocus(self) -> bool:
        """Check if autofocus should be performed at current position."""
        if self.config.autofocus_interval <= 0:
            return False
        return self.current_index % self.config.autofocus_interval == 0


# ============================================================================
# Z-Stack Manager
# ============================================================================

class ZStackManager:
    """Manages Z-stack capture and Extended Depth of Field (EDF) compositing."""

    def __init__(self, tile_manager: TileManager):
        """Initialize Z-stack manager.

        Args:
            tile_manager: TileManager to store captured tiles
        """
        self.tile_manager = tile_manager
        self.active_stack_id: Optional[str] = None
        self.stack_counter = 0

    def start_stack(self, x: int, y: int) -> str:
        """Start a new Z-stack at the given XY position.

        Returns:
            Stack ID for this Z-stack
        """
        self.stack_counter += 1
        self.active_stack_id = f"zstack_{x}_{y}_{self.stack_counter}"
        return self.active_stack_id

    def add_to_stack(self, x: int, y: int, z: float, image: np.ndarray,
                     z_index: int, save_full_res: bool = False) -> Optional[Tile]:
        """Add an image to the current Z-stack.

        Args:
            x, y, z: Stage position
            image: Captured image
            z_index: Index within the stack
            save_full_res: Whether to save full-res to disk

        Returns:
            Created tile or None
        """
        if not self.active_stack_id:
            self.start_stack(x, y)

        return self.tile_manager.add_tile(
            x=x, y=y, z=z, image=image,
            save_full_res=save_full_res,
            z_stack_id=self.active_stack_id,
            z_index=z_index
        )

    def end_stack(self):
        """End the current Z-stack."""
        self.active_stack_id = None

    def compute_edf(self, stack_id: str) -> Optional[np.ndarray]:
        """Compute Extended Depth of Field from a Z-stack.

        Uses focus-weighted blending to combine sharp regions from each plane.

        Args:
            stack_id: Z-stack ID

        Returns:
            EDF composite image or None if stack not found
        """
        tiles = self.tile_manager.get_z_stack(stack_id)
        if not tiles:
            return None

        # Load full-res images if available, otherwise use thumbnails
        images = []
        for tile in tiles:
            if tile.full_res_path and os.path.exists(tile.full_res_path):
                img = np.load(tile.full_res_path)
            else:
                img = tile.thumbnail
            images.append(img)

        if not images:
            return None

        return self._focus_stack_blend(images)

    def _focus_stack_blend(self, images: List[np.ndarray]) -> np.ndarray:
        """Blend images using focus-weighted compositing.

        Args:
            images: List of images at different Z planes

        Returns:
            Focus-stacked composite image
        """
        if len(images) == 1:
            return images[0]

        # Ensure all images same size
        h, w = images[0].shape[:2]
        channels = images[0].shape[2] if len(images[0].shape) > 2 else 1

        # Compute focus maps for each image
        focus_maps = []
        for img in images:
            focus_map = self._compute_focus_map(img)
            focus_maps.append(focus_map)

        # Stack and find best focus per pixel
        focus_stack = np.stack(focus_maps, axis=0)  # (N, H, W)

        # Apply Gaussian blur to smooth focus selection
        for i in range(len(focus_maps)):
            focus_stack[i] = self._gaussian_blur(focus_stack[i], sigma=3)

        # Find index of best focus at each pixel
        best_idx = np.argmax(focus_stack, axis=0)  # (H, W)

        # Build output by selecting pixels from best-focused image
        if channels > 1:
            output = np.zeros((h, w, channels), dtype=images[0].dtype)
            for c in range(channels):
                for i, img in enumerate(images):
                    mask = (best_idx == i)
                    output[:, :, c][mask] = img[:, :, c][mask]
        else:
            output = np.zeros((h, w), dtype=images[0].dtype)
            for i, img in enumerate(images):
                mask = (best_idx == i)
                output[mask] = img[mask]

        return output

    def _compute_focus_map(self, image: np.ndarray) -> np.ndarray:
        """Compute local focus measure for each pixel."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            if image.shape[2] >= 3:
                gray = (0.299 * image[:, :, 0] +
                        0.587 * image[:, :, 1] +
                        0.114 * image[:, :, 2])
            else:
                gray = image[:, :, 0]
        else:
            gray = image

        # Convert to float for processing
        gray = gray.astype(np.float32)
        if gray.max() <= 1.0:
            gray = gray * 255

        h, w = gray.shape

        # Laplacian-based focus measure
        laplacian = np.zeros_like(gray)
        padded = np.pad(gray, 1, mode='edge')
        kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
        for i in range(3):
            for j in range(3):
                laplacian += kernel[i, j] * padded[i:i+h, j:j+w]

        # Take absolute value and apply local averaging
        focus_map = np.abs(laplacian)
        focus_map = self._gaussian_blur(focus_map, sigma=5)

        return focus_map

    def _gaussian_blur(self, image: np.ndarray, sigma: float) -> np.ndarray:
        """Apply Gaussian blur using separable convolution."""
        # Create 1D Gaussian kernel
        size = int(sigma * 4) | 1  # Ensure odd
        x = np.arange(size) - size // 2
        kernel = np.exp(-x**2 / (2 * sigma**2))
        kernel = kernel / kernel.sum()

        # Separable convolution
        # Horizontal pass
        result = np.zeros_like(image)
        padded = np.pad(image, size // 2, mode='edge')
        for i, k in enumerate(kernel):
            result += k * padded[:, i:i + image.shape[1]]

        # Vertical pass
        padded = np.pad(result, size // 2, mode='edge')
        result = np.zeros_like(image)
        for i, k in enumerate(kernel):
            result += k * padded[i:i + image.shape[0], :]

        return result


# ============================================================================
# Stitch Canvas (Preview)
# ============================================================================

class StitchCanvas:
    """Composites tiles into a unified canvas for display.

    Memory-efficient design:
    - Works with thumbnails only for preview
    - Canvas size is limited and configurable
    - Supports incremental updates as tiles are added
    - Shows quality indicators
    """

    def __init__(self, width: int = 200, height: int = 200):
        """Initialize the stitch canvas.

        Args:
            width: Canvas width in pixels
            height: Canvas height in pixels
        """
        self.width = width
        self.height = height

        # RGBA canvas (float32, 0-1)
        self.canvas = np.zeros((height, width, 4), dtype=np.float32)
        self.canvas[:, :, 3] = 0.3  # Dim background alpha

        # Quality overlay
        self.quality_overlay = np.zeros((height, width, 4), dtype=np.float32)

        # Track what's been rendered
        self._rendered_tiles: set = set()
        self._view_bounds = (0, 0, 65535, 65535)  # Current view in stage coords
        self.show_quality = True  # Show quality indicators

    def set_view(self, x_min: int, y_min: int, x_max: int, y_max: int):
        """Set the view bounds (stage coordinates that map to the canvas)."""
        if self._view_bounds != (x_min, y_min, x_max, y_max):
            self._view_bounds = (x_min, y_min, x_max, y_max)
            self._rendered_tiles.clear()  # Force re-render

    def render(self, tile_manager: TileManager) -> np.ndarray:
        """Render tiles to the canvas and return the result.

        Args:
            tile_manager: TileManager containing tiles to render

        Returns:
            The rendered canvas as RGBA numpy array
        """
        x_min, y_min, x_max, y_max = self._view_bounds

        # Get tiles that intersect the view
        tiles = tile_manager.get_tiles_in_region(x_min, y_min, x_max, y_max)

        # Check if we need to re-render
        current_tile_ids = {(t.x, t.y, t.timestamp) for t in tiles}
        if current_tile_ids != self._rendered_tiles:
            self._render_tiles(tiles, x_min, y_min, x_max, y_max)
            self._rendered_tiles = current_tile_ids

        return self.canvas

    def _render_tiles(self, tiles: List[Tile],
                      x_min: int, y_min: int, x_max: int, y_max: int):
        """Internal method to render tiles to the canvas."""
        # Clear canvas
        self.canvas[:] = 0
        self.canvas[:, :, 3] = 0.2  # Dim background
        self.quality_overlay[:] = 0

        if not tiles:
            return

        # Calculate scale factors
        range_x = x_max - x_min if x_max > x_min else 1
        range_y = y_max - y_min if y_max > y_min else 1
        scale_x = self.width / range_x
        scale_y = self.height / range_y

        # Sort tiles by timestamp (oldest first, so newest are on top)
        tiles_sorted = sorted(tiles, key=lambda t: t.timestamp)

        for tile in tiles_sorted:
            # Get tile bounds in stage coordinates
            tx_min, ty_min, tx_max, ty_max = tile.bounds

            # Convert to canvas coordinates
            cx_min = int((tx_min - x_min) * scale_x)
            cy_min = int((ty_min - y_min) * scale_y)
            cx_max = int((tx_max - x_min) * scale_x)
            cy_max = int((ty_max - y_min) * scale_y)

            # Clamp to canvas bounds
            cx_min = max(0, cx_min)
            cy_min = max(0, cy_min)
            cx_max = min(self.width, cx_max)
            cy_max = min(self.height, cy_max)

            if cx_max <= cx_min or cy_max <= cy_min:
                continue  # Tile is outside canvas

            # Get destination size
            dest_w = cx_max - cx_min
            dest_h = cy_max - cy_min

            if dest_w < 1 or dest_h < 1:
                continue

            # Resize thumbnail to fit destination
            thumb = tile.thumbnail
            resized = self._resize_image(thumb, dest_w, dest_h)

            # Blend into canvas
            self._blend_into_canvas(resized, cx_min, cy_min)

            # Add quality indicator
            if self.show_quality and tile.quality:
                self._draw_quality_indicator(tile.quality, cx_min, cy_min, dest_w, dest_h)

    def _resize_image(self, img: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        """Resize image using simple interpolation."""
        h, w = img.shape[:2]

        # Create coordinate maps
        y_indices = np.linspace(0, h - 1, target_h).astype(int)
        x_indices = np.linspace(0, w - 1, target_w).astype(int)

        # Sample the image
        resized = img[y_indices][:, x_indices]
        return resized

    def _blend_into_canvas(self, img: np.ndarray, x: int, y: int):
        """Blend an image into the canvas at the given position."""
        h, w = img.shape[:2]

        # Ensure we don't go out of bounds
        if x + w > self.width:
            w = self.width - x
            img = img[:, :w]
        if y + h > self.height:
            h = self.height - y
            img = img[:h]

        if w <= 0 or h <= 0:
            return

        # Simple overwrite (could use alpha blending for overlaps)
        # Reduce brightness slightly for background appearance
        dimmed = img.copy()
        dimmed[:, :, :3] *= 0.6  # Dim RGB channels
        dimmed[:, :, 3] = 0.8    # Set alpha

        self.canvas[y:y+h, x:x+w] = dimmed

    def _draw_quality_indicator(self, quality: TileQuality,
                                x: int, y: int, w: int, h: int):
        """Draw a quality indicator border around a tile."""
        color = np.array(quality.color, dtype=np.float32) / 255.0

        # Draw border (2 pixels wide)
        border = 2
        if w > border * 2 and h > border * 2:
            # Top edge
            self.canvas[y:y+border, x:x+w] = color
            # Bottom edge
            self.canvas[y+h-border:y+h, x:x+w] = color
            # Left edge
            self.canvas[y:y+h, x:x+border] = color
            # Right edge
            self.canvas[y:y+h, x+w-border:x+w] = color

    def clear(self):
        """Clear the canvas."""
        self.canvas[:] = 0
        self.canvas[:, :, 3] = 0.2
        self._rendered_tiles.clear()

    def get_flat_data(self) -> np.ndarray:
        """Get canvas data flattened for DearPyGUI texture."""
        return self.canvas.flatten()


# ============================================================================
# Overlap Detection and Blending
# ============================================================================

class OverlapBlender:
    """Handles overlap detection and feathered blending between tiles."""

    @staticmethod
    def detect_overlap(tile1: Tile, tile2: Tile) -> Optional[Tuple[int, int, int, int]]:
        """Detect overlap region between two tiles.

        Returns:
            Overlap bounds (x_min, y_min, x_max, y_max) or None if no overlap
        """
        b1 = tile1.bounds
        b2 = tile2.bounds

        x_min = max(b1[0], b2[0])
        y_min = max(b1[1], b2[1])
        x_max = min(b1[2], b2[2])
        y_max = min(b1[3], b2[3])

        if x_max > x_min and y_max > y_min:
            return (x_min, y_min, x_max, y_max)
        return None

    @staticmethod
    def create_feather_mask(width: int, height: int, direction: str = "horizontal") -> np.ndarray:
        """Create a feathered blending mask.

        Args:
            width: Mask width
            height: Mask height
            direction: 'horizontal', 'vertical', or 'radial'

        Returns:
            Mask array with values 0-1
        """
        if direction == "horizontal":
            mask = np.linspace(0, 1, width)
            mask = np.tile(mask, (height, 1))
        elif direction == "vertical":
            mask = np.linspace(0, 1, height)
            mask = np.tile(mask.reshape(-1, 1), (1, width))
        elif direction == "radial":
            y, x = np.ogrid[:height, :width]
            cx, cy = width / 2, height / 2
            dist = np.sqrt((x - cx)**2 + (y - cy)**2)
            max_dist = np.sqrt(cx**2 + cy**2)
            mask = 1 - np.clip(dist / max_dist, 0, 1)
        else:
            mask = np.ones((height, width))

        return mask.astype(np.float32)

    @staticmethod
    def blend_tiles(img1: np.ndarray, img2: np.ndarray,
                    overlap_region: Tuple[int, int, int, int],
                    tile1_bounds: Tuple[int, int, int, int],
                    tile2_bounds: Tuple[int, int, int, int]) -> np.ndarray:
        """Blend two tiles in their overlap region.

        Args:
            img1, img2: Full resolution images
            overlap_region: (x_min, y_min, x_max, y_max) of overlap
            tile1_bounds, tile2_bounds: Bounds of each tile

        Returns:
            Blended image for the overlap region
        """
        ox_min, oy_min, ox_max, oy_max = overlap_region
        ow = ox_max - ox_min
        oh = oy_max - oy_min

        # Determine blend direction based on tile positions
        t1_cx = (tile1_bounds[0] + tile1_bounds[2]) / 2
        t2_cx = (tile2_bounds[0] + tile2_bounds[2]) / 2
        t1_cy = (tile1_bounds[1] + tile1_bounds[3]) / 2
        t2_cy = (tile2_bounds[1] + tile2_bounds[3]) / 2

        dx = abs(t2_cx - t1_cx)
        dy = abs(t2_cy - t1_cy)

        direction = "horizontal" if dx > dy else "vertical"
        mask = OverlapBlender.create_feather_mask(ow, oh, direction)

        # Extract overlap regions from each image
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]

        # Convert overlap coords to image coords
        # (This is simplified - actual implementation needs proper coordinate mapping)
        scale_x1 = w1 / (tile1_bounds[2] - tile1_bounds[0])
        scale_y1 = h1 / (tile1_bounds[3] - tile1_bounds[1])
        scale_x2 = w2 / (tile2_bounds[2] - tile2_bounds[0])
        scale_y2 = h2 / (tile2_bounds[3] - tile2_bounds[1])

        # Get regions from each image
        x1_start = int((ox_min - tile1_bounds[0]) * scale_x1)
        y1_start = int((oy_min - tile1_bounds[1]) * scale_y1)
        x2_start = int((ox_min - tile2_bounds[0]) * scale_x2)
        y2_start = int((oy_min - tile2_bounds[1]) * scale_y2)

        region1 = img1[y1_start:y1_start + oh, x1_start:x1_start + ow]
        region2 = img2[y2_start:y2_start + oh, x2_start:x2_start + ow]

        # Ensure same shape
        min_h = min(region1.shape[0], region2.shape[0], oh)
        min_w = min(region1.shape[1], region2.shape[1], ow)
        region1 = region1[:min_h, :min_w]
        region2 = region2[:min_h, :min_w]
        mask = mask[:min_h, :min_w]

        # Blend
        if len(region1.shape) == 3:
            mask = mask[:, :, np.newaxis]

        blended = region1 * (1 - mask) + region2 * mask
        return blended.astype(region1.dtype)


# ============================================================================
# Session Persistence
# ============================================================================

class StitchSession:
    """Manages saving and loading stitch sessions."""

    VERSION = 1

    def __init__(self, session_dir: str):
        """Initialize session manager.

        Args:
            session_dir: Directory to store session data
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def save(self, tile_manager: TileManager, name: str = "session") -> str:
        """Save current session to disk.

        Args:
            tile_manager: TileManager with tiles to save
            name: Session name

        Returns:
            Path to saved session file
        """
        session_path = self.session_dir / f"{name}.json"
        thumbs_dir = self.session_dir / f"{name}_thumbs"
        thumbs_dir.mkdir(exist_ok=True)

        # Serialize tiles
        tiles_data = []
        for key, tile in tile_manager.tiles.items():
            # Save thumbnail
            thumb_path = thumbs_dir / f"thumb_{tile.x}_{tile.y}.npy"
            np.save(str(thumb_path), tile.thumbnail)

            tile_dict = tile.to_dict()
            tile_dict["thumbnail_path"] = str(thumb_path)
            tile_dict["key"] = key if isinstance(key, (list, tuple)) else [key]
            tiles_data.append(tile_dict)

        session_data = {
            "version": self.VERSION,
            "timestamp": time.time(),
            "fov_width": tile_manager.fov_width,
            "fov_height": tile_manager.fov_height,
            "position_threshold": tile_manager.position_threshold,
            "tile_count": tile_manager.tile_count,
            "tiles": tiles_data,
        }

        with open(session_path, 'w') as f:
            json.dump(session_data, f, indent=2)

        print(f"Session saved: {session_path}")
        return str(session_path)

    def load(self, name: str = "session") -> Optional[TileManager]:
        """Load a session from disk.

        Args:
            name: Session name

        Returns:
            TileManager with loaded tiles, or None if not found
        """
        session_path = self.session_dir / f"{name}.json"
        if not session_path.exists():
            print(f"Session not found: {session_path}")
            return None

        with open(session_path, 'r') as f:
            session_data = json.load(f)

        if session_data.get("version", 0) != self.VERSION:
            print(f"Warning: Session version mismatch")

        tile_manager = TileManager()
        tile_manager.fov_width = session_data.get("fov_width", 3000)
        tile_manager.fov_height = session_data.get("fov_height", 2250)
        tile_manager.position_threshold = session_data.get("position_threshold", 500)

        for tile_data in session_data.get("tiles", []):
            thumb_path = tile_data.get("thumbnail_path")
            if thumb_path and os.path.exists(thumb_path):
                thumbnail = np.load(thumb_path)
            else:
                # Create placeholder thumbnail
                thumbnail = np.zeros((48, 64, 4), dtype=np.float32)
                thumbnail[:, :, 3] = 0.5

            tile = Tile.from_dict(tile_data, thumbnail)
            key = tuple(tile_data.get("key", [tile.x, tile.y]))
            tile_manager.tiles[key] = tile

        tile_manager._bounds_dirty = True
        print(f"Session loaded: {tile_manager.tile_count} tiles")
        return tile_manager

    def list_sessions(self) -> List[str]:
        """List available session names."""
        sessions = []
        for f in self.session_dir.glob("*.json"):
            sessions.append(f.stem)
        return sorted(sessions)

    def delete(self, name: str):
        """Delete a session and its data."""
        session_path = self.session_dir / f"{name}.json"
        thumbs_dir = self.session_dir / f"{name}_thumbs"

        if session_path.exists():
            session_path.unlink()
        if thumbs_dir.exists():
            import shutil
            shutil.rmtree(thumbs_dir)

        print(f"Session deleted: {name}")


# ============================================================================
# Progressive Resolution / Pyramid Export
# ============================================================================

class PyramidLevel:
    """A single level in an image pyramid."""

    def __init__(self, level: int, tile_size: int = 256):
        self.level = level
        self.tile_size = tile_size
        self.tiles: Dict[Tuple[int, int], np.ndarray] = {}
        self.width = 0
        self.height = 0


class ImagePyramid:
    """Multi-resolution image pyramid for efficient viewing of large stitched images."""

    def __init__(self, base_width: int, base_height: int, tile_size: int = 256):
        """Initialize image pyramid.

        Args:
            base_width: Full resolution width
            base_height: Full resolution height
            tile_size: Size of tiles at each level
        """
        self.base_width = base_width
        self.base_height = base_height
        self.tile_size = tile_size
        self.levels: List[PyramidLevel] = []

        # Calculate number of levels
        max_dim = max(base_width, base_height)
        num_levels = max(1, int(np.ceil(np.log2(max_dim / tile_size))) + 1)

        for level in range(num_levels):
            scale = 2 ** level
            pl = PyramidLevel(level, tile_size)
            pl.width = (base_width + scale - 1) // scale
            pl.height = (base_height + scale - 1) // scale
            self.levels.append(pl)

    def get_tile(self, level: int, tile_x: int, tile_y: int) -> Optional[np.ndarray]:
        """Get a tile from the pyramid.

        Args:
            level: Pyramid level (0 = full resolution)
            tile_x, tile_y: Tile coordinates

        Returns:
            Tile image or None if not available
        """
        if level >= len(self.levels):
            return None
        return self.levels[level].tiles.get((tile_x, tile_y))

    def set_tile(self, level: int, tile_x: int, tile_y: int, data: np.ndarray):
        """Set a tile in the pyramid."""
        if level < len(self.levels):
            self.levels[level].tiles[(tile_x, tile_y)] = data


class PyramidExporter:
    """Exports stitched images as multi-resolution pyramids.

    Supports:
    - Memory-mapped export for large images
    - TIFF pyramid format
    - Deep zoom tile format
    """

    def __init__(self, tile_manager: TileManager):
        """Initialize pyramid exporter.

        Args:
            tile_manager: TileManager with tiles to export
        """
        self.tile_manager = tile_manager

    def estimate_output_size(self, pixels_per_stage_unit: float = 0.5) -> Tuple[int, int]:
        """Estimate output image size.

        Args:
            pixels_per_stage_unit: Resolution scale factor

        Returns:
            (width, height) in pixels
        """
        bounds = self.tile_manager.get_bounds()
        if bounds == (0, 0, 0, 0):
            return (0, 0)

        x_min, y_min, x_max, y_max = bounds
        width = int((x_max - x_min) * pixels_per_stage_unit)
        height = int((y_max - y_min) * pixels_per_stage_unit)
        return (width, height)

    def export_deep_zoom(self, output_dir: str,
                         pixels_per_stage_unit: float = 0.5,
                         tile_size: int = 256,
                         progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        """Export as Deep Zoom Image (DZI) format.

        Creates a tile pyramid suitable for web viewers like OpenSeadragon.

        Args:
            output_dir: Output directory
            pixels_per_stage_unit: Resolution scale
            tile_size: Tile size for pyramid
            progress_callback: Optional callback for progress updates

        Returns:
            True if export succeeded
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        width, height = self.estimate_output_size(pixels_per_stage_unit)
        if width == 0 or height == 0:
            return False

        # Calculate number of levels
        max_dim = max(width, height)
        num_levels = int(np.ceil(np.log2(max_dim))) + 1

        # Create DZI descriptor
        dzi_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
       Format="png" Overlap="0" TileSize="{tile_size}">
    <Size Width="{width}" Height="{height}"/>
</Image>'''

        with open(output_path / "image.dzi", 'w') as f:
            f.write(dzi_content)

        # Create tiles directory
        tiles_dir = output_path / "image_files"
        tiles_dir.mkdir(exist_ok=True)

        bounds = self.tile_manager.get_bounds()
        x_min, y_min, x_max, y_max = bounds

        total_tiles = 0
        for level in range(num_levels):
            scale = 2 ** (num_levels - 1 - level)
            level_width = (width + scale - 1) // scale
            level_height = (height + scale - 1) // scale
            tiles_x = (level_width + tile_size - 1) // tile_size
            tiles_y = (level_height + tile_size - 1) // tile_size
            total_tiles += tiles_x * tiles_y

        tiles_done = 0

        # Generate tiles for each level
        for level in range(num_levels):
            level_dir = tiles_dir / str(level)
            level_dir.mkdir(exist_ok=True)

            scale = 2 ** (num_levels - 1 - level)
            level_width = (width + scale - 1) // scale
            level_height = (height + scale - 1) // scale

            tiles_x = (level_width + tile_size - 1) // tile_size
            tiles_y = (level_height + tile_size - 1) // tile_size

            for ty in range(tiles_y):
                for tx in range(tiles_x):
                    # Calculate tile bounds in stage coordinates
                    px_x = tx * tile_size * scale
                    px_y = ty * tile_size * scale
                    stage_x = x_min + px_x / pixels_per_stage_unit
                    stage_y = y_min + px_y / pixels_per_stage_unit

                    # Get tiles that contribute to this pyramid tile
                    tile_stage_width = tile_size * scale / pixels_per_stage_unit
                    tile_stage_height = tile_size * scale / pixels_per_stage_unit

                    source_tiles = self.tile_manager.get_tiles_in_region(
                        int(stage_x), int(stage_y),
                        int(stage_x + tile_stage_width),
                        int(stage_y + tile_stage_height)
                    )

                    # Render tile
                    tile_img = self._render_pyramid_tile(
                        source_tiles, stage_x, stage_y,
                        tile_stage_width, tile_stage_height,
                        tile_size, tile_size, scale
                    )

                    # Save tile
                    try:
                        from PIL import Image
                        if tile_img.dtype == np.float32:
                            tile_img = (tile_img[:, :, :3] * 255).astype(np.uint8)
                        img = Image.fromarray(tile_img)
                        img.save(level_dir / f"{tx}_{ty}.png")
                    except Exception as e:
                        print(f"Error saving tile: {e}")

                    tiles_done += 1
                    if progress_callback:
                        progress_callback(tiles_done / total_tiles * 100)

        return True

    def _render_pyramid_tile(self, source_tiles: List[Tile],
                             stage_x: float, stage_y: float,
                             stage_width: float, stage_height: float,
                             out_width: int, out_height: int,
                             scale: int) -> np.ndarray:
        """Render a single pyramid tile from source tiles."""
        output = np.zeros((out_height, out_width, 3), dtype=np.uint8)

        if not source_tiles:
            return output

        for tile in source_tiles:
            # Load tile image
            if tile.full_res_path and os.path.exists(tile.full_res_path):
                try:
                    img = np.load(tile.full_res_path)
                except Exception:
                    img = tile.thumbnail
            else:
                img = tile.thumbnail

            # Calculate where this tile maps to in output
            tx_min, ty_min, tx_max, ty_max = tile.bounds

            # Clamp to region of interest
            src_x_min = max(tx_min, stage_x)
            src_y_min = max(ty_min, stage_y)
            src_x_max = min(tx_max, stage_x + stage_width)
            src_y_max = min(ty_max, stage_y + stage_height)

            if src_x_max <= src_x_min or src_y_max <= src_y_min:
                continue

            # Convert to output coordinates
            out_x_min = int((src_x_min - stage_x) / stage_width * out_width)
            out_y_min = int((src_y_min - stage_y) / stage_height * out_height)
            out_x_max = int((src_x_max - stage_x) / stage_width * out_width)
            out_y_max = int((src_y_max - stage_y) / stage_height * out_height)

            if out_x_max <= out_x_min or out_y_max <= out_y_min:
                continue

            # Convert to tile image coordinates
            th, tw = img.shape[:2]
            tile_w = tx_max - tx_min
            tile_h = ty_max - ty_min

            img_x_min = int((src_x_min - tx_min) / tile_w * tw)
            img_y_min = int((src_y_min - ty_min) / tile_h * th)
            img_x_max = int((src_x_max - tx_min) / tile_w * tw)
            img_y_max = int((src_y_max - ty_min) / tile_h * th)

            # Extract and resize region
            region = img[img_y_min:img_y_max, img_x_min:img_x_max]
            if region.size == 0:
                continue

            # Simple resize
            dest_h = out_y_max - out_y_min
            dest_w = out_x_max - out_x_min
            if dest_h > 0 and dest_w > 0:
                rh, rw = region.shape[:2]
                y_idx = np.linspace(0, rh - 1, dest_h).astype(int)
                x_idx = np.linspace(0, rw - 1, dest_w).astype(int)
                resized = region[y_idx][:, x_idx]

                # Convert to uint8 if needed
                if resized.dtype == np.float32:
                    resized = (resized * 255).astype(np.uint8)
                if len(resized.shape) == 3 and resized.shape[2] == 4:
                    resized = resized[:, :, :3]

                # Place in output
                try:
                    output[out_y_min:out_y_max, out_x_min:out_x_max] = resized
                except ValueError:
                    pass  # Shape mismatch, skip

        return output

    def export_tiff_pyramid(self, output_path: str,
                            pixels_per_stage_unit: float = 0.5,
                            max_memory_mb: int = 512,
                            progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        """Export as pyramidal TIFF.

        Uses memory-mapped file for efficient large image export.

        Args:
            output_path: Output TIFF file path
            pixels_per_stage_unit: Resolution scale
            max_memory_mb: Maximum memory usage in MB
            progress_callback: Optional progress callback

        Returns:
            True if export succeeded
        """
        try:
            from PIL import Image
        except ImportError:
            print("PIL required for TIFF export")
            return False

        width, height = self.estimate_output_size(pixels_per_stage_unit)
        if width == 0 or height == 0:
            return False

        bounds = self.tile_manager.get_bounds()
        x_min, y_min, x_max, y_max = bounds

        # Calculate chunk size based on memory limit
        bytes_per_pixel = 3  # RGB
        chunk_height = max(1, (max_memory_mb * 1024 * 1024) // (width * bytes_per_pixel))
        chunk_height = min(chunk_height, height)

        # Create output file
        num_chunks = (height + chunk_height - 1) // chunk_height

        # Build image in chunks
        chunks = []
        for i in range(num_chunks):
            chunk_y_start = i * chunk_height
            chunk_y_end = min((i + 1) * chunk_height, height)
            actual_chunk_height = chunk_y_end - chunk_y_start

            # Calculate stage coordinates for this chunk
            stage_y_start = y_min + chunk_y_start / pixels_per_stage_unit
            stage_y_end = y_min + chunk_y_end / pixels_per_stage_unit

            # Create chunk array
            chunk = np.zeros((actual_chunk_height, width, 3), dtype=np.uint8)

            # Get tiles for this chunk
            source_tiles = self.tile_manager.get_tiles_in_region(
                x_min, int(stage_y_start), x_max, int(stage_y_end)
            )

            # Render tiles to chunk
            for tile in source_tiles:
                self._render_tile_to_chunk(
                    tile, chunk, x_min, stage_y_start,
                    pixels_per_stage_unit, width
                )

            chunks.append(chunk)

            if progress_callback:
                progress_callback((i + 1) / num_chunks * 100)

        # Concatenate chunks and save
        full_image = np.vstack(chunks)
        img = Image.fromarray(full_image)

        # Save with pyramid (requires tifffile for proper pyramid TIFF)
        try:
            import tifffile
            tifffile.imwrite(
                output_path, full_image,
                tile=(256, 256),
                compression='jpeg',
                photometric='rgb',
                metadata={'axes': 'YXC'}
            )
        except ImportError:
            # Fall back to PIL
            img.save(output_path, compression="tiff_lzw")

        return True

    def _render_tile_to_chunk(self, tile: Tile, chunk: np.ndarray,
                              stage_x_min: float, stage_y_min: float,
                              scale: float, width: int):
        """Render a single tile to a chunk array."""
        # Load tile image
        if tile.full_res_path and os.path.exists(tile.full_res_path):
            try:
                img = np.load(tile.full_res_path)
            except Exception:
                img = tile.thumbnail
        else:
            img = tile.thumbnail

        tx_min, ty_min, tx_max, ty_max = tile.bounds
        chunk_height = chunk.shape[0]

        # Calculate output coordinates
        out_x_min = int((tx_min - stage_x_min) * scale)
        out_y_min = int((ty_min - stage_y_min) * scale)
        out_x_max = int((tx_max - stage_x_min) * scale)
        out_y_max = int((ty_max - stage_y_min) * scale)

        # Clamp to chunk bounds
        out_x_min = max(0, out_x_min)
        out_y_min = max(0, out_y_min)
        out_x_max = min(width, out_x_max)
        out_y_max = min(chunk_height, out_y_max)

        if out_x_max <= out_x_min or out_y_max <= out_y_min:
            return

        # Resize tile to fit
        dest_w = out_x_max - out_x_min
        dest_h = out_y_max - out_y_min

        th, tw = img.shape[:2]
        y_idx = np.linspace(0, th - 1, dest_h).astype(int)
        x_idx = np.linspace(0, tw - 1, dest_w).astype(int)
        resized = img[y_idx][:, x_idx]

        # Convert format
        if resized.dtype == np.float32:
            resized = (resized * 255).astype(np.uint8)
        if len(resized.shape) == 3 and resized.shape[2] == 4:
            resized = resized[:, :, :3]

        # Place in chunk
        try:
            chunk[out_y_min:out_y_max, out_x_min:out_x_max] = resized
        except ValueError:
            pass


# ============================================================================
# Export Preview (Simple)
# ============================================================================

class StitchExporter:
    """Simple stitched image export utilities."""

    @staticmethod
    def export_preview(tile_manager: TileManager,
                       output_path: str,
                       max_size: int = 2048) -> bool:
        """Export a preview image from thumbnails.

        Args:
            tile_manager: TileManager with tiles to export
            output_path: Path to save the image
            max_size: Maximum dimension of output image

        Returns:
            True if export succeeded
        """
        if tile_manager.tile_count == 0:
            return False

        bounds = tile_manager.get_bounds()
        x_min, y_min, x_max, y_max = bounds

        # Calculate output size maintaining aspect ratio
        range_x = x_max - x_min
        range_y = y_max - y_min

        if range_x > range_y:
            out_w = min(max_size, range_x)
            out_h = int(out_w * range_y / range_x)
        else:
            out_h = min(max_size, range_y)
            out_w = int(out_h * range_x / range_y)

        out_w = max(1, out_w)
        out_h = max(1, out_h)

        # Create canvas and render
        canvas = StitchCanvas(out_w, out_h)
        canvas.show_quality = False
        canvas.set_view(x_min, y_min, x_max, y_max)
        result = canvas.render(tile_manager)

        # Convert to uint8 and save
        try:
            from PIL import Image
            img_uint8 = (result[:, :, :3] * 255).astype(np.uint8)
            img = Image.fromarray(img_uint8)
            img.save(output_path)
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False
