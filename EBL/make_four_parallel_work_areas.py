from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import gdstk

import make_four_radial_work_areas as base


OUT_DIR = Path(__file__).resolve().parent
GDS_PATH = OUT_DIR / "four_parallel_work_areas.gds"
PNG_PATH = OUT_DIR / "four_parallel_work_areas_schematic.png"

CELL_NAME = "FOUR_PARALLEL_WORK_AREAS"
CENTER_CORNER_CLEARANCE_UM = 0.5
PARALLEL_ROUTE_WIDTH_UM = 3.0
ROUTE_PULL_FACTOR = 0.1
ROUTE_TANGENT_BLEND = 0.5


def direction_angles_for_area(name: str) -> list[float]:
    return [0.0, 90.0, 180.0, 270.0]


def unit_vector(angle_deg: float) -> tuple[float, float]:
    theta = math.radians(angle_deg)
    return (math.cos(theta), math.sin(theta))


def add_vector(
    origin: tuple[float, float],
    direction: tuple[float, float],
    distance: float,
) -> tuple[float, float]:
    return (origin[0] + direction[0] * distance, origin[1] + direction[1] * distance)


def offset_point(
    origin: tuple[float, float],
    direction: tuple[float, float],
    direction_distance: float,
    normal: tuple[float, float],
    normal_distance: float,
) -> tuple[float, float]:
    return (
        origin[0] + direction[0] * direction_distance + normal[0] * normal_distance,
        origin[1] + direction[1] * direction_distance + normal[1] * normal_distance,
    )


def blended_unit_vector(a: tuple[float, float], b: tuple[float, float], blend: float) -> tuple[float, float]:
    x = (1 - blend) * a[0] + blend * b[0]
    y = (1 - blend) * a[1] + blend * b[1]
    length = math.hypot(x, y)
    return (x / length, y / length)


def add_parallel_area(
    cell: gdstk.Cell,
    name: str,
    center: tuple[float, float],
    x_gap: float,
    targets: list[tuple[float, float]],
) -> None:
    fine_half_pitch = x_gap / 2 + base.CENTER_ELECTRODE_WIDTH_UM / 2
    route_half_pitch = x_gap / 2 + PARALLEL_ROUTE_WIDTH_UM / 2
    fine_start = x_gap / 2 + base.CENTER_ELECTRODE_WIDTH_UM / 2 + CENTER_CORNER_CLEARANCE_UM
    route_start = fine_start + base.TAPER_LENGTH_UM

    electrodes: list[tuple[float, tuple[float, float], tuple[float, float]]] = []
    for direction_angle in direction_angles_for_area(name):
        direction = unit_vector(direction_angle)
        normal = unit_vector(direction_angle + 90)
        for side in (-1.0, 1.0):
            p0 = offset_point(center, direction, fine_start, normal, side * fine_half_pitch)
            p1 = offset_point(center, direction, route_start, normal, side * route_half_pitch)
            electrodes.append((direction_angle, p0, p1))

    electrodes.sort(key=lambda item: base.angle_to(center, item[1]))
    sorted_targets = sorted(targets, key=lambda target: base.angle_to(center, target))
    for (direction_angle, p0, p1), target in zip(electrodes, sorted_targets):
        target_angle = base.angle_to(center, target)
        route_distance = math.dist(p1, target)
        route_pull = min(base.SMOOTH_ROUTE_PULL_UM, route_distance * ROUTE_PULL_FACTOR)
        initial_direction = unit_vector(direction_angle)
        target_route_direction = (
            (target[0] - p1[0]) / route_distance,
            (target[1] - p1[1]) / route_distance,
        )
        route_direction = blended_unit_vector(initial_direction, target_route_direction, ROUTE_TANGENT_BLEND)
        target_direction = unit_vector(target_angle)
        control1 = add_vector(p1, route_direction, route_pull)
        control2 = add_vector(target, target_direction, -route_pull)

        path = gdstk.RobustPath(p0, base.CENTER_ELECTRODE_WIDTH_UM, layer=base.METAL_LAYER)
        path.segment(p1, width=(PARALLEL_ROUTE_WIDTH_UM, "smooth"))
        path.cubic([control1, control2, target], width=PARALLEL_ROUTE_WIDTH_UM)
        cell.add(path)

    cell.add(
        gdstk.ellipse(
            center,
            x_gap / 2,
            inner_radius=max(x_gap / 2 - 0.2, 0.05),
            tolerance=0.02,
            layer=base.GUIDE_LAYER,
        )
    )
    etch_outer_radius = (x_gap - 1.5) / 2
    etch_inner_radius = 1.2 / 2
    cell.add(gdstk.ellipse(center, etch_outer_radius, inner_radius=etch_inner_radius, tolerance=0.02, layer=base.ETCH_LAYER))
    label_angle = {"NW": 315.0, "NE": 225.0, "SE": 135.0, "SW": 45.0}[name]
    label_position = base.polar(center, 48.0, label_angle)
    base.add_text_polygons(cell, f"x={x_gap:g}", label_position, 18.0, base.LABEL_LAYER)


def build_layout() -> None:
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    top = lib.new_cell(CELL_NAME)
    base.add_frame(top)

    pad_centers = base.perimeter_pad_centers()
    for index, (x, y) in enumerate(pad_centers):
        half = base.PAD_SIZE_UM / 2
        top.add(gdstk.Polygon(base.rect_points(x - half, y - half, x + half, y + half), layer=base.METAL_LAYER))
        if y == base.PAD_TRACK_HALF_SPAN_UM:
            label_position = (x - 115, y + half + 18)
        elif x == base.PAD_TRACK_HALF_SPAN_UM:
            label_position = (x + half + 18, y - 90)
        elif y == -base.PAD_TRACK_HALF_SPAN_UM:
            label_position = (x - 115, y - half - 218)
        else:
            label_position = (x - half - 258, y - 90)
        base.add_text_polygons(top, f"{index:02d}", label_position, base.PAD_LABEL_SIZE_UM, base.LABEL_LAYER)

    for name, center, x_gap, pad_indices in base.area_definitions():
        add_parallel_area(top, name, center, x_gap, [pad_centers[index] for index in pad_indices])

    base.add_overlay_markers(top)
    base.add_text_polygons(top, "Yuanrong Li", (-340, 80), base.SIGNATURE_SIZE_UM, base.LABEL_LAYER)
    base.add_text_polygons(top, "260530", (-180, -20), base.SIGNATURE_SIZE_UM, base.LABEL_LAYER)
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
    guide = (78, 132, 176)
    grid = (231, 234, 240)
    font = ImageFont.truetype("arial.ttf", 28) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()
    title_font = ImageFont.truetype("arial.ttf", 42) if Path("C:/Windows/Fonts/arial.ttf").exists() else ImageFont.load_default()

    def px(x: float, y: float) -> tuple[int, int]:
        return (round(img_size / 2 + x * scale), round(img_size / 2 - y * scale))

    for tick in range(-2500, 2501, 250):
        draw.line([px(-2500, tick), px(2500, tick)], fill=grid)
        draw.line([px(tick, -2500), px(tick, 2500)], fill=grid)

    for polygon in top.polygons:
        if polygon.layer == base.METAL_LAYER:
            color = metal
        elif polygon.layer == base.GUIDE_LAYER:
            color = guide
        else:
            color = frame
        draw.polygon([px(x, y) for x, y in polygon.points], fill=color)

    draw.text((img_size / 2, 52), "Four parallel work areas draft", font=title_font, anchor="mm", fill=(24, 38, 68))
    for index, center in enumerate(base.perimeter_pad_centers()):
        x, y = px(*center)
        draw.text((x, y), f"P{index:02d}", font=font, anchor="mm", fill="white")

    img.save(PNG_PATH)


if __name__ == "__main__":
    build_layout()
    draw_schematic()
    print(f"Wrote {GDS_PATH}")
    print(f"Wrote {PNG_PATH}")
