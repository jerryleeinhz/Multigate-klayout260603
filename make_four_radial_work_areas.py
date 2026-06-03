from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import gdstk


OUT_DIR = Path(__file__).resolve().parent
GDS_PATH = OUT_DIR / "four_radial_work_areas.gds"
PNG_PATH = OUT_DIR / "four_radial_work_areas_schematic.png"

METAL_LAYER = 1
FRAME_LAYER = 10
LABEL_LAYER = 11
GUIDE_LAYER = 20
MARKER_LAYER = 30
ETCH_LAYER = 40

FRAME_OUTER_UM = 5000.0
FRAME_WIDTH_UM = 10.0
PAD_SIZE_UM = 380.0
PAD_TRACK_HALF_SPAN_UM = 2050.0
PAD_CENTER_HALF_SPAN_UM = 1660.0
WORK_OFFSET_UM = 1150.0
TAPER_LENGTH_UM = 140.0
ESCAPE_LENGTH_UM = 360.0
ROUTE_WIDTH_UM = 8.0
PAD_LABEL_SIZE_UM = 200.0
SIGNATURE_SIZE_UM = 75.0


def rect_points(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def polar(origin: tuple[float, float], radius: float, angle_deg: float) -> tuple[float, float]:
    theta = math.radians(angle_deg)
    return (origin[0] + radius * math.cos(theta), origin[1] + radius * math.sin(theta))


def angle_to(origin: tuple[float, float], target: tuple[float, float]) -> float:
    return math.degrees(math.atan2(target[1] - origin[1], target[0] - origin[0])) % 360


def angle_delta(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def add_frame(cell: gdstk.Cell) -> None:
    outer = FRAME_OUTER_UM / 2
    inner = outer - FRAME_WIDTH_UM
    for points in (
        rect_points(-outer, inner, outer, outer),
        rect_points(-outer, -outer, outer, -inner),
        rect_points(-outer, -inner, -inner, inner),
        rect_points(inner, -inner, outer, inner),
    ):
        cell.add(gdstk.Polygon(points, layer=FRAME_LAYER))


def add_text_polygons(
    cell: gdstk.Cell,
    text: str,
    position: tuple[float, float],
    size: float,
    layer: int = LABEL_LAYER,
) -> None:
    for polygon in gdstk.text(text, size, position, layer=layer):
        cell.add(polygon)


def add_cross_marker(cell: gdstk.Cell, x: float, y: float, size: float, width: float) -> None:
    cell.add(gdstk.Polygon(rect_points(x - size / 2, y - width / 2, x + size / 2, y + width / 2), layer=MARKER_LAYER))
    cell.add(gdstk.Polygon(rect_points(x - width / 2, y - size / 2, x + width / 2, y + size / 2), layer=MARKER_LAYER))


def add_overlay_markers(cell: gdstk.Cell) -> None:
    for text, x, y, tx, ty in (
        ("A", -1500.0, -1500.0, -1640.0, -1650.0),
        ("B", -1500.0, 1500.0, -1640.0, 1540.0),
        ("C", 1500.0, 1500.0, 1540.0, 1540.0),
        ("D", 1500.0, -1500.0, 1540.0, -1650.0),
    ):
        add_cross_marker(cell, x, y, 120.0, 20.0)
        add_text_polygons(cell, text, (tx, ty), 75.0, MARKER_LAYER)

    add_cross_marker(cell, -32.0, 32.0, 42.0, 6.0)
    add_cross_marker(cell, 32.0, -32.0, 42.0, 6.0)

    square = 20.0
    pitch = 40.0
    for cx, cy in ((700.0, 700.0), (-700.0, 700.0), (-700.0, -700.0), (700.0, -700.0)):
        for ix in range(5):
            for iy in range(5):
                x = cx + (ix - 2) * pitch
                y = cy + (iy - 2) * pitch
                cell.add(gdstk.Polygon(rect_points(x - square / 2, y - square / 2, x + square / 2, y + square / 2), layer=MARKER_LAYER))


def perimeter_pad_centers() -> list[tuple[float, float]]:
    edge = PAD_TRACK_HALF_SPAN_UM
    spread = PAD_CENTER_HALF_SPAN_UM
    step = 2 * spread / 6
    axis_positions = [-spread + index * step for index in range(7)]

    centers: list[tuple[float, float]] = []
    centers.extend((x, edge) for x in axis_positions)
    centers.extend((edge, y) for y in reversed(axis_positions))
    centers.extend((x, -edge) for x in reversed(axis_positions))
    centers.extend((-edge, y) for y in axis_positions)
    return centers


def area_definitions() -> list[tuple[str, tuple[float, float], float, list[int]]]:
    return [
        ("N", (0, WORK_OFFSET_UM), 6.0, [27, 0, 1, 2, 3, 4, 5, 6]),
        ("E", (WORK_OFFSET_UM, 0), 8.0, [6, 7, 8, 9, 10, 11, 12, 13]),
        ("S", (0, -WORK_OFFSET_UM), 10.0, [13, 14, 15, 16, 17, 18, 19, 20]),
        ("W", (-WORK_OFFSET_UM, 0), 12.0, [20, 21, 22, 23, 24, 25, 26, 27]),
    ]


def spoke_angles_for_area(name: str) -> list[float]:
    return {
        "N": [270, 225, 180, 135, 90, 45, 0, 315],
        "E": [180, 135, 90, 45, 0, 315, 270, 225],
        "S": [90, 45, 0, 315, 270, 225, 180, 135],
        "W": [0, 315, 270, 225, 180, 135, 90, 45],
    }[name]


def add_radial_area(
    cell: gdstk.Cell,
    name: str,
    center: tuple[float, float],
    circle_diameter: float,
    targets: list[tuple[float, float]],
) -> None:
    circle_radius = circle_diameter / 2
    spoke_start = circle_radius
    spoke_end = circle_radius + TAPER_LENGTH_UM
    escape_end = circle_radius + ESCAPE_LENGTH_UM

    for angle, target in zip(spoke_angles_for_area(name), targets):
        p0 = polar(center, spoke_start, angle)
        p1 = polar(center, spoke_end, angle)
        p2 = polar(center, escape_end, angle)
        path = gdstk.RobustPath(p0, 1.0, layer=METAL_LAYER)
        path.segment(p1, width=(ROUTE_WIDTH_UM, "smooth"))
        control2 = (
            target[0] + (center[0] - target[0]) * 0.28,
            target[1] + (center[1] - target[1]) * 0.28,
        )
        path.cubic([p2, control2, target], width=ROUTE_WIDTH_UM)
        cell.add(path)
        corner_half = ROUTE_WIDTH_UM / 2
        for corner_x, corner_y in (p1, target):
            cell.add(
                gdstk.Polygon(
                    rect_points(
                        corner_x - corner_half,
                        corner_y - corner_half,
                        corner_x + corner_half,
                        corner_y + corner_half,
                    ),
                    layer=METAL_LAYER,
                )
            )

    cell.add(gdstk.ellipse(center, circle_radius, inner_radius=max(circle_radius - 0.2, 0.05), tolerance=0.02, layer=GUIDE_LAYER))
    etch_outer_radius = (circle_diameter - 1.5) / 2
    etch_inner_radius = 1.2 / 2
    cell.add(gdstk.ellipse(center, etch_outer_radius, inner_radius=etch_inner_radius, tolerance=0.02, layer=ETCH_LAYER))
    label_angle = {"N": 210.0, "E": 120.0, "S": 30.0, "W": -60.0}[name]
    label_position = polar(center, 48.0, label_angle)
    add_text_polygons(cell, f"x={circle_diameter:g}", label_position, 18.0, LABEL_LAYER)


def build_layout() -> None:
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    top = lib.new_cell("FOUR_RADIAL_WORK_AREAS")
    add_frame(top)

    pad_centers = perimeter_pad_centers()
    for index, (x, y) in enumerate(pad_centers):
        half = PAD_SIZE_UM / 2
        top.add(gdstk.Polygon(rect_points(x - half, y - half, x + half, y + half), layer=METAL_LAYER))
        if y == PAD_TRACK_HALF_SPAN_UM:
            label_position = (x - 115, y + half + 18)
        elif x == PAD_TRACK_HALF_SPAN_UM:
            label_position = (x + half + 18, y - 90)
        elif y == -PAD_TRACK_HALF_SPAN_UM:
            label_position = (x - 115, y - half - 218)
        else:
            label_position = (x - half - 258, y - 90)
        add_text_polygons(top, f"{index:02d}", label_position, PAD_LABEL_SIZE_UM, LABEL_LAYER)

    for name, center, diameter, pad_indices in area_definitions():
        add_radial_area(top, name, center, diameter, [pad_centers[index] for index in pad_indices])

    add_overlay_markers(top)
    add_text_polygons(top, "Yuanrong Li", (-340, 80), SIGNATURE_SIZE_UM, LABEL_LAYER)
    add_text_polygons(top, "260530", (-180, -20), SIGNATURE_SIZE_UM, LABEL_LAYER)
    lib.write_gds(GDS_PATH)


def draw_schematic() -> None:
    lib = gdstk.read_gds(GDS_PATH)
    top = lib.top_level()[0]
    img_size = 2600
    scale = 0.49
    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)
    metal = (55, 101, 184)
    frame = (220, 72, 54)
    grid = (231, 234, 240)
    font = ImageFont.truetype("arial.ttf", 28) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()
    title_font = ImageFont.truetype("arial.ttf", 42) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()

    def px(x: float, y: float) -> tuple[int, int]:
        return (round(img_size / 2 + x * scale), round(img_size / 2 - y * scale))

    for tick in range(-2500, 2501, 250):
        draw.line([px(-2500, tick), px(2500, tick)], fill=grid)
        draw.line([px(tick, -2500), px(tick, 2500)], fill=grid)

    for polygon in top.polygons:
        color = metal if polygon.layer == METAL_LAYER else frame
        draw.polygon([px(x, y) for x, y in polygon.points], fill=color)
    for path in top.paths:
        for polygon in path.to_polygons():
            draw.polygon([px(x, y) for x, y in polygon.points], fill=metal)

    draw.text((img_size / 2, 52), "Four radial work areas draft", font=title_font, anchor="mm", fill=(24, 38, 68))
    for index, center in enumerate(perimeter_pad_centers()):
        x, y = px(*center)
        draw.text((x, y), f"P{index:02d}", font=font, anchor="mm", fill="white")

    img.save(PNG_PATH)


if __name__ == "__main__":
    build_layout()
    draw_schematic()
    print(f"Wrote {GDS_PATH}")
    print(f"Wrote {PNG_PATH}")
