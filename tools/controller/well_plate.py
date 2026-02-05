"""
96-Well Plate scanning module for CM30 Controller.

Provides capabilities for:
- Well plate coordinate mapping (well names <-> stage coordinates)
- Reference label scanning and stitching
- Automated plate alignment using etched labels
- Grid scanning of well plate regions

Standard 96-well plate layout:
- Rows: A-H (8 rows) varying along Y-axis
- Columns: 1-12 (12 columns) varying along X-axis
- Standard well spacing: 9mm (9000 stage units assuming 1 unit = 1 micron)
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

import numpy as np

from tools.controller.stitching import (
    TileManager, StitchCanvas, GridScanConfig, GridScanner,
    ScanState, TileQuality, QualityAssessor, StitchExporter
)


# ============================================================================
# Well Plate Configuration
# ============================================================================

class PlateType(Enum):
    """Standard well plate types."""
    PLATE_96 = "96-well"
    PLATE_48 = "48-well"
    PLATE_24 = "24-well"
    PLATE_12 = "12-well"
    PLATE_6 = "6-well"


@dataclass
class WellPlateConfig:
    """Configuration for a well plate type.

    All dimensions in stage units (typically microns).
    """
    plate_type: PlateType = PlateType.PLATE_96

    # Grid dimensions
    num_rows: int = 8       # A-H for 96-well
    num_cols: int = 12      # 1-12 for 96-well

    # Well spacing (center to center)
    well_spacing_x: int = 9000  # 9mm in microns
    well_spacing_y: int = 9000  # 9mm in microns

    # Well dimensions
    well_diameter: int = 6400   # ~6.4mm for 96-well

    # Label positions relative to well centers
    # Labels are typically between wells, offset from well center
    label_offset_x: int = 4500  # Halfway between wells in X
    label_offset_y: int = 4500  # Halfway between wells in Y

    # Estimated label size (for FOV coverage calculation)
    label_width: int = 3000     # Label width in stage units
    label_height: int = 2000    # Label height in stage units

    @property
    def row_labels(self) -> List[str]:
        """Get row labels (A-H for 96-well)."""
        return [chr(ord('A') + i) for i in range(self.num_rows)]

    @property
    def col_labels(self) -> List[int]:
        """Get column labels (1-12 for 96-well)."""
        return list(range(1, self.num_cols + 1))


# Default configurations for common plate types
PLATE_CONFIGS = {
    PlateType.PLATE_96: WellPlateConfig(
        plate_type=PlateType.PLATE_96,
        num_rows=8, num_cols=12,
        well_spacing_x=9000, well_spacing_y=9000,
        well_diameter=6400
    ),
    PlateType.PLATE_48: WellPlateConfig(
        plate_type=PlateType.PLATE_48,
        num_rows=6, num_cols=8,
        well_spacing_x=13000, well_spacing_y=13000,
        well_diameter=11000
    ),
}


# ============================================================================
# Reference Label Positions
# ============================================================================

@dataclass
class LabelReference:
    """A reference label position on the well plate.

    Labels are etched markers (like "B12", "H2") used for plate alignment.
    """
    well_name: str          # e.g., "B12", "H2"
    row: str                # e.g., "B", "H"
    col: int                # e.g., 12, 2
    approx_x: int           # Approximate X stage position
    approx_y: int           # Approximate Y stage position
    measured_x: Optional[int] = None    # Measured X after scanning
    measured_y: Optional[int] = None    # Measured Y after scanning
    measured_z: Optional[float] = None  # Z position from autofocus
    scan_complete: bool = False
    tiles: List = field(default_factory=list)  # Captured tiles for this label

    @classmethod
    def from_well_name(cls, well_name: str, approx_x: int, approx_y: int) -> "LabelReference":
        """Create a label reference from well name and approximate position."""
        row = well_name[0].upper()
        col = int(well_name[1:])
        return cls(
            well_name=well_name,
            row=row,
            col=col,
            approx_x=approx_x,
            approx_y=approx_y
        )


# Known reference label positions for the plate
# These are approximate positions that will be refined by scanning
DEFAULT_LABEL_REFERENCES = {
    "B12": LabelReference.from_well_name("B12", approx_x=15795, approx_y=18240),
    "H2": LabelReference.from_well_name("H2", approx_x=69995, approx_y=108220),
}


# ============================================================================
# Well Plate Coordinate System
# ============================================================================

class WellPlate:
    """Represents a 96-well plate with coordinate mapping.

    Handles conversion between:
    - Well names (A1, B12, H2, etc.)
    - Row/column indices (0-7, 0-11)
    - Stage coordinates (X, Y in microns)

    The plate coordinate system is established by scanning reference labels
    and computing an affine transformation.
    """

    def __init__(self, config: WellPlateConfig = None):
        """Initialize well plate.

        Args:
            config: Well plate configuration (defaults to 96-well)
        """
        self.config = config or PLATE_CONFIGS[PlateType.PLATE_96]

        # Reference labels for alignment
        self.references: Dict[str, LabelReference] = {}

        # Transformation parameters (computed from references)
        # Maps from well grid coordinates to stage coordinates
        self._transform_computed = False
        self._origin_x = 0      # Stage X of well A1 center
        self._origin_y = 0      # Stage Y of well A1 center
        self._scale_x = 1.0     # Stage units per grid unit in X
        self._scale_y = 1.0     # Stage units per grid unit in Y
        self._rotation = 0.0    # Rotation angle in radians

    def add_reference(self, ref: LabelReference):
        """Add a reference label."""
        self.references[ref.well_name] = ref
        self._transform_computed = False

    def get_reference(self, well_name: str) -> Optional[LabelReference]:
        """Get a reference label by well name."""
        return self.references.get(well_name.upper())

    def compute_transform(self) -> bool:
        """Compute the coordinate transformation from reference labels.

        Requires at least 2 measured reference labels.

        Returns:
            True if transform was computed successfully
        """
        # Get measured references
        measured = [ref for ref in self.references.values()
                   if ref.measured_x is not None and ref.measured_y is not None]

        if len(measured) < 2:
            print(f"Need at least 2 measured references, have {len(measured)}")
            return False

        # Use first two references to compute transform
        ref1, ref2 = measured[0], measured[1]

        # Convert well names to grid coordinates
        grid1 = self.well_name_to_grid(ref1.well_name)
        grid2 = self.well_name_to_grid(ref2.well_name)

        if grid1 is None or grid2 is None:
            return False

        row1, col1 = grid1
        row2, col2 = grid2

        # Calculate expected distance in grid units
        dx_grid = (col2 - col1) * self.config.well_spacing_x
        dy_grid = (row2 - row1) * self.config.well_spacing_y

        # Calculate measured distance in stage units
        dx_stage = ref2.measured_x - ref1.measured_x
        dy_stage = ref2.measured_y - ref1.measured_y

        # Compute scale and rotation
        expected_dist = np.sqrt(dx_grid**2 + dy_grid**2)
        measured_dist = np.sqrt(dx_stage**2 + dy_stage**2)

        if expected_dist > 0:
            scale = measured_dist / expected_dist
            self._scale_x = scale
            self._scale_y = scale

        # Compute rotation
        expected_angle = np.arctan2(dy_grid, dx_grid)
        measured_angle = np.arctan2(dy_stage, dx_stage)
        self._rotation = measured_angle - expected_angle

        # Compute origin (A1 position) by back-calculating from ref1
        # Grid position of ref1 in stage units (relative to A1)
        rel_x = col1 * self.config.well_spacing_x
        rel_y = row1 * self.config.well_spacing_y

        # Apply rotation
        cos_r = np.cos(self._rotation)
        sin_r = np.sin(self._rotation)
        rotated_x = rel_x * cos_r - rel_y * sin_r
        rotated_y = rel_x * sin_r + rel_y * cos_r

        # Scale and compute origin
        self._origin_x = ref1.measured_x - rotated_x * self._scale_x
        self._origin_y = ref1.measured_y - rotated_y * self._scale_y

        self._transform_computed = True
        print(f"Transform computed: origin=({self._origin_x}, {self._origin_y}), "
              f"scale=({self._scale_x:.4f}, {self._scale_y:.4f}), "
              f"rotation={np.degrees(self._rotation):.2f}°")

        return True

    def well_name_to_grid(self, well_name: str) -> Optional[Tuple[int, int]]:
        """Convert well name to grid coordinates (row, col).

        Args:
            well_name: Well name like "A1", "B12", "H2"

        Returns:
            (row_index, col_index) tuple, or None if invalid
        """
        try:
            row = well_name[0].upper()
            col = int(well_name[1:])

            row_idx = ord(row) - ord('A')
            col_idx = col - 1

            if 0 <= row_idx < self.config.num_rows and 0 <= col_idx < self.config.num_cols:
                return (row_idx, col_idx)
        except (ValueError, IndexError):
            pass
        return None

    def grid_to_well_name(self, row: int, col: int) -> str:
        """Convert grid coordinates to well name."""
        return f"{chr(ord('A') + row)}{col + 1}"

    def well_to_stage(self, well_name: str) -> Optional[Tuple[int, int]]:
        """Convert well name to stage coordinates.

        Args:
            well_name: Well name like "A1", "B12"

        Returns:
            (stage_x, stage_y) tuple, or None if invalid
        """
        grid = self.well_name_to_grid(well_name)
        if grid is None:
            return None

        row, col = grid
        return self.grid_to_stage(row, col)

    def grid_to_stage(self, row: int, col: int) -> Tuple[int, int]:
        """Convert grid coordinates to stage coordinates.

        Args:
            row: Row index (0-7 for A-H)
            col: Column index (0-11 for 1-12)

        Returns:
            (stage_x, stage_y) tuple
        """
        # Calculate position relative to A1 in grid units
        rel_x = col * self.config.well_spacing_x
        rel_y = row * self.config.well_spacing_y

        if self._transform_computed:
            # Apply rotation
            cos_r = np.cos(self._rotation)
            sin_r = np.sin(self._rotation)
            rotated_x = rel_x * cos_r - rel_y * sin_r
            rotated_y = rel_x * sin_r + rel_y * cos_r

            # Apply scale and origin
            stage_x = int(self._origin_x + rotated_x * self._scale_x)
            stage_y = int(self._origin_y + rotated_y * self._scale_y)
        else:
            # Use approximate positions without transform
            stage_x = int(self._origin_x + rel_x)
            stage_y = int(self._origin_y + rel_y)

        return (stage_x, stage_y)

    def stage_to_well(self, stage_x: int, stage_y: int) -> Optional[str]:
        """Find the nearest well to a stage position.

        Args:
            stage_x, stage_y: Stage coordinates

        Returns:
            Well name of nearest well, or None if too far from any well
        """
        min_dist = float('inf')
        nearest_well = None

        for row in range(self.config.num_rows):
            for col in range(self.config.num_cols):
                well_x, well_y = self.grid_to_stage(row, col)
                dist = np.sqrt((stage_x - well_x)**2 + (stage_y - well_y)**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_well = self.grid_to_well_name(row, col)

        # Only return if within reasonable distance of a well
        if min_dist < self.config.well_diameter:
            return nearest_well
        return None

    def get_label_position(self, well_name: str) -> Optional[Tuple[int, int]]:
        """Get the expected label position for a well.

        Labels are typically between wells, offset from well center.

        Args:
            well_name: Well name like "B12"

        Returns:
            (stage_x, stage_y) of expected label position
        """
        well_pos = self.well_to_stage(well_name)
        if well_pos is None:
            return None

        # Labels are offset from well center (between wells)
        label_x = well_pos[0] + self.config.label_offset_x
        label_y = well_pos[1] + self.config.label_offset_y

        return (label_x, label_y)

    def get_all_wells(self) -> List[str]:
        """Get list of all well names."""
        wells = []
        for row in range(self.config.num_rows):
            for col in range(self.config.num_cols):
                wells.append(self.grid_to_well_name(row, col))
        return wells


# ============================================================================
# Label Scan Configuration
# ============================================================================

@dataclass
class LabelScanConfig:
    """Configuration for reference label scanning."""

    # Search area around approximate position
    search_radius_x: int = 2000  # Search area in X
    search_radius_y: int = 2000  # Search area in Y

    # Image acquisition settings
    use_low_res: bool = True    # Use low resolution for faster scanning
    autofocus_enabled: bool = True  # Autofocus at each position

    # Grid overlap for stitching
    overlap_pct: float = 20.0   # 20% overlap between tiles

    # Number of FOVs to capture (for stitching multi-FOV labels)
    grid_cols: int = 2          # Number of columns in scan grid
    grid_rows: int = 2          # Number of rows in scan grid

    # Z-stack for focus bracketing (optional)
    z_stack_enabled: bool = False
    z_stack_range: float = 20.0
    z_stack_steps: int = 3

    @property
    def total_captures(self) -> int:
        """Total number of captures per label."""
        z_mult = self.z_stack_steps if self.z_stack_enabled else 1
        return self.grid_cols * self.grid_rows * z_mult


class LabelScanState(Enum):
    """State of label scanning operation."""
    IDLE = "idle"
    MOVING = "moving"
    FOCUSING = "focusing"
    CAPTURING = "capturing"
    STITCHING = "stitching"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Label Scanner
# ============================================================================

class LabelScanner:
    """Scanner for finding and capturing reference labels on well plates.

    Features:
    - Searches for etched labels at approximate positions
    - Multi-FOV capture and stitching for large labels
    - Autofocus at each label position
    - Records Z position from autofocus
    - Prepares images for future computer vision matching
    """

    def __init__(self, config: LabelScanConfig = None,
                 fov_width: int = 3000, fov_height: int = 2250):
        """Initialize label scanner.

        Args:
            config: Label scan configuration
            fov_width: Camera FOV width in stage units
            fov_height: Camera FOV height in stage units
        """
        self.config = config or LabelScanConfig()
        self.fov_width = fov_width
        self.fov_height = fov_height

        # Current scan state
        self.state = LabelScanState.IDLE
        self.current_label: Optional[LabelReference] = None
        self.scan_positions: List[Tuple[int, int]] = []
        self.current_position_idx: int = 0

        # Tile manager for stitching label images
        self.tile_manager = TileManager()
        self.tile_manager.fov_width = fov_width
        self.tile_manager.fov_height = fov_height
        self.tile_manager.position_threshold = 100  # Finer grid for labels

        # Results
        self.captured_labels: Dict[str, LabelScanResult] = {}

    def setup_label_scan(self, label_ref: LabelReference):
        """Set up scanning for a specific label.

        Args:
            label_ref: Label reference to scan
        """
        self.current_label = label_ref
        self.tile_manager.clear()

        # Calculate grid positions around the approximate label position
        self.scan_positions = self._generate_scan_positions(
            label_ref.approx_x, label_ref.approx_y
        )
        self.current_position_idx = 0
        self.state = LabelScanState.IDLE

        print(f"Label scan setup for {label_ref.well_name}: "
              f"{len(self.scan_positions)} positions")

    def _generate_scan_positions(self, center_x: int, center_y: int) -> List[Tuple[int, int]]:
        """Generate grid of scan positions around center point."""
        positions = []

        # Calculate step sizes with overlap
        overlap_factor = 1.0 - (self.config.overlap_pct / 100.0)
        step_x = int(self.fov_width * overlap_factor)
        step_y = int(self.fov_height * overlap_factor)

        # Calculate grid extent
        half_cols = self.config.grid_cols // 2
        half_rows = self.config.grid_rows // 2

        # Generate positions (snake pattern)
        for row in range(self.config.grid_rows):
            row_y = center_y + (row - half_rows) * step_y

            # Alternate direction for snake pattern
            cols = range(self.config.grid_cols)
            if row % 2 == 1:
                cols = reversed(cols)

            for col in cols:
                col_x = center_x + (col - half_cols) * step_x
                positions.append((col_x, row_y))

        return positions

    def get_next_position(self) -> Optional[Tuple[int, int]]:
        """Get the next position to scan.

        Returns:
            (x, y) position or None if scan complete
        """
        if self.current_position_idx >= len(self.scan_positions):
            return None
        return self.scan_positions[self.current_position_idx]

    def advance(self):
        """Advance to next position after capture."""
        self.current_position_idx += 1
        if self.current_position_idx >= len(self.scan_positions):
            self.state = LabelScanState.STITCHING

    def add_capture(self, x: int, y: int, z: float, image: np.ndarray):
        """Add a captured image to the label tiles.

        Args:
            x, y: Stage position
            z: Z position (from autofocus)
            image: Captured image
        """
        tile = self.tile_manager.add_tile(x, y, z, image, save_full_res=False)
        if tile and self.current_label:
            self.current_label.tiles.append(tile)

            # Update measured Z (use average or best focus)
            if self.current_label.measured_z is None:
                self.current_label.measured_z = z
            else:
                # Keep the Z with best focus
                if tile.quality and tile.quality.focus_score > 200:
                    self.current_label.measured_z = z

    def finalize_scan(self) -> Optional["LabelScanResult"]:
        """Finalize the scan and create stitched result.

        Returns:
            LabelScanResult with stitched image, or None if failed
        """
        if not self.current_label:
            return None

        # Calculate measured center position
        if self.tile_manager.tile_count > 0:
            bounds = self.tile_manager.get_bounds()
            measured_x = (bounds[0] + bounds[2]) // 2
            measured_y = (bounds[1] + bounds[3]) // 2
            self.current_label.measured_x = measured_x
            self.current_label.measured_y = measured_y

        # Create stitched preview
        bounds = self.tile_manager.get_bounds()
        if bounds != (0, 0, 0, 0):
            width = min(512, bounds[2] - bounds[0])
            height = min(512, bounds[3] - bounds[1])
            canvas = StitchCanvas(width, height)
            canvas.show_quality = False
            canvas.set_view(bounds[0], bounds[1], bounds[2], bounds[3])
            stitched = canvas.render(self.tile_manager)
        else:
            stitched = None

        result = LabelScanResult(
            well_name=self.current_label.well_name,
            measured_x=self.current_label.measured_x,
            measured_y=self.current_label.measured_y,
            measured_z=self.current_label.measured_z,
            stitched_image=stitched,
            tile_count=self.tile_manager.tile_count,
            bounds=bounds
        )

        self.captured_labels[self.current_label.well_name] = result
        self.current_label.scan_complete = True
        self.state = LabelScanState.COMPLETED

        print(f"Label scan complete for {self.current_label.well_name}: "
              f"position=({result.measured_x}, {result.measured_y}), "
              f"z={result.measured_z if result.measured_z else 'N/A'}")

        return result

    @property
    def progress(self) -> float:
        """Get scan progress as percentage."""
        if not self.scan_positions:
            return 0.0
        return (self.current_position_idx / len(self.scan_positions)) * 100

    @property
    def is_complete(self) -> bool:
        """Check if current scan is complete."""
        return self.state in (LabelScanState.COMPLETED, LabelScanState.FAILED)


@dataclass
class LabelScanResult:
    """Result of scanning a reference label."""
    well_name: str
    measured_x: Optional[int]
    measured_y: Optional[int]
    measured_z: Optional[float]
    stitched_image: Optional[np.ndarray]
    tile_count: int
    bounds: Tuple[int, int, int, int]

    def save_image(self, output_path: str) -> bool:
        """Save the stitched label image."""
        if self.stitched_image is None:
            return False
        try:
            from PIL import Image
            img_uint8 = (self.stitched_image[:, :, :3] * 255).astype(np.uint8)
            img = Image.fromarray(img_uint8)
            img.save(output_path)
            return True
        except Exception as e:
            print(f"Error saving label image: {e}")
            return False


# ============================================================================
# Plate Grid Scanner
# ============================================================================

@dataclass
class PlateGridScanConfig:
    """Configuration for scanning a grid of wells on a plate."""

    # Wells to scan (list of well names or "all")
    wells: List[str] = field(default_factory=list)

    # Scan parameters per well
    images_per_well: int = 1    # Number of images per well (1 = center only)
    z_stack_enabled: bool = False
    z_stack_range: float = 50.0
    z_stack_steps: int = 5

    # Movement optimization
    snake_pattern: bool = True
    autofocus_interval: int = 4  # Autofocus every N wells (0 = every well)

    # Image acquisition
    use_low_res: bool = False

    @classmethod
    def all_wells(cls) -> "PlateGridScanConfig":
        """Create config to scan all 96 wells."""
        wells = []
        for row in range(8):
            for col in range(12):
                wells.append(f"{chr(ord('A') + row)}{col + 1}")
        return cls(wells=wells)

    @classmethod
    def row(cls, row: str) -> "PlateGridScanConfig":
        """Create config to scan a single row."""
        wells = [f"{row.upper()}{col}" for col in range(1, 13)]
        return cls(wells=wells)

    @classmethod
    def column(cls, col: int) -> "PlateGridScanConfig":
        """Create config to scan a single column."""
        wells = [f"{chr(ord('A') + row)}{col}" for row in range(8)]
        return cls(wells=wells)


class PlateGridScanner:
    """Grid scanner specialized for well plates.

    Handles:
    - Well-based coordinate mapping
    - Optimized scan path for plate geometry
    - Per-well Z tracking
    - Integration with plate alignment
    """

    def __init__(self, plate: WellPlate, config: PlateGridScanConfig):
        """Initialize plate grid scanner.

        Args:
            plate: WellPlate with coordinate mapping
            config: Scan configuration
        """
        self.plate = plate
        self.config = config

        # Generate scan positions
        self.positions = self._generate_positions()
        self.current_index = 0
        self.state = ScanState.IDLE

        # Per-well results
        self.well_z_positions: Dict[str, float] = {}
        self.well_images: Dict[str, List[np.ndarray]] = {}

        # Progress tracking
        self.wells_scanned = 0
        self.start_time = 0.0

    def _generate_positions(self) -> List[Tuple[str, int, int]]:
        """Generate list of (well_name, x, y) positions to scan."""
        positions = []

        # Sort wells for optimal path
        wells = list(self.config.wells)

        if self.config.snake_pattern:
            # Sort by row, then alternate column direction
            wells_by_row = {}
            for well in wells:
                row = well[0]
                if row not in wells_by_row:
                    wells_by_row[row] = []
                wells_by_row[row].append(well)

            sorted_wells = []
            for i, row in enumerate(sorted(wells_by_row.keys())):
                row_wells = sorted(wells_by_row[row], key=lambda w: int(w[1:]))
                if i % 2 == 1:
                    row_wells = list(reversed(row_wells))
                sorted_wells.extend(row_wells)
            wells = sorted_wells

        # Convert to stage positions
        for well in wells:
            pos = self.plate.well_to_stage(well)
            if pos:
                positions.append((well, pos[0], pos[1]))

        return positions

    @property
    def total_positions(self) -> int:
        """Total number of positions to scan."""
        return len(self.positions)

    @property
    def progress(self) -> float:
        """Scan progress as percentage."""
        if self.total_positions == 0:
            return 100.0
        return (self.current_index / self.total_positions) * 100

    def start(self):
        """Start the scan."""
        self.state = ScanState.RUNNING
        self.start_time = time.time()

    def pause(self):
        """Pause the scan."""
        if self.state == ScanState.RUNNING:
            self.state = ScanState.PAUSED

    def cancel(self):
        """Cancel the scan."""
        self.state = ScanState.CANCELLED

    def get_next_position(self) -> Optional[Tuple[str, int, int]]:
        """Get next position (well_name, x, y) or None if complete."""
        if self.state != ScanState.RUNNING:
            return None

        if self.current_index >= len(self.positions):
            self.state = ScanState.COMPLETED
            return None

        return self.positions[self.current_index]

    def should_autofocus(self) -> bool:
        """Check if autofocus should be performed."""
        if self.config.autofocus_interval == 0:
            return True  # Always autofocus
        return self.current_index % self.config.autofocus_interval == 0

    def record_result(self, well_name: str, z: float, images: List[np.ndarray]):
        """Record scan result for a well."""
        self.well_z_positions[well_name] = z
        self.well_images[well_name] = images
        self.wells_scanned += 1
        self.current_index += 1

        if self.current_index >= len(self.positions):
            self.state = ScanState.COMPLETED


# ============================================================================
# Plate Scan Manager (High-level interface)
# ============================================================================

class PlateScanManager:
    """High-level manager for well plate scanning operations.

    Coordinates:
    - Reference label scanning for alignment
    - Plate coordinate transformation
    - Well grid scanning
    - Result aggregation
    """

    def __init__(self, fov_width: int = 3000, fov_height: int = 2250):
        """Initialize plate scan manager.

        Args:
            fov_width: Camera FOV width
            fov_height: Camera FOV height
        """
        self.fov_width = fov_width
        self.fov_height = fov_height

        # Initialize well plate
        self.plate = WellPlate()

        # Initialize label scanner
        self.label_scanner = LabelScanner(
            fov_width=fov_width,
            fov_height=fov_height
        )

        # Add default reference labels
        for name, ref in DEFAULT_LABEL_REFERENCES.items():
            self.plate.add_reference(ref)

        # Current operations
        self.current_operation: str = "idle"
        self.grid_scanner: Optional[PlateGridScanner] = None

    def add_reference_label(self, well_name: str, approx_x: int, approx_y: int):
        """Add a new reference label position.

        Args:
            well_name: Well name (e.g., "C4", "G7")
            approx_x, approx_y: Approximate stage position
        """
        ref = LabelReference.from_well_name(well_name, approx_x, approx_y)
        self.plate.add_reference(ref)
        print(f"Added reference label {well_name} at approx ({approx_x}, {approx_y})")

    def get_label_scan_config(self) -> LabelScanConfig:
        """Get the label scan configuration."""
        return self.label_scanner.config

    def start_label_scan(self, well_name: str) -> bool:
        """Start scanning a reference label.

        Args:
            well_name: Well name of label to scan

        Returns:
            True if scan started successfully
        """
        ref = self.plate.get_reference(well_name)
        if not ref:
            print(f"Reference label {well_name} not found")
            return False

        self.label_scanner.setup_label_scan(ref)
        self.current_operation = f"label_scan:{well_name}"
        return True

    def get_pending_labels(self) -> List[str]:
        """Get list of reference labels that haven't been scanned."""
        return [name for name, ref in self.plate.references.items()
                if not ref.scan_complete]

    def get_scanned_labels(self) -> List[str]:
        """Get list of reference labels that have been scanned."""
        return [name for name, ref in self.plate.references.items()
                if ref.scan_complete]

    def compute_plate_alignment(self) -> bool:
        """Compute plate alignment from scanned reference labels.

        Returns:
            True if alignment was computed successfully
        """
        return self.plate.compute_transform()

    def setup_well_scan(self, config: PlateGridScanConfig = None):
        """Set up scanning of wells.

        Args:
            config: Scan configuration (defaults to all wells)
        """
        if config is None:
            config = PlateGridScanConfig.all_wells()

        self.grid_scanner = PlateGridScanner(self.plate, config)
        self.current_operation = "well_scan"
        print(f"Well scan configured: {self.grid_scanner.total_positions} wells")

    def get_well_position(self, well_name: str) -> Optional[Tuple[int, int]]:
        """Get stage position for a well.

        Args:
            well_name: Well name (e.g., "A1", "H12")

        Returns:
            (x, y) stage position or None if invalid
        """
        return self.plate.well_to_stage(well_name)

    def export_label_images(self, output_dir: str):
        """Export all captured label images.

        Args:
            output_dir: Directory to save images
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for well_name, result in self.label_scanner.captured_labels.items():
            img_path = output_path / f"label_{well_name}.png"
            if result.save_image(str(img_path)):
                print(f"Saved {img_path}")

    def get_alignment_report(self) -> str:
        """Get a report of plate alignment status."""
        lines = ["Plate Alignment Report", "=" * 40]

        lines.append(f"\nReference Labels ({len(self.plate.references)}):")
        for name, ref in self.plate.references.items():
            status = "SCANNED" if ref.scan_complete else "PENDING"
            if ref.measured_x is not None:
                lines.append(f"  {name}: {status}")
                lines.append(f"    Approx: ({ref.approx_x}, {ref.approx_y})")
                lines.append(f"    Measured: ({ref.measured_x}, {ref.measured_y})")
                if ref.measured_z is not None:
                    lines.append(f"    Z: {ref.measured_z:.2f}")
            else:
                lines.append(f"  {name}: {status} at approx ({ref.approx_x}, {ref.approx_y})")

        if self.plate._transform_computed:
            lines.append(f"\nTransform Computed:")
            lines.append(f"  Origin: ({self.plate._origin_x:.0f}, {self.plate._origin_y:.0f})")
            lines.append(f"  Scale: ({self.plate._scale_x:.4f}, {self.plate._scale_y:.4f})")
            lines.append(f"  Rotation: {np.degrees(self.plate._rotation):.2f}°")
        else:
            lines.append("\nTransform: NOT COMPUTED (need 2+ scanned labels)")

        return "\n".join(lines)
