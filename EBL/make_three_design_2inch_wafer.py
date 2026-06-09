from __future__ import annotations

import math
from pathlib import Path

import gdstk


OUT_DIR = Path(__file__).resolve().parent
OUTPUT_GDS = OUT_DIR / "three_ebl_designs_2inch_wafer.gds"

WAFER_DIAMETER_UM = 50_800.0
WAFER_RADIUS_UM = WAFER_DIAMETER_UM / 2
PLACEMENT_RADIUS_UM = WAFER_RADIUS_UM / 3

WAFER_OUTLINE_LAYER = 100
WAFER_LABEL_LAYER = 101
WAFER_OUTLINE_WIDTH_UM = 10.0

DESIGNS = (
    (
        "DIE_FOUR_PARALLEL_WORK_AREAS",
        OUT_DIR / "four_parallel_work_areas.gds",
        90.0,
        "four_parallel_work_areas",
    ),
    (
        "DIE_FOUR_RADIAL_WORK_AREAS",
        OUT_DIR / "four_radial_work_areas.gds",
        210.0,
        "four_radial_work_areas",
    ),
    (
        "DIE_MLA_FOUR_DIRECTION_ELECTRODES",
        OUT_DIR / "mla_four_direction_electrodes.gds",
        330.0,
        "mla_four_direction_electrodes",
    ),
)


def import_top_cell(path: Path, new_name: str) -> gdstk.Cell:
    source_lib = gdstk.read_gds(path)
    top_cells = source_lib.top_level()
    if len(top_cells) != 1:
        names = ", ".join(cell.name for cell in top_cells)
        raise ValueError(f"{path} should contain exactly one top cell, found: {names}")
    top = top_cells[0]
    top.name = new_name
    return top


def cell_half_diagonal(cell: gdstk.Cell) -> float:
    bbox = cell.bounding_box()
    if bbox is None:
        return 0.0
    (xmin, ymin), (xmax, ymax) = bbox
    return 0.5 * math.hypot(xmax - xmin, ymax - ymin)


def placement_origin(angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return (
        PLACEMENT_RADIUS_UM * math.cos(angle),
        PLACEMENT_RADIUS_UM * math.sin(angle),
    )


def add_label(cell: gdstk.Cell, text: str, origin: tuple[float, float]) -> None:
    x, y = origin
    label_polys = gdstk.text(
        text,
        220.0,
        (x - 1900.0, y - 3150.0),
        layer=WAFER_LABEL_LAYER,
    )
    cell.add(*label_polys)


def build_wafer() -> dict[str, tuple[float, float]]:
    imported = [(name, import_top_cell(path, name), angle, label) for name, path, angle, label in DESIGNS]

    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    lib.add(*(cell for _, cell, _, _ in imported))
    wafer = lib.new_cell("THREE_EBL_DESIGNS_2INCH_WAFER")

    placements: dict[str, tuple[float, float]] = {}
    for name, cell, angle, label in imported:
        origin = placement_origin(angle)
        if math.hypot(*origin) + cell_half_diagonal(cell) > WAFER_RADIUS_UM:
            raise ValueError(f"{name} does not fit inside the 2 inch wafer at {origin}")
        wafer.add(gdstk.Reference(cell, origin=origin))
        add_label(wafer, label, origin)
        placements[name] = origin

    wafer.add(
        gdstk.ellipse(
            (0, 0),
            WAFER_RADIUS_UM,
            inner_radius=WAFER_RADIUS_UM - WAFER_OUTLINE_WIDTH_UM,
            tolerance=0.25,
            layer=WAFER_OUTLINE_LAYER,
        )
    )
    lib.write_gds(OUTPUT_GDS)
    return placements


if __name__ == "__main__":
    placements = build_wafer()
    print(f"Wrote {OUTPUT_GDS}")
    print(f"Wafer diameter: {WAFER_DIAMETER_UM:g} um")
    print(f"Placement radius: {PLACEMENT_RADIUS_UM:g} um")
    for name, (x, y) in placements.items():
        print(f"{name}: ({x:.3f}, {y:.3f}) um")
