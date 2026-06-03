from __future__ import annotations

import math
from pathlib import Path

import gdstk


OUT_DIR = Path(__file__).resolve().parent
OUTPUT_GDS = OUT_DIR / "mixed_three_designs_4inch_wafer.gds"

WAFER_DIAMETER_UM = 101_600.0
WAFER_RADIUS_UM = WAFER_DIAMETER_UM / 2
DIE_PITCH_UM = 5_000.0
DIE_HALF_UM = DIE_PITCH_UM / 2
WAFER_OUTLINE_LAYER = 100
WAFER_OUTLINE_WIDTH_UM = 10.0

DESIGNS = (
    ("DIE_MLA_STANDARD", OUT_DIR / "mla_four_direction_electrodes.gds"),
    ("DIE_MLA_COMPACT_CENTER", OUT_DIR / "mla_four_direction_electrodes_compact_center.gds"),
    ("DIE_RADIAL_WORK_AREAS", OUT_DIR / "four_radial_work_areas.gds"),
)


def die_fits_wafer(cx: float, cy: float) -> bool:
    corners = (
        (cx - DIE_HALF_UM, cy - DIE_HALF_UM),
        (cx - DIE_HALF_UM, cy + DIE_HALF_UM),
        (cx + DIE_HALF_UM, cy - DIE_HALF_UM),
        (cx + DIE_HALF_UM, cy + DIE_HALF_UM),
    )
    return all(math.hypot(x, y) <= WAFER_RADIUS_UM for x, y in corners)


def import_top_cell(path: Path, new_name: str) -> gdstk.Cell:
    source_lib = gdstk.read_gds(path)
    top = source_lib.top_level()[0]
    top.name = new_name
    return top


def build_array() -> dict[str, int]:
    cells = [import_top_cell(path, name) for name, path in DESIGNS]

    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    lib.add(*cells)
    wafer = lib.new_cell("MIXED_THREE_DESIGNS_4INCH_WAFER")

    grid_limit = math.ceil(WAFER_RADIUS_UM / DIE_PITCH_UM)
    sites: list[tuple[int, int]] = []
    for iy in range(-grid_limit, grid_limit + 1):
        for ix in range(-grid_limit, grid_limit + 1):
            x = ix * DIE_PITCH_UM
            y = iy * DIE_PITCH_UM
            if die_fits_wafer(x, y):
                sites.append((ix, iy))

    counts = {cell.name: 0 for cell in cells}
    for index, (ix, iy) in enumerate(sites):
        cell = cells[index % len(cells)]
        wafer.add(gdstk.Reference(cell, origin=(ix * DIE_PITCH_UM, iy * DIE_PITCH_UM)))
        counts[cell.name] += 1

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
    counts = build_array()
    print(f"Wrote {OUTPUT_GDS}")
    for name, count in counts.items():
        print(f"{name}: {count}")
    print(f"Placed total dies: {sum(counts.values())}")
