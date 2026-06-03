from __future__ import annotations

from pathlib import Path

import make_mla_layout as base


OUT_DIR = Path(__file__).resolve().parent


def build_variant() -> None:
    base.GDS_PATH = OUT_DIR / "mla_four_direction_electrodes_compact_center.gds"
    base.PNG_PATH = OUT_DIR / "mla_four_direction_electrodes_compact_center_schematic.png"

    base.PARAMS["ns_center_gaps_um_west_to_east"] = [14.0, 7.0, 7.0, 14.0]
    base.PARAMS["ew_to_ns_lateral_gap_um"] = 2.0
    base.PARAMS["ew_reference_electrodes"] = "middle"

    base.build_gds()
    base.draw_schematic()
    print(f"Wrote {base.GDS_PATH}")
    print(f"Wrote {base.PNG_PATH}")


if __name__ == "__main__":
    build_variant()
