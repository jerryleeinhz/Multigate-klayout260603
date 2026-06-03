from __future__ import annotations

import math
from pathlib import Path

import gdstk


OUT_DIR = Path(__file__).resolve().parent
SOURCE_RADIAL = OUT_DIR / "four_radial_work_areas.gds"
SOURCE_MLA = OUT_DIR / "mla_four_direction_electrodes.gds"
OUTPUT_GDS = OUT_DIR / "mixed_radial_mla_4inch_wafer.gds"

WAFER_DIAMETER_UM = 101_600.0
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


def import_top_cell(path: Path, new_name: str) -> gdstk.Cell:
    source_lib = gdstk.read_gds(path)
    top = source_lib.top_level()[0]
    top.name = new_name
    return top


def build_mixed_wafer() -> tuple[int, int]:
    radial = import_top_cell(SOURCE_RADIAL, "DIE_RADIAL_WORK_AREAS")
    mla = import_top_cell(SOURCE_MLA, "DIE_MLA_FOUR_DIRECTION")

    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    lib.add(radial, mla)
    wafer = lib.new_cell("MIXED_RADIAL_MLA_4INCH_WAFER")

    grid_limit = math.ceil(WAFER_RADIUS_UM / DIE_PITCH_UM)
    radial_count = 0
    mla_count = 0
    for ix in range(-grid_limit, grid_limit + 1):
        for iy in range(-grid_limit, grid_limit + 1):
            x = ix * DIE_PITCH_UM
            y = iy * DIE_PITCH_UM
            if not die_fits_wafer(x, y):
                continue

            if (ix + iy) % 2 == 0:
                wafer.add(gdstk.Reference(radial, origin=(x, y)))
                radial_count += 1
            else:
                wafer.add(gdstk.Reference(mla, origin=(x, y)))
                mla_count += 1

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
    return radial_count, mla_count


if __name__ == "__main__":
    radial_count, mla_count = build_mixed_wafer()
    print(f"Wrote {OUTPUT_GDS}")
    print(f"Placed radial dies: {radial_count}")
    print(f"Placed MLA dies: {mla_count}")
    print(f"Placed total dies: {radial_count + mla_count}")
