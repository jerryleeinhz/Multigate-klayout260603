from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import gdstk


OUT_DIR = Path(__file__).resolve().parent
GDS_PATH = OUT_DIR / "mla_four_direction_electrodes.gds"
PNG_PATH = OUT_DIR / "mla_four_direction_electrodes_schematic.png"

METAL_LAYER = 1
MARK_LAYER = 10
LABEL_LAYER = 11
ETCH_LAYER = 40


PARAMS = {
    "line_width_um": 1.5,
    "line_gap_um": 1.5,
    "line_count_per_direction": 4,
    "ns_center_gaps_um_west_to_east": [6.0, 8.0, 10.0, 12.0],
    "ew_to_ns_lateral_gap_um": 1.5,
    "ew_reference_electrodes": "outer",
    "unchanged_center_square_um": 100.0,
    "step_length_um": 50.0,
    "step_count": 18,
    "step_transition_um": 2.0,
    "line_width_increment_per_step_um": 0.25,
    "line_gap_increment_per_step_um": 1.0,
    "straight_lead_length_um": 960.0,
    "fanout_end_um": 1300.0,
    "pad_size_um": 500.0,
    "pad_gap_um": 60.0,
    "text_size_um": 10.0,
    "pad_label_size_um": 200.0,
    "signature_size_um": 75.0,
    "coarse_marker_size_um": 120.0,
    "coarse_marker_width_um": 20.0,
    "small_marker_square_um": 20.0,
    "small_marker_pitch_um": 40.0,
    "frame_outer_size_um": 5000.0,
    "frame_line_width_um": 10.0,
}


def transform_point(p: tuple[float, float], rotation_deg: float) -> tuple[float, float]:
    x, y = p
    theta = math.radians(rotation_deg)
    c = math.cos(theta)
    s = math.sin(theta)
    return (x * c - y * s, x * s + y * c)


def transform_poly(points: list[tuple[float, float]], rotation_deg: float) -> list[tuple[float, float]]:
    return [transform_point(p, rotation_deg) for p in points]


def rect_points(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def add_polygon(cell: gdstk.Cell, points: list[tuple[float, float]], layer: int, rotation: float = 0) -> None:
    cell.add(gdstk.Polygon(transform_poly(points, rotation), layer=layer))


def add_cross_marker(cell: gdstk.Cell, x: float, y: float, size: float, rotation: float = 0) -> None:
    w = size / 5
    for pts in (
        rect_points(x - size / 2, y - w / 2, x + size / 2, y + w / 2),
        rect_points(x - w / 2, y - size / 2, x + w / 2, y + size / 2),
    ):
        add_polygon(cell, pts, MARK_LAYER, rotation)


def add_fixed_cross_marker(cell: gdstk.Cell, x: float, y: float, size: float, width: float, layer: int = MARK_LAYER) -> None:
    cell.add(gdstk.Polygon(rect_points(x - size / 2, y - width / 2, x + size / 2, y + width / 2), layer=layer))
    cell.add(gdstk.Polygon(rect_points(x - width / 2, y - size / 2, x + width / 2, y + size / 2), layer=layer))


def add_triangle_marker(cell: gdstk.Cell, x: float, y: float, size: float, rotation: float = 0) -> None:
    pts = [(x, y + size / 2), (x - size / 2, y - size / 2), (x + size / 2, y - size / 2)]
    add_polygon(cell, pts, MARK_LAYER, rotation)


def add_text_polygons(
    cell: gdstk.Cell,
    text: str,
    position: tuple[float, float],
    size: float | None = None,
    layer: int = LABEL_LAYER,
    rotation: float = 0,
) -> None:
    text_size = PARAMS["text_size_um"] if size is None else size
    for poly in gdstk.text(text, text_size, position, layer=layer):
        if rotation:
            poly.rotate(math.radians(rotation), (0, 0))
        cell.add(poly)


def electrode_offsets() -> list[float]:
    return offsets_for_dimensions(PARAMS["line_width_um"], PARAMS["line_gap_um"])


def offsets_for_dimensions(width: float, gap: float) -> list[float]:
    pitch = width + gap
    return [(-1.5 * pitch), (-0.5 * pitch), (0.5 * pitch), (1.5 * pitch)]


def step_dimensions(step_index: int) -> tuple[float, float, list[float]]:
    width = PARAMS["line_width_um"] + step_index * PARAMS["line_width_increment_per_step_um"]
    gap = PARAMS["line_gap_um"] + step_index * PARAMS["line_gap_increment_per_step_um"]
    return width, gap, offsets_for_dimensions(width, gap)


def ns_gap_by_global_x(global_x: float) -> float:
    xs = sorted(electrode_offsets())
    gaps = PARAMS["ns_center_gaps_um_west_to_east"]
    return dict(zip(xs, gaps))[global_x]


def center_start_for_arm(name: str, fine_y: float) -> float:
    width = PARAMS["line_width_um"]
    if name in ("E", "W"):
        offsets = electrode_offsets()
        if PARAMS["ew_reference_electrodes"] == "middle":
            reference_edge = min(abs(y) for y in offsets) + width / 2
        else:
            reference_edge = max(abs(y) for y in offsets) + width / 2
        return reference_edge + PARAMS["ew_to_ns_lateral_gap_um"]

    if name == "N":
        global_x = -fine_y
    elif name == "S":
        global_x = fine_y
    else:
        raise ValueError(f"Unknown arm name {name}")
    return ns_gap_by_global_x(global_x) / 2


def lead_polygons_for_electrode(name: str, electrode_index: int) -> tuple[list[list[tuple[float, float]]], float, float]:
    base_width = PARAMS["line_width_um"]
    base_y = electrode_offsets()[electrode_index]
    center_start = center_start_for_arm(name, base_y)
    center_edge = PARAMS["unchanged_center_square_um"] / 2
    step_length = PARAMS["step_length_um"]
    step_count = PARAMS["step_count"]
    transition = PARAMS["step_transition_um"]
    straight_end = PARAMS["straight_lead_length_um"]

    polygons = [rect_points(center_start, base_y - base_width / 2, center_edge, base_y + base_width / 2)]
    prev_x = center_edge
    prev_y = base_y
    prev_w = base_width

    for step in range(1, step_count + 1):
        step_start = center_edge + (step - 1) * step_length
        transition_end = step_start + transition
        step_end = center_edge + step * step_length
        next_w, _next_gap, next_offsets = step_dimensions(step)
        next_y = next_offsets[electrode_index]
        polygons.append(
            [
                (step_start, prev_y - prev_w / 2),
                (transition_end, next_y - next_w / 2),
                (transition_end, next_y + next_w / 2),
                (step_start, prev_y + prev_w / 2),
            ]
        )
        polygons.append(rect_points(transition_end, next_y - next_w / 2, step_end, next_y + next_w / 2))
        prev_x = step_end
        prev_y = next_y
        prev_w = next_w

    polygons.append(rect_points(prev_x, prev_y - prev_w / 2, straight_end, prev_y + prev_w / 2))
    return polygons, prev_y, prev_w


def add_arm(cell: gdstk.Cell, name: str, rotation: float) -> None:
    straight_end = PARAMS["straight_lead_length_um"]
    fanout_end = PARAMS["fanout_end_um"]
    pad_size = PARAMS["pad_size_um"]
    pad_gap = PARAMS["pad_gap_um"]
    pad_pitch = pad_size + pad_gap
    fine_ys = electrode_offsets()
    pad_ys = [(-1.5 * pad_pitch), (-0.5 * pad_pitch), (0.5 * pad_pitch), (1.5 * pad_pitch)]

    for idx, (fine_y, pad_y) in enumerate(zip(fine_ys, pad_ys), start=1):
        lead_polygons, final_y, final_width = lead_polygons_for_electrode(name, idx - 1)
        for lead_polygon in lead_polygons:
            add_polygon(cell, lead_polygon, METAL_LAYER, rotation)
        taper = [
            (straight_end, final_y - final_width / 2),
            (fanout_end, pad_y - pad_size / 2),
            (fanout_end, pad_y + pad_size / 2),
            (straight_end, final_y + final_width / 2),
        ]
        add_polygon(cell, taper, METAL_LAYER, rotation)
        add_polygon(
            cell,
            rect_points(fanout_end, pad_y - pad_size / 2, fanout_end + pad_size, pad_y + pad_size / 2),
            METAL_LAYER,
            rotation,
        )

        label_pos = transform_point((fanout_end + pad_size / 2 - 70, pad_y), rotation)
        cell.add(gdstk.Label(f"{name}{idx}", label_pos, anchor="o", rotation=math.radians(rotation), layer=LABEL_LAYER))

    add_cross_marker(cell, 95, 18, 18, rotation)
    add_triangle_marker(cell, 250, -30, 20, rotation)
    for text, pos in (("A", (95, 42)), ("B", (250, -58))):
        label_pos = transform_point(pos, rotation)
        cell.add(gdstk.Label(f"{name}-{text}", label_pos, anchor="o", rotation=math.radians(rotation), layer=LABEL_LAYER))


def add_gap_step_labels(cell: gdstk.Cell) -> None:
    center_edge = PARAMS["unchanged_center_square_um"] / 2
    step_length = PARAMS["step_length_um"]
    label_y = 42.0
    for rotation in (0, 90, 180, -90):
        for step in range(1, PARAMS["step_count"] + 1):
            _width, gap, _offsets = step_dimensions(step)
            x = center_edge + (step - 0.5) * step_length - 7
            add_text_polygons(cell, f"{gap:.1f}", (x, label_y), size=PARAMS["text_size_um"], layer=LABEL_LAYER, rotation=rotation - 90)


def add_pad_numbers(cell: gdstk.Cell) -> None:
    pad_size = PARAMS["pad_size_um"]
    pad_gap = PARAMS["pad_gap_um"]
    pad_pitch = pad_size + pad_gap
    fanout_end = PARAMS["fanout_end_um"]
    pad_ys = [(-1.5 * pad_pitch), (-0.5 * pad_pitch), (0.5 * pad_pitch), (1.5 * pad_pitch)]

    sequence: list[tuple[float, float]] = []
    sequence.extend((fanout_end + pad_size + 35, pad_y - 90) for pad_y in pad_ys)
    sequence.extend((-pad_y - 90, fanout_end + pad_size + 35) for pad_y in pad_ys)
    sequence.extend((-(fanout_end + pad_size + 325), -pad_y - 90) for pad_y in pad_ys)
    sequence.extend((pad_y - 90, -(fanout_end + pad_size + 325)) for pad_y in pad_ys)

    labels = [f"A{i}" for i in range(8)] + [f"B{i}" for i in range(8)]
    for label, (x, y) in zip(labels, sequence):
        add_text_polygons(cell, label, (x, y), size=PARAMS["pad_label_size_um"], layer=LABEL_LAYER)


def add_overlay_markers(cell: gdstk.Cell) -> None:
    marker_size = PARAMS["coarse_marker_size_um"]
    marker_width = PARAMS["coarse_marker_width_um"]
    corner_markers = [
        ("A", (-1500.0, -1500.0), (-1640.0, -1650.0)),
        ("B", (-1500.0, 1500.0), (-1640.0, 1540.0)),
        ("C", (1500.0, 1500.0), (1540.0, 1540.0)),
        ("D", (1500.0, -1500.0), (1540.0, -1650.0)),
    ]
    for label, (x, y), text_pos in corner_markers:
        add_fixed_cross_marker(cell, x, y, marker_size, marker_width)
        add_text_polygons(cell, label, text_pos, size=75.0, layer=LABEL_LAYER)

    add_fixed_cross_marker(cell, -32.0, 32.0, 42.0, 6.0)
    add_fixed_cross_marker(cell, 32.0, -32.0, 42.0, 6.0)

    square = PARAMS["small_marker_square_um"]
    pitch = PARAMS["small_marker_pitch_um"]
    for cx, cy in ((700.0, 700.0), (-700.0, 700.0), (-700.0, -700.0), (700.0, -700.0)):
        for ix in range(5):
            for iy in range(5):
                x = cx + (ix - 2) * pitch
                y = cy + (iy - 2) * pitch
                cell.add(gdstk.Polygon(rect_points(x - square / 2, y - square / 2, x + square / 2, y + square / 2), layer=MARK_LAYER))


def add_outer_frame(cell: gdstk.Cell) -> None:
    half_outer = PARAMS["frame_outer_size_um"] / 2
    half_inner = half_outer - PARAMS["frame_line_width_um"]
    cell.add(gdstk.Polygon(rect_points(-half_outer, half_inner, half_outer, half_outer), layer=MARK_LAYER))
    cell.add(gdstk.Polygon(rect_points(-half_outer, -half_outer, half_outer, -half_inner), layer=MARK_LAYER))
    cell.add(gdstk.Polygon(rect_points(-half_outer, -half_inner, -half_inner, half_inner), layer=MARK_LAYER))
    cell.add(gdstk.Polygon(rect_points(half_inner, -half_inner, half_outer, half_inner), layer=MARK_LAYER))


def add_capsule(
    cell: gdstk.Cell,
    center: tuple[float, float],
    total_length: float,
    width: float,
    rotation: float,
) -> None:
    x, y = center
    half_length = total_length / 2
    half_width = width / 2
    radius = min(half_length, half_width)
    points: list[tuple[float, float]] = []
    for cx, cy, start_angle in (
        (x + half_length - radius, y + half_width - radius, 0),
        (x - half_length + radius, y + half_width - radius, 90),
        (x - half_length + radius, y - half_width + radius, 180),
        (x + half_length - radius, y - half_width + radius, 270),
    ):
        for angle in range(start_angle, start_angle + 91, 15):
            theta = math.radians(angle)
            points.append((cx + radius * math.cos(theta), cy + radius * math.sin(theta)))
    polygon = gdstk.Polygon(points, layer=ETCH_LAYER)
    if rotation:
        polygon.rotate(math.radians(rotation), (0, 0))
    cell.add(polygon)


def add_etching_layer(cell: gdstk.Cell) -> None:
    center_edge = PARAMS["unchanged_center_square_um"] / 2
    step_length = PARAMS["step_length_um"]
    for rotation in (0, 90, 180, -90):
        for step in range(1, PARAMS["step_count"] + 1):
            _width, gap, offsets = step_dimensions(step)
            capsule_width = gap - 2.0
            gap_centers = [(offsets[index] + offsets[index + 1]) / 2 for index in range(3)]
            step_start = center_edge + (step - 1) * step_length
            for gap_center in gap_centers:
                add_capsule(cell, (step_start + 12, gap_center), 5.0, capsule_width, rotation)
                add_capsule(cell, (step_start + 34, gap_center), 10.0, capsule_width, rotation)

    cell.add(gdstk.ellipse((0, 0), 2.5, inner_radius=0.75, tolerance=0.02, layer=ETCH_LAYER))


def build_gds() -> None:
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    top = lib.new_cell("MLA_FOUR_DIRECTION_ELECTRODES")

    for name, rot in (("E", 0), ("N", 90), ("W", 180), ("S", -90)):
        add_arm(top, name, rot)

    for global_x, ns_gap in zip(sorted(electrode_offsets()), PARAMS["ns_center_gaps_um_west_to_east"]):
        x0 = global_x - PARAMS["line_width_um"] / 2
        x1 = global_x + PARAMS["line_width_um"] / 2
        add_polygon(top, rect_points(x0, -ns_gap / 2, x1, ns_gap / 2), MARK_LAYER, 0)
        top.add(gdstk.Label(f"{ns_gap:g}um", (global_x, 0), anchor="o", layer=LABEL_LAYER))

    ew_start = center_start_for_arm("E", electrode_offsets()[0])
    top.add(
        gdstk.Label(
            f"EW-NS lateral gap {PARAMS['ew_to_ns_lateral_gap_um']:g}um",
            (0, -18),
            anchor="o",
            layer=LABEL_LAYER,
        )
    )
    add_polygon(top, rect_points(-ew_start, -8, ew_start, 8), MARK_LAYER, 0)
    add_polygon(
        top,
        rect_points(
            -PARAMS["unchanged_center_square_um"] / 2,
            -PARAMS["unchanged_center_square_um"] / 2,
            PARAMS["unchanged_center_square_um"] / 2,
            PARAMS["unchanged_center_square_um"] / 2,
        ),
        MARK_LAYER,
        0,
    )

    add_gap_step_labels(top)
    add_pad_numbers(top)
    add_overlay_markers(top)
    add_outer_frame(top)
    add_etching_layer(top)
    add_text_polygons(top, "Yuanrong Li", (1240, -1580), size=PARAMS["signature_size_um"], layer=LABEL_LAYER)
    add_text_polygons(top, "260528", (1240, -1680), size=PARAMS["signature_size_um"], layer=LABEL_LAYER)

    lib.write_gds(GDS_PATH)


def world_to_px(x: float, y: float, scale: float, w: int, h: int) -> tuple[int, int]:
    return (round(w / 2 + x * scale), round(h / 2 - y * scale))


def draw_poly(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], scale: float, w: int, h: int, fill, outline=None) -> None:
    draw.polygon([world_to_px(x, y, scale, w, h) for x, y in pts], fill=fill, outline=outline)


def draw_schematic() -> None:
    img_w, img_h = 2400, 2400
    scale = 0.46
    img = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    metal = (64, 104, 184)
    marker = (220, 72, 54)
    outline = (28, 37, 65)
    grid = (226, 230, 238)

    for tick in range(-2500, 2501, 250):
        draw.line([world_to_px(-2500, tick, scale, img_w, img_h), world_to_px(2500, tick, scale, img_w, img_h)], fill=grid)
        draw.line([world_to_px(tick, -2500, scale, img_w, img_h), world_to_px(tick, 2500, scale, img_w, img_h)], fill=grid)

    polygons: list[tuple[list[tuple[float, float]], tuple[int, int, int]]] = []

    def collect_poly(points, layer, rotation=0):
        color = metal if layer == METAL_LAYER else marker
        polygons.append((transform_poly(points, rotation), color))

    width = PARAMS["line_width_um"]
    straight_end = PARAMS["straight_lead_length_um"]
    fanout_end = PARAMS["fanout_end_um"]
    pad_size = PARAMS["pad_size_um"]
    pad_gap = PARAMS["pad_gap_um"]
    pad_pitch = pad_size + pad_gap
    fine_ys = electrode_offsets()
    pad_ys = [(-1.5 * pad_pitch), (-0.5 * pad_pitch), (0.5 * pad_pitch), (1.5 * pad_pitch)]

    for name, rotation in (("E", 0), ("N", 90), ("W", 180), ("S", -90)):
        for idx, pad_y in enumerate(pad_ys):
            lead_polygons, final_y, final_width = lead_polygons_for_electrode(name, idx)
            for lead_polygon in lead_polygons:
                collect_poly(lead_polygon, METAL_LAYER, rotation)
            collect_poly(
                [
                    (straight_end, final_y - final_width / 2),
                    (fanout_end, pad_y - pad_size / 2),
                    (fanout_end, pad_y + pad_size / 2),
                    (straight_end, final_y + final_width / 2),
                ],
                METAL_LAYER,
                rotation,
            )
            collect_poly(rect_points(fanout_end, pad_y - pad_size / 2, fanout_end + pad_size, pad_y + pad_size / 2), METAL_LAYER, rotation)

    for pts, color in polygons:
        draw_poly(draw, pts, scale, img_w, img_h, fill=color, outline=outline)

    font = ImageFont.truetype("arial.ttf", 28) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()
    small_font = ImageFont.truetype("arial.ttf", 22) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()
    title_font = ImageFont.truetype("arial.ttf", 42) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()
    pad_font = ImageFont.truetype("arial.ttf", 110) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()
    signature_font = ImageFont.truetype("arial.ttf", 42) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()

    labels = []
    for name, rot in (("E", 0), ("N", 90), ("W", 180), ("S", -90)):
        for idx, pad_y in enumerate(pad_ys, start=1):
            labels.append((f"{name}{idx}", transform_point((fanout_end + pad_size / 2 - 70, pad_y), rot), font, "white"))
        labels.append((f"{name}-A", transform_point((95, 42), rot), small_font, marker))
        labels.append((f"{name}-B", transform_point((250, -58), rot), small_font, marker))

    pad_label_positions = []
    pad_label_positions.extend((fanout_end + pad_size + 35, pad_y - 90) for pad_y in pad_ys)
    pad_label_positions.extend((-pad_y - 90, fanout_end + pad_size + 35) for pad_y in pad_ys)
    pad_label_positions.extend((-(fanout_end + pad_size + 325), -pad_y - 90) for pad_y in pad_ys)
    pad_label_positions.extend((pad_y - 90, -(fanout_end + pad_size + 325)) for pad_y in pad_ys)
    for text, pos in zip([f"A{i}" for i in range(8)] + [f"B{i}" for i in range(8)], pad_label_positions):
        labels.append((text, pos, pad_font, marker))

    labels.extend(
        [
            ("4 electrodes / direction", (-410, 520), small_font, outline),
            ("1.5 um width, 1.5 um gap", (-410, 480), small_font, outline),
            ("Center 100 um x 100 um unchanged", (-410, 440), small_font, marker),
            ("18 widening steps, every 50 um", (-410, 400), small_font, marker),
            ("Final gap 19.5 um, width 6.0 um", (-410, 360), small_font, marker),
            ("500 um x 500 um wire-bond pads", (-410, 320), small_font, outline),
            ("Yuanrong Li", (1240, -1580), signature_font, outline),
            ("260528", (1240, -1680), signature_font, outline),
        ]
    )

    for text, (x, y), fnt, fill in labels:
        px, py = world_to_px(x, y, scale, img_w, img_h)
        draw.text((px, py), text, font=fnt, anchor="mm", fill=fill)

    for global_x, ns_gap in zip(sorted(electrode_offsets()), PARAMS["ns_center_gaps_um_west_to_east"]):
        box = [
            world_to_px(global_x - width / 2, ns_gap / 2, scale, img_w, img_h),
            world_to_px(global_x + width / 2, -ns_gap / 2, scale, img_w, img_h),
        ]
        draw.rectangle([box[0], box[1]], outline=marker, width=3)

    center_half = PARAMS["unchanged_center_square_um"] / 2
    center_box = [
        world_to_px(-center_half, center_half, scale, img_w, img_h),
        world_to_px(center_half, -center_half, scale, img_w, img_h),
    ]
    draw.rectangle([center_box[0], center_box[1]], outline=marker, width=2)

    def draw_cross_px(x: float, y: float, size: float, cross_width: float, color=marker, line_width=3) -> None:
        px, py = world_to_px(x, y, scale, img_w, img_h)
        half = size * scale / 2
        draw.line([(px - half, py), (px + half, py)], fill=color, width=line_width)
        draw.line([(px, py - half), (px, py + half)], fill=color, width=line_width)

    for text, (x, y), text_pos in (
        ("A", (-1500, -1500), (-1640, -1650)),
        ("B", (-1500, 1500), (-1640, 1540)),
        ("C", (1500, 1500), (1540, 1540)),
        ("D", (1500, -1500), (1540, -1650)),
    ):
        draw_cross_px(x, y, PARAMS["coarse_marker_size_um"], PARAMS["coarse_marker_width_um"], marker, 5)
        px, py = world_to_px(*text_pos, scale, img_w, img_h)
        draw.text((px, py), text, font=signature_font, anchor="mm", fill=marker)

    for x, y in ((-32, 32), (32, -32)):
        draw_cross_px(x, y, 42, 6, marker, 3)

    sq = PARAMS["small_marker_square_um"]
    pitch = PARAMS["small_marker_pitch_um"]
    for cx, cy in ((700, 700), (-700, 700), (-700, -700), (700, -700)):
        for ix in range(5):
            for iy in range(5):
                x = cx + (ix - 2) * pitch
                y = cy + (iy - 2) * pitch
                p0 = world_to_px(x - sq / 2, y + sq / 2, scale, img_w, img_h)
                p1 = world_to_px(x + sq / 2, y - sq / 2, scale, img_w, img_h)
                draw.rectangle([p0, p1], outline=marker, width=1)

    outer = PARAMS["frame_outer_size_um"] / 2
    inner = outer - PARAMS["frame_line_width_um"]
    for pts in (
        rect_points(-outer, inner, outer, outer),
        rect_points(-outer, -outer, outer, -inner),
        rect_points(-outer, -inner, -inner, inner),
        rect_points(inner, -inner, outer, inner),
    ):
        draw_poly(draw, pts, scale, img_w, img_h, fill=marker, outline=marker)

    for rot in (0, 90, 180, -90):
        cx, cy = world_to_px(*transform_point((95, 18), rot), scale, img_w, img_h)
        r = 10
        draw.line([(cx - r, cy), (cx + r, cy)], fill=marker, width=3)
        draw.line([(cx, cy - r), (cx, cy + r)], fill=marker, width=3)
        tri = [world_to_px(*p, scale, img_w, img_h) for p in transform_poly([(250, -20), (240, -40), (260, -40)], rot)]
        draw.polygon(tri, fill=marker)

    draw.text((img_w // 2, 70), "MLA four-direction electrode draft", font=title_font, anchor="mm", fill=outline)

    inset_w, inset_h = 720, 520
    inset = Image.new("RGB", (inset_w, inset_h), (250, 251, 253))
    inset_draw = ImageDraw.Draw(inset)
    inset_scale = 6.0

    def inset_px(x: float, y: float) -> tuple[int, int]:
        return (round(inset_w / 2 + x * inset_scale), round(inset_h / 2 - y * inset_scale))

    for tick in range(-60, 61, 10):
        inset_draw.line([inset_px(-80, tick), inset_px(80, tick)], fill=(225, 229, 236))
        inset_draw.line([inset_px(tick, -60), inset_px(tick, 60)], fill=(225, 229, 236))

    def draw_inset_poly(pts: list[tuple[float, float]], fill, outline_color=None) -> None:
        inset_draw.polygon([inset_px(x, y) for x, y in pts], fill=fill, outline=outline_color)

    for name, rotation in (("E", 0), ("N", 90), ("W", 180), ("S", -90)):
        for idx, fine_y in enumerate(fine_ys):
            center_start = center_start_for_arm(name, fine_y)
            pts = transform_poly(rect_points(center_start, fine_y - width / 2, 80, fine_y + width / 2), rotation)
            draw_inset_poly(pts, metal, outline)

    for global_x, ns_gap in zip(sorted(electrode_offsets()), PARAMS["ns_center_gaps_um_west_to_east"]):
        inset_draw.rectangle(
            [inset_px(global_x - width / 2, ns_gap / 2), inset_px(global_x + width / 2, -ns_gap / 2)],
            outline=marker,
            width=2,
        )
        inset_draw.text((inset_px(global_x, 0)), f"{ns_gap:g}", font=small_font, anchor="mm", fill=marker)
    for rot, name in (("0", "E"), ("90", "N"), ("180", "W"), ("-90", "S")):
        rotation = float(rot)
        for text, pos in ((f"{name}-A", (48, 16)), (f"{name}-B", (70, -14))):
            px, py = inset_px(*transform_point(pos, rotation))
            inset_draw.text((px, py), text, font=small_font, anchor="mm", fill=marker)

    ns_gap_text = "/".join(f"{gap:g}" for gap in PARAMS["ns_center_gaps_um_west_to_east"])
    inset_draw.text(
        (inset_w / 2, 26),
        f"Center zoom: N-S gaps {ns_gap_text} um, E-W side gap {PARAMS['ew_to_ns_lateral_gap_um']:g} um",
        font=small_font,
        anchor="mm",
        fill=outline,
    )
    inset_draw.rectangle([(0, 0), (inset_w - 1, inset_h - 1)], outline=(120, 128, 145), width=2)
    img.paste(inset, (80, img_h - inset_h - 80))

    step_w, step_h = 980, 320
    step = Image.new("RGB", (step_w, step_h), (250, 251, 253))
    step_draw = ImageDraw.Draw(step)
    step_scale = 0.9

    def step_px(x: float, y: float) -> tuple[int, int]:
        return (round(40 + (x - 40) * step_scale), round(step_h / 2 - y * step_scale))

    for tick in range(50, 1001, 50):
        step_draw.line([step_px(tick, -80), step_px(tick, 80)], fill=(225, 229, 236))
    for name, rotation in (("E", 0),):
        for idx in range(4):
            lead_polygons, _final_y, _final_width = lead_polygons_for_electrode(name, idx)
            for lead_polygon in lead_polygons[: 1 + 2 * PARAMS["step_count"]]:
                step_draw.polygon([step_px(x, y) for x, y in lead_polygon], fill=metal, outline=outline)

    for step_idx in range(1, PARAMS["step_count"] + 1):
        _w, gap, _offs = step_dimensions(step_idx)
        x = PARAMS["unchanged_center_square_um"] / 2 + (step_idx - 0.5) * PARAMS["step_length_um"]
        px, py = step_px(x, 52)
        step_draw.text((px, py), f"{gap:.1f}", font=small_font, anchor="mm", fill=marker)

    step_draw.line([step_px(50, -80), step_px(50, 80)], fill=marker, width=3)
    step_draw.text((step_w / 2, 24), "West/East/North/South lead widening after center square edge", font=small_font, anchor="mm", fill=outline)
    step_draw.text((step_w / 2, step_h - 24), "x=50 to 950 um: 18 steps, 50 um each, gap labels in um", font=small_font, anchor="mm", fill=marker)
    step_draw.rectangle([(0, 0), (step_w - 1, step_h - 1)], outline=(120, 128, 145), width=2)
    img.paste(step, (img_w - step_w - 80, img_h - step_h - 80))

    img.save(PNG_PATH)


if __name__ == "__main__":
    build_gds()
    draw_schematic()
    print(f"Wrote {GDS_PATH}")
    print(f"Wrote {PNG_PATH}")
