from __future__ import annotations

import math
from pathlib import Path

import gdstk


OUT_DIR = Path(__file__).resolve().parent
SOURCE_GDS = OUT_DIR / "mla_four_direction_electrodes.gds"
OUTPUT_GDS = OUT_DIR / "mla_four_direction_electrodes_2inch_wafer.gds"

WAFER_DIAMETER_UM = 50_800.0
WAFER_RADIUS_UM = WAFER_DIAMETER_UM / 2
DIE_PITCH_UM = 5_000.0
DIE_HALF_UM = DIE_PITCH_UM / 2
WAFER_OUTLINE_LAYER = 100
WAFER_OUTLINE_WIDTH_UM = 10.0


def die_fits_wafer(cx: float, cy: float) -> bool:
    corners = (
        (cx - DIE_HALF_UM, cy - DIE_HALF_UM),
        (cx - DIE_HALF_UM, cy + DIE_HALF_UM),
        (cx + DIE_HALF_UM, cy - DIE_HALF_UM),
        (cx + DIE_HALF_UM, cy + DIE_HALF_UM),
    )
    return all(math.hypot(x, y) <= WAFER_RADIUS_UM for x, y in corners)


def build_wafer_array() -> int:
    source_lib = gdstk.read_gds(SOURCE_GDS)
    source_top = source_lib.top_level()[0]

    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    lib.add(source_top)
    wafer = lib.new_cell("MLA_2INCH_WAFER_ARRAY")

    grid_limit = math.ceil(WAFER_RADIUS_UM / DIE_PITCH_UM)
    count = 0
    for ix in range(-grid_limit, grid_limit + 1):
        for iy in range(-grid_limit, grid_limit + 1):
            x = ix * DIE_PITCH_UM
            y = iy * DIE_PITCH_UM
            if die_fits_wafer(x, y):
                wafer.add(gdstk.Reference(source_top, origin=(x, y)))
                count += 1

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
    return count


if __name__ == "__main__":
    die_count = build_wafer_array()
    print(f"Wrote {OUTPUT_GDS}")
    print(f"Placed {die_count} complete 5 mm x 5 mm dies")
