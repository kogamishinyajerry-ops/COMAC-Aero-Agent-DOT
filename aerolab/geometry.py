"""One parameter contract for analytic metrics, CAD and the thermal surrogate.

The reference is an original, dimension-based idealization of the older heat
sink tabulated in NASA/TM-20230011420, not recovered NASA CAD or final Mod II.
Runtime metrics/preview and checked-in preset exports need only the stdlib.
Fresh arbitrary STEP/STL generation and independent BRep checks need CadQuery.
All CAD coordinates are millimetres; metric outputs use explicit SI suffixes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, fields
from functools import lru_cache
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import struct
import tempfile
from typing import Any, Mapping

SOURCE_URL = "https://ntrs.nasa.gov/citations/20230011420"
GEOMETRY_SCHEMA = "aerolab-rectangular-fin-v1"
CAD_DIR = Path(__file__).resolve().parents[1] / "cad"
# Computational bounds, not manufacturing recommendations or validated ranges.
GEOMETRY_LIMITS = {
    "length_mm": (20.0, 1000.0), "width_mm": (20.0, 500.0),
    "fin_height_mm": (2.0, 150.0), "base_thickness_mm": (1.0, 30.0),
    "fin_thickness_mm": (0.2, 10.0), "fin_count": (2, 120),
}
MIN_GAP_MM = 0.25
ASSUMPTIONS = (
    "Uniform rectangular fins and a flat base replace unprovided contours, taper, holes and radii.",
    "Gap is derived from width; NASA's reported 3.14 mm reference gap is rounded.",
    "Density is an illustrative aluminum assumption, not a verified alloy specification.",
    "Heated area includes channel-facing fin sides and exposed base only; external sides, fin tips and ends are excluded.",
    "Hydraulic diameter assumes a separate adiabatic lid/duct closing each channel; that lid is not part of the exported solid or mass.",
    "No manufacturing tolerances, CFD mesh, experimental calibration or flight qualification are represented.",
)


@dataclass(frozen=True)
class Geometry:
    length_mm: float = 388.6
    width_mm: float = 179.5
    fin_height_mm: float = 41.0
    base_thickness_mm: float = 6.0
    fin_thickness_mm: float = 1.11
    fin_count: int = 43

    def __post_init__(self) -> None:
        for field in fields(self):
            name, value = field.name, getattr(self, field.name)
            try:
                finite = math.isfinite(value) if isinstance(value, (int, float)) else False
            except OverflowError:
                finite = False
            if isinstance(value, bool) or not finite:
                raise ValueError(f"{name} must be a finite number")
            if name == "fin_count" and int(value) != value:
                raise ValueError("fin_count must be an integer")
            low, high = GEOMETRY_LIMITS[name]
            if not low <= value <= high:
                raise ValueError(f"{name} must be between {low:g} and {high:g}")
            object.__setattr__(self, name, int(value) if name == "fin_count" else float(value))
        if self.gap_mm < MIN_GAP_MM:
            raise ValueError(f"Derived channel gap must be at least {MIN_GAP_MM} mm; fins must not overlap")

    @property
    def gap_mm(self) -> float:
        return (self.width_mm - self.fin_count * self.fin_thickness_mm) / (self.fin_count - 1)

    def to_dict(self) -> dict:
        return asdict(self)


GEOMETRY_PRESETS = {
    "reference": Geometry(),
    "light": Geometry(fin_count=31, fin_height_mm=32.0, base_thickness_mm=5.0),
    "dense": Geometry(fin_count=57),
}


def parse_geometry(params: Mapping[str, Any] | Geometry | None = None) -> Geometry:
    """Validate a partial mapping, filling omitted dimensions from the reference."""
    if params is None:
        return Geometry()
    if isinstance(params, Geometry):
        return params
    if not isinstance(params, Mapping):
        raise ValueError("geometry must be an object containing dimensional parameters")
    names = {f.name for f in fields(Geometry)}
    unknown = set(params) - names
    if unknown:
        raise ValueError(f"Unknown geometry parameter(s): {', '.join(sorted(map(str, unknown)))}")
    return Geometry(**params)


def geometry_fingerprint(params: Mapping | Geometry | None = None) -> str:
    payload = {"schema": GEOMETRY_SCHEMA, "parameters": asdict(parse_geometry(params))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def geometry_metrics(params: Mapping | Geometry | None = None, density_kg_m3: float = 2700.0) -> dict:
    """Exact rectangular-solid formulae; these are NOT independent BRep measurements."""
    p = parse_geometry(params)
    try:
        finite_density = math.isfinite(density_kg_m3) if isinstance(density_kg_m3, (int, float)) else False
    except OverflowError:
        finite_density = False
    if isinstance(density_kg_m3, bool) or not finite_density or density_kg_m3 <= 0:
        raise ValueError("density_kg_m3 must be finite and positive")
    length, width, height, base, thick = (p.length_mm, p.width_mm, p.fin_height_mm, p.base_thickness_mm, p.fin_thickness_mm)
    channels, gap = p.fin_count - 1, p.gap_mm
    volume = length * (width * base + p.fin_count * thick * height)
    fin_area = 2 * channels * height * length * 1e-6
    base_area = channels * gap * length * 1e-6
    flow_area = channels * gap * height * 1e-6
    wetted_perimeter = 2 * channels * (gap + height) * 1e-3
    heated_perimeter = channels * (gap + 2 * height) * 1e-3
    all_area = (2 * width * length + 2 * base * (width + length) + 2 * p.fin_count * height * (length + thick)) * 1e-6
    result = {
        "parameters": asdict(p), "fingerprint": geometry_fingerprint(p),
        "method": "analytic_rectangular_fin_geometry", "volume_mm3": volume,
        "volume_m3": volume * 1e-9, "mass_kg": volume * 1e-9 * density_kg_m3,
        "density_kg_m3": density_kg_m3, "gap_mm": gap, "gap_m": gap * 1e-3,
        "total_height_mm": height + base, "channel_count": channels,
        "flow_area_m2": flow_area, "channel_heated_area_m2": fin_area + base_area,
        "channel_base_area_m2": base_area, "channel_fin_area_m2": fin_area,
        "all_solid_surface_area_m2": all_area,
        "hydraulic_diameter_m": 4 * flow_area / wetted_perimeter,
        "wetted_perimeter_m": wetted_perimeter, "heated_perimeter_m": heated_perimeter,
        "base_footprint_area_m2": width * length * 1e-6,
        "bbox_mm": {"x": width, "y": length, "z": height + base},
        "source": {"url": SOURCE_URL, "location": "Table 2, printed p. 13", "classification": "source dimensions apply to reference preset only"},
        "assumptions": list(ASSUMPTIONS),
    }
    for key in ("length", "width", "fin_height", "base_thickness", "fin_thickness"):
        result[key + "_m"] = getattr(p, key + "_mm") * 1e-3
    return result


@lru_cache(maxsize=1)
def _load_kernel():
    try:
        import cadquery as cq
    except (ImportError, OSError) as exc:
        raise RuntimeError("Custom STEP/STL export requires optional CadQuery 2.7.0. Install with python -m pip install cadquery==2.7.0") from exc
    return cq


def kernel_status() -> dict:
    try:
        cq = _load_kernel()
        return {"available": True, "name": "CadQuery/OpenCascade", "version": cq.__version__, "preset_exports_available": (CAD_DIR / "manifest.json").is_file()}
    except RuntimeError as exc:
        return {"available": False, "name": "CadQuery/OpenCascade", "version": None, "preset_exports_available": (CAD_DIR / "manifest.json").is_file(), "detail": str(exc)}


def build_solid(params: Mapping | Geometry | None = None):
    """Return an actual fused OpenCascade BRep solid; requires CadQuery."""
    p, cq = parse_geometry(params), _load_kernel()
    solid = (cq.Workplane("XY")
             .box(p.width_mm, p.length_mm, p.base_thickness_mm, centered=(False, False, False))
             .faces(">Z").workplane(centerOption="ProjectedOrigin")
             .pushPoints([(i * (p.fin_thickness_mm + p.gap_mm) + p.fin_thickness_mm / 2, p.length_mm / 2) for i in range(p.fin_count)])
             .rect(p.fin_thickness_mm, p.length_mm).extrude(p.fin_height_mm).val())
    check = inspect_brep(solid, p)
    if not check["passed"]:
        raise RuntimeError(f"Generated BRep failed validation: {check}")
    return solid


def inspect_brep(solid, params: Mapping | Geometry | None = None, density_kg_m3: float = 2700.0) -> dict:
    """Measure the kernel solid independently and compare with analytic geometry."""
    p, metric = parse_geometry(params), geometry_metrics(params, density_kg_m3)
    box = solid.BoundingBox()
    measured = {"x": box.xlen, "y": box.ylen, "z": box.zlen}
    bbox_error = max(abs(measured[k] - metric["bbox_mm"][k]) for k in measured)
    volume, area = solid.Volume(), solid.Area()
    relative_error = abs(volume - metric["volume_mm3"]) / metric["volume_mm3"]
    surface_relative_error = abs(area * 1e-6 - metric["all_solid_surface_area_m2"]) / metric["all_solid_surface_area_m2"]
    vertices, edges, faces = len(solid.Vertices()), len(solid.Edges()), len(solid.Faces())
    euler = vertices - edges + faces
    valid, n_solids, shells = solid.isValid(), len(solid.Solids()), solid.Shells()
    closed = bool(shells) and all(shell.Closed() for shell in shells)
    passed = valid and n_solids == 1 and len(shells) == 1 and closed and euler == 2 and relative_error < 1e-9 and surface_relative_error < 1e-9 and bbox_error < 1e-7
    return {"passed": passed, "method": "independent_OpenCascade_BRep_measurement", "is_valid": valid,
            "solid_count": n_solids, "shell_count": len(shells), "closed_shells": closed,
            "volume_mm3": volume, "mass_kg": volume * 1e-9 * density_kg_m3,
            "surface_area_m2": area * 1e-6, "bbox_mm": measured,
            "vertices": vertices, "edges": edges, "faces": faces, "euler_characteristic": euler,
            "relative_volume_error": relative_error, "relative_surface_area_error": surface_relative_error,
            "max_bbox_error_mm": bbox_error}


def _cached_artifact(p: Geometry, kind: str) -> bytes | None:
    manifest_path = CAD_DIR / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest.get("presets", {}).values():
        if item["fingerprint"] == geometry_fingerprint(p):
            artifact = item["artifacts"][kind]
            data = gzip.decompress((CAD_DIR / artifact["file"]).read_bytes())
            if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
                raise RuntimeError("Stored CAD artifact checksum mismatch; regenerate the CAD evidence")
            return data
    return None


def cad_status(params: Mapping | Geometry | None = None) -> dict:
    """Trust only matching, checksum-checked committed validation evidence.

    Custom metrics remain analytic-only even if a kernel could export them.
    No expensive CAD import or build is performed by this status query.
    """
    p = parse_geometry(params)
    fingerprint = geometry_fingerprint(p)
    available = importlib.util.find_spec("cadquery") is not None
    status = {"verification": "analytic_only", "geometry_fingerprint": fingerprint,
              "step_available": available, "stl_available": available,
              "preset_id": None, "kernel_installed": available,
              "detail": "Analytic geometry only; no matching independently verified BRep artifact yet"}
    path = CAD_DIR / "manifest.json"
    if not path.is_file():
        return status
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for name, item in manifest.get("presets", {}).items():
        if item["fingerprint"] != fingerprint:
            continue
        # A stale/missing artifact may never be advertised as verified.
        try:
            if _cached_artifact(p, "step") is None or _cached_artifact(p, "stl") is None:
                return status
        except (OSError, ValueError, KeyError, RuntimeError):
            status["detail"] = "Stored CAD evidence is missing or fails its checksum"
            return status
        validation = item["validation"]
        if not all(validation[key]["passed"] for key in ("brep", "step_roundtrip", "stl")):
            return status
        status.update({"verification": "verified_brep", "step_available": True,
                       "stl_available": True, "preset_id": name,
                       "validation": validation,
                       "detail": "Matching generated BRep and STEP roundtrip measured independently; STL is closed and oriented"})
        return status
    return status


def generate_step(params: Mapping | Geometry | None = None, *, force_regenerate: bool = False) -> bytes:
    """Export editable STEP BRep. Bundled exact presets also work without CadQuery."""
    p = parse_geometry(params)
    cached = None if force_regenerate else _cached_artifact(p, "step")
    if cached is not None:
        return cached
    cq, solid = _load_kernel(), build_solid(p)
    with tempfile.TemporaryDirectory(prefix="aerolab-step-") as tmp:
        path = Path(tmp) / "heatsink.step"
        cq.exporters.export(solid, str(path))
        imported = cq.importers.importStep(str(path)).val()
        if not inspect_brep(imported, p)["passed"]:
            raise RuntimeError("STEP roundtrip validation failed")
        return path.read_bytes()


def generate_stl(params: Mapping | Geometry | None = None, *, force_regenerate: bool = False) -> bytes:
    """Export a closed surface mesh (STL has no native units; coordinates are mm)."""
    p = parse_geometry(params)
    cached = None if force_regenerate else _cached_artifact(p, "stl")
    if cached is not None:
        return cached
    cq, solid = _load_kernel(), build_solid(p)
    with tempfile.TemporaryDirectory(prefix="aerolab-stl-") as tmp:
        path = Path(tmp) / "heatsink.stl"
        cq.exporters.export(solid, str(path), tolerance=0.05, angularTolerance=0.1)
        data = path.read_bytes()
        if not inspect_stl(data, p)["passed"]:
            raise RuntimeError("STL watertight/volume validation failed")
        return data


def inspect_stl(data: bytes, params: Mapping | Geometry | None = None) -> dict:
    """Independent stdlib binary STL topology, orientation and volume checks.

    Weld identical float32 vertex coordinates. Every undirected edge must occur
    exactly twice, with opposite direction; triangles must form one component.
    """
    p, metric = parse_geometry(params), geometry_metrics(params)
    if len(data) < 84:
        raise ValueError("Not a binary STL file")
    count = struct.unpack_from("<I", data, 80)[0]
    if count == 0 or len(data) != 84 + 50 * count:
        raise ValueError("Invalid binary STL triangle count")
    vertex_ids, positions, triangles = {}, [], []
    edges, directions, adjacency = Counter(), Counter(), defaultdict(set)
    signed_volume = 0.0
    degenerate = 0
    for face in range(count):
        record = struct.unpack_from("<12fH", data, 84 + 50 * face)
        xyz = [tuple(record[i:i + 3]) for i in (3, 6, 9)]
        if not all(math.isfinite(v) for vertex in xyz for v in vertex):
            raise ValueError("Nonfinite STL vertex")
        ids = []
        for vertex in xyz:
            if vertex not in vertex_ids:
                vertex_ids[vertex] = len(positions)
                positions.append(vertex)
            ids.append(vertex_ids[vertex])
        a, b, c = xyz
        ab, ac = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        cross = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
        if len(set(ids)) < 3 or sum(x*x for x in cross) < 1e-16:
            degenerate += 1
        signed_volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2]) + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6
        for u, v in zip(ids, ids[1:] + ids[:1]):
            key = tuple(sorted((u, v)))
            edges[key] += 1
            directions[key] += 1 if u < v else -1
            adjacency[u].add(v)
            adjacency[v].add(u)
        triangles.append(ids)
    visited, stack = set(), [0]
    while stack:
        vertex = stack.pop()
        if vertex in visited:
            continue
        visited.add(vertex)
        stack.extend(adjacency[vertex] - visited)
    bbox = {axis: max(v[i] for v in positions) - min(v[i] for v in positions) for i, axis in enumerate("xyz")}
    watertight = all(n == 2 for n in edges.values())
    oriented = all(value == 0 for value in directions.values())
    euler = len(positions) - len(edges) + count
    relative_error = abs(signed_volume - metric["volume_mm3"]) / metric["volume_mm3"]
    bbox_error = max(abs(bbox[k] - metric["bbox_mm"][k]) for k in bbox)
    connected = len(visited) == len(positions)
    passed = watertight and oriented and connected and euler == 2 and degenerate == 0 and relative_error < 1e-5 and bbox_error < 1e-3
    return {"passed": passed, "method": "independent_binary_STL_edge_and_signed_volume_check", "triangles": count,
            "vertices": len(positions), "edges": len(edges), "euler_characteristic": euler,
            "watertight": watertight, "consistent_orientation": oriented, "connected": connected,
            "degenerate_triangles": degenerate, "volume_mm3": signed_volume, "bbox_mm": bbox,
            "relative_volume_error": relative_error, "max_bbox_error_mm": bbox_error}


def geometry_preview_svg(params: Mapping | Geometry | None = None) -> str:
    """Exact parametric orthographic section + axonometric preview; not a CFD image."""
    p = parse_geometry(params)
    fingerprint = geometry_fingerprint(p)
    # Consistent orthographic projection; visual lengths all derive from CAD dimensions.
    def project(x, y, z):
        return (1.8*x + 0.75*y, -0.36*x + 0.42*y - 2.2*z)
    corners = [project(x, y, z) for x in (0, p.width_mm) for y in (0, p.length_mm) for z in (0, p.fin_height_mm + p.base_thickness_mm)]
    xmin, xmax = min(x for x, y in corners), max(x for x, y in corners)
    ymin, ymax = min(y for x, y in corners), max(y for x, y in corners)
    scale = min(630 / (xmax-xmin), 300 / (ymax-ymin))
    def point(x, y, z):
        px, py = project(x, y, z)
        return f"{55+(px-xmin)*scale:.3f},{92+(py-ymin)*scale:.3f}"
    polygons = []
    def face(vertices, fill):
        polygons.append('<polygon points="' + ' '.join(point(*v) for v in vertices) + f'" fill="{fill}" stroke="#4c768a" stroke-width="0.55"/>')
    w, length, b, h, t = p.width_mm, p.length_mm, p.base_thickness_mm, p.fin_height_mm, p.fin_thickness_mm
    face([(0,0,b),(w,0,b),(w,length,b),(0,length,b)], "#b7d8e3")
    face([(0,length,0),(w,length,0),(w,length,b),(0,length,b)], "#6694a6")
    face([(0,0,0),(0,length,0),(0,length,b),(0,0,b)], "#86b1c1")
    # Far-to-near order so visible surfaces remain physically occluded.
    for i in reversed(range(p.fin_count)):
        x = i * (t + p.gap_mm)
        face([(x,0,b),(x,length,b),(x,length,b+h),(x,0,b+h)], "#88b3c4")
        face([(x,0,b+h),(x+t,0,b+h),(x+t,length,b+h),(x,length,b+h)], "#d0e8ed")
        face([(x,length,b),(x+t,length,b),(x+t,length,b+h),(x,length,b+h)], "#6694a6")
    section_scale = min(800 / w, 94 / (h+b))
    section_width = w * section_scale
    section_x, baseline = (920-section_width)/2, 540
    fins = ''.join(f'<rect class="fin-section" x="{section_x+i*(t+p.gap_mm)*section_scale:.4f}" y="{baseline-(h+b)*section_scale:.4f}" width="{t*section_scale:.4f}" height="{h*section_scale:.4f}"/>' for i in range(p.fin_count))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="640" viewBox="0 0 920 640" role="img" aria-labelledby="title desc" data-geometry-fingerprint="{fingerprint}">
<title id="title">Parametric {p.fin_count}-fin heat sink</title><desc id="desc">Dimension-driven preview of the same idealized solid exported as STEP. Length {length:g}, width {w:g}, fin height {h:g}, base {b:g}, fin thickness {t:g} millimetres. A duct lid is assumed for flow analysis and is not shown or included in solid mass.</desc>
<rect width="920" height="640" fill="#f5fafb" rx="18"/><g fill="#163a4c" font-family="system-ui,sans-serif">
<text x="32" y="37" font-size="22" font-weight="700">Dimension-linked CAD · {p.fin_count} fins</text><text x="32" y="63" font-size="13">Idealized reference geometry · millimetres · not a manufacturing drawing</text>
{''.join(polygons)}
<text x="700" y="130" font-size="16">L {length:g} mm</text><text x="700" y="160" font-size="16">W {w:g} mm</text><text x="700" y="190" font-size="16">Fin H {h:g} mm</text><text x="700" y="220" font-size="16">Base {b:g} mm</text><text x="700" y="250" font-size="16">Fin t {t:g} mm</text><text x="700" y="280" font-size="16">Gap {p.gap_mm:.4f} mm</text>
<text x="32" y="418" font-size="15" font-weight="600">End section · {p.fin_count-1} open channels · flow along L</text><g fill="#96becd" stroke="#335b6e" stroke-width="0.6">{fins}<rect x="{section_x:.4f}" y="{baseline-b*section_scale:.4f}" width="{section_width:.4f}" height="{b*section_scale:.4f}"/></g>
<text x="32" y="578" font-size="13">Gap = (W − N × t) / (N − 1) · heated surfaces: channel sides + exposed base</text><text x="32" y="603" font-size="12">Reference dimensions: NASA/TM-20230011420 Table 2. Uniform fins and flat base are assumptions.</text><text x="32" y="624" font-size="11" fill="#527181">Geometry ID: {fingerprint[:16]} · preview is parameter-derived, not a BRep-validation image</text>
</g></svg>'''
