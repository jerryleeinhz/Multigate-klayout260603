from __future__ import annotations

from pathlib import Path

import gdstk


OUT_DIR = Path(__file__).resolve().parent
SOURCE_GDS = OUT_DIR / "mla_four_direction_electrodes.gds"
OUTPUT_GDS = OUT_DIR / "mla_four_direction_electrodes_direct_write.gds"

METAL_LAYER = 1
ETCH_LAYER = 40
CENTER_HALF_SIZE_UM = 50.0


def is_inside_center(points) -> bool:
    return all(
        -CENTER_HALF_SIZE_UM <= x <= CENTER_HALF_SIZE_UM
        and -CENTER_HALF_SIZE_UM <= y <= CENTER_HALF_SIZE_UM
        for x, y in points
    )


def export_direct_write() -> tuple[dict[int, int], int, int]:
    source_lib = gdstk.read_gds(SOURCE_GDS)
    source_top = source_lib.top_level()[0]

    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    clean = lib.new_cell("MLA_FOUR_DIRECTION_DIRECT_WRITE")

    counts: dict[int, int] = {}
    removed_polygons = 0
    for polygon in source_top.polygons:
        if polygon.layer not in {METAL_LAYER, ETCH_LAYER} and is_inside_center(polygon.points):
            removed_polygons += 1
            continue
        clean.add(polygon.copy())
        counts[polygon.layer] = counts.get(polygon.layer, 0) + 1

    removed_labels = 0
    for label in source_top.labels:
        x, y = label.origin
        if -CENTER_HALF_SIZE_UM <= x <= CENTER_HALF_SIZE_UM and -CENTER_HALF_SIZE_UM <= y <= CENTER_HALF_SIZE_UM:
            removed_labels += 1
            continue
        clean.add(label.copy())

    lib.write_gds(OUTPUT_GDS)
    return counts, removed_polygons, removed_labels


if __name__ == "__main__":
    layer_counts, removed_polygons, removed_labels = export_direct_write()
    print(f"Wrote {OUTPUT_GDS}")
    print(f"Kept layers: {sorted(layer_counts)}")
    print(f"Polygon counts: {layer_counts}")
    print(f"Removed center auxiliary polygons: {removed_polygons}")
    print(f"Removed center auxiliary labels: {removed_labels}")
