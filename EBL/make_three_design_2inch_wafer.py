from __future__ import annotations

import math
from pathlib import Path

import gdstk


OUT_DIR = Path(__file__).resolve().parent
OUTPUT_GDS = OUT_DIR / "three_ebl_designs_2inch_wafer.gds"

WAFER_DIAMETER_UM = 50_800.0
WAFER_RADIUS_UM = WAFER_DIAMETER_UM / 2
SITE_PITCH_UM = 5_000.0

WAFER_OUTLINE_LAYER = 100
WAFER_LABEL_LAYER = 101
WAFER_OUTLINE_WIDTH_UM = 10.0

DESIGNS = (
    (
        "DIE_FOUR_PARALLEL_WORK_AREAS",
        OUT_DIR / "four_parallel_work_areas.gds",
        "four_parallel_work_areas",
    ),
    (
        "DIE_FOUR_RADIAL_WORK_AREAS",
        OUT_DIR / "four_radial_work_areas.gds",
        "four_radial_work_areas",
    ),
    (
        "DIE_MLA_FOUR_DIRECTION_ELECTRODES",
        OUT_DIR / "mla_four_direction_electrodes.gds",
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


def cell_fits_wafer(cell: gdstk.Cell, origin: tuple[float, float]) -> bool:
    bbox = cell.bounding_box()
    if bbox is None:
        return True
    (xmin, ymin), (xmax, ymax) = bbox
    ox, oy = origin
    corners = (
        (ox + xmin, oy + ymin),
        (ox + xmin, oy + ymax),
        (ox + xmax, oy + ymin),
        (ox + xmax, oy + ymax),
    )
    return all(math.hypot(x, y) <= WAFER_RADIUS_UM for x, y in corners)


def add_label(cell: gdstk.Cell, text: str, origin: tuple[float, float]) -> None:
    x, y = origin
    label_polys = gdstk.text(
        text,
        220.0,
        (x - 1900.0, y - 3150.0),
        layer=WAFER_LABEL_LAYER,
    )
    cell.add(*label_polys)


def design_index_for_site(ix: int, iy: int) -> int:
    # This 3-coloring avoids long stripes and keeps each design near one-third of the wafer.
    return (ix + 2 * iy) % len(DESIGNS)


def build_wafer() -> dict[str, int]:
    imported = [(name, import_top_cell(path, name), label) for name, path, label in DESIGNS]

    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    lib.add(*(cell for _, cell, _ in imported))
    wafer = lib.new_cell("THREE_EBL_DESIGNS_2INCH_WAFER")

    grid_limit = math.ceil(WAFER_RADIUS_UM / SITE_PITCH_UM)
    counts = {name: 0 for name, _, _ in imported}
    for iy in range(-grid_limit, grid_limit + 1):
        for ix in range(-grid_limit, grid_limit + 1):
            origin = (ix * SITE_PITCH_UM, iy * SITE_PITCH_UM)
            design_index = design_index_for_site(ix, iy)
            name, cell, label = imported[design_index]
            if not cell_fits_wafer(cell, origin):
                continue
            wafer.add(gdstk.Reference(cell, origin=origin))
            add_label(wafer, label, origin)
            counts[name] += 1

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
    return counts


if __name__ == "__main__":
    counts = build_wafer()
    print(f"Wrote {OUTPUT_GDS}")
    print(f"Wafer diameter: {WAFER_DIAMETER_UM:g} um")
    print(f"Site pitch: {SITE_PITCH_UM:g} um")
    for name, count in counts.items():
        print(f"{name}: {count}")
    print(f"Placed total dies: {sum(counts.values())}")
