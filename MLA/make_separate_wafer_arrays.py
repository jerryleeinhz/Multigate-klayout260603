from __future__ import annotations

import math
from pathlib import Path

import gdstk


OUT_DIR = Path(__file__).resolve().parent
DIE_PITCH_UM = 5_000.0
DIE_HALF_UM = DIE_PITCH_UM / 2
WAFER_OUTLINE_LAYER = 100
WAFER_OUTLINE_WIDTH_UM = 10.0

DESIGNS = (
    ("four_radial_work_areas", OUT_DIR / "four_radial_work_areas.gds"),
    ("mla_four_direction_electrodes", OUT_DIR / "mla_four_direction_electrodes.gds"),
)

WAFERS = (
    ("2inch", 50_800.0),
    ("4inch", 101_600.0),
)


def die_fits_wafer(cx: float, cy: float, wafer_radius_um: float) -> bool:
    corners = (
        (cx - DIE_HALF_UM, cy - DIE_HALF_UM),
        (cx - DIE_HALF_UM, cy + DIE_HALF_UM),
        (cx + DIE_HALF_UM, cy - DIE_HALF_UM),
        (cx + DIE_HALF_UM, cy + DIE_HALF_UM),
    )
    return all(math.hypot(x, y) <= wafer_radius_um for x, y in corners)


def build_array(design_name: str, source_path: Path, wafer_name: str, wafer_diameter_um: float) -> tuple[Path, int]:
    source_lib = gdstk.read_gds(source_path)
    source_top = source_lib.top_level()[0]
    source_top.name = f"DIE_{design_name.upper()}"

    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    lib.add(source_top)
    wafer = lib.new_cell(f"{design_name.upper()}_{wafer_name.upper()}_WAFER")

    radius = wafer_diameter_um / 2
    grid_limit = math.ceil(radius / DIE_PITCH_UM)
    count = 0
    for ix in range(-grid_limit, grid_limit + 1):
        for iy in range(-grid_limit, grid_limit + 1):
            x = ix * DIE_PITCH_UM
            y = iy * DIE_PITCH_UM
            if die_fits_wafer(x, y, radius):
                wafer.add(gdstk.Reference(source_top, origin=(x, y)))
                count += 1

    wafer.add(
        gdstk.ellipse(
            (0, 0),
            radius,
            inner_radius=radius - WAFER_OUTLINE_WIDTH_UM,
            tolerance=0.25,
            layer=WAFER_OUTLINE_LAYER,
        )
    )

    output_path = OUT_DIR / f"{design_name}_{wafer_name}_wafer.gds"
    lib.write_gds(output_path)
    return output_path, count


if __name__ == "__main__":
    for design_name, source_path in DESIGNS:
        for wafer_name, wafer_diameter_um in WAFERS:
            output_path, die_count = build_array(design_name, source_path, wafer_name, wafer_diameter_um)
            print(f"Wrote {output_path}")
            print(f"Placed {die_count} complete dies")
