"""X-57 Mod II local nacelle reconstruction: one parameter contract, mesh and STEP.

This is a new, inference-based demonstrator, not released NASA production CAD.
The topology follows Borer/Bui/Smith (2023), figures 5–7. Only the historical
14-inch cruise-motor / 5-foot propeller sizes are external scale anchors;
all local dimensions, materials and airfoil coordinates are explicit assumptions.
Coordinates are millimetres: +X aft, +Y spanwise, +Z up. Metrics use SI units.
The older 43-fin heat-sink benchmark is intentionally completely independent.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, fields
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import zlib
from typing import Any, Mapping

SCHEMA = "aerolab-x57-modii-nacelle-v1"
# Capture once: in-memory geometry can never claim a newer on-disk definition.
GEOMETRY_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CAD_DIR = Path(__file__).resolve().parents[1] / "cad" / "nacelle"
STEP_CHUNK_MAX_BYTES = 250_000
STEP_COMPRESSED_MAX_BYTES = 64 * 1024 * 1024
STEP_UNCOMPRESSED_MAX_BYTES = 128 * 1024 * 1024
SOURCE_URL = "https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf"
SCALE_URL = "https://www.nasa.gov/centers-and-facilities/armstrong/x-57-maxwell/"
LIMITS = {
    "motor_diameter_mm": (320., 390.), "prop_diameter_mm": (1400., 1650.),
    "nacelle_length_mm": (1300., 1650.), "nacelle_width_mm": (490., 600.),
    "nacelle_height_mm": (470., 580.), "wing_span_mm": (1600., 2800.),
    "wing_chord_mm": (900., 1350.), "cmc_length_mm": (240., 340.),
    "cmc_width_mm": (160., 200.), "cmc_thickness_mm": (30., 52.),
    "cmc_tilt_deg": (35., 60.), "hv_fin_count": (12, 40),
    "hv_fin_height_mm": (15., 38.), "hv_fin_thickness_mm": (.8, 2.4),
    "motor_gap_mm": (3., 10.), "main_inlet_height_mm": (12., 40.),
    "motor_bypass_gap_mm": (15., 42.), "upper_inlet_height_mm": (15., 50.),
    "backplate_gap_mm": (10., 30.), "outlet_area_mm2": (12000., 36000.), "motor_exhaust_area_mm2": (4500., 16000.),
}
ASSUMPTIONS = [
    "Source topology is X-57 Mod II, 2023 thermal-analysis figures 5–7 (printed pp. 7–8), not the Mod IV aircraft exterior.",
    "NASA's 14-inch motor and 5-foot propeller are historical scale anchors listed on a Mod IV specifications page; they are not a dimensioned Mod II nacelle drawing.",
    "All dimensions beyond those anchors, airfoil section, propeller blade shape, shell thickness and material densities are inferred, editable reconstruction assumptions.",
    "The twin side-by-side tilted CMCs use inferred 24-fin HV arrays and separate LV backplates; the older NASA 43-fin benchmark is not used here.",
    "Local wing uses an illustrative NACA 2412 section; the NASA CFD figures omit the full wing and do not specify this section.",
    "Solid-volume mass uses illustrative homogeneous material densities; it is geometric proxy mass, not weighed aircraft hardware. Gross component volumes include the small declared attachment overlaps; installation-context wing is excluded.",
    "Air channels are reduced-order equivalent sections derived from the same dimensions; this is not a solved CFD volume mesh or a validated pressure-loss model.",
    "Named STEP solids are regenerated with CadQuery/OpenCascade. Browser fallback is closed procedural surface tessellation of the same parameterized construction.",
]
DENSITIES = {"aluminum": 2700., "copper_proxy": 6000., "magnet_proxy": 7400., "steel": 7850., "composite": 1550., "electronics_proxy": 1850.}

@dataclass(frozen=True)
class NacelleParams:
    motor_diameter_mm: float = 355.6
    prop_diameter_mm: float = 1524.
    nacelle_length_mm: float = 1470.
    nacelle_width_mm: float = 520.
    nacelle_height_mm: float = 490.
    wing_span_mm: float = 2200.
    wing_chord_mm: float = 1100.
    cmc_length_mm: float = 300.
    cmc_width_mm: float = 185.
    cmc_thickness_mm: float = 42.
    cmc_tilt_deg: float = 48.
    hv_fin_count: int = 24
    hv_fin_height_mm: float = 27.
    hv_fin_thickness_mm: float = 1.4
    motor_gap_mm: float = 6.
    main_inlet_height_mm: float = 24.
    motor_bypass_gap_mm: float = 28.
    upper_inlet_height_mm: float = 30.
    backplate_gap_mm: float = 18.
    outlet_area_mm2: float = 22000.
    motor_exhaust_area_mm2: float = 9000.

    def __post_init__(self):
        for f in fields(self):
            value = getattr(self, f.name)
            try:
                valid = not isinstance(value, bool) and isinstance(value, (float, int)) and math.isfinite(value)
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError(f"{f.name} must be a finite number")
            low, high = LIMITS[f.name]
            if not low <= value <= high:
                raise ValueError(f"{f.name} must be between {low:g} and {high:g}")
            if f.name == "hv_fin_count" and int(value) != value:
                raise ValueError("hv_fin_count must be an integer")
            object.__setattr__(self, f.name, int(value) if f.name == "hv_fin_count" else float(value))
        if self.hv_gap_mm < .7:
            raise ValueError("HV fin channel gap must be at least 0.7 mm")
        if self.motor_diameter_mm + 2 * self.motor_bypass_gap_mm + 14 > min(self.nacelle_width_mm, self.nacelle_height_mm):
            raise ValueError("Motor and bypass passage must fit inside nacelle cross-section")
        if self.motor_diameter_mm/2+self.motor_bypass_gap_mm+2 > min(.92*self.nacelle_width_mm/2,.96*self.nacelle_height_mm/2)-3:
            raise ValueError("Motor bypass guide must clear the local forward cowling section")
        if 2*self.cmc_width_mm+38 > self.nacelle_width_mm-45:
            raise ValueError("Side-by-side CMC cases must fit within nacelle width")

    @property
    def hv_gap_mm(self):
        return (self.cmc_width_mm - 2*6. - self.hv_fin_count*self.hv_fin_thickness_mm)/(self.hv_fin_count-1)

    def to_dict(self):
        return asdict(self)


def parse_nacelle(params: Mapping[str, Any] | NacelleParams | None = None) -> NacelleParams:
    if params is None: return NacelleParams()
    if isinstance(params, NacelleParams): return params
    if not isinstance(params, Mapping): raise ValueError("nacelle geometry must be a dimensional parameter object")
    unknown = set(params)-{f.name for f in fields(NacelleParams)}
    if unknown: raise ValueError("Unknown nacelle parameter(s): "+", ".join(sorted(map(str, unknown))))
    return NacelleParams(**params)


def nacelle_fingerprint(params=None):
    data = {"schema": SCHEMA, "construction_sha256": GEOMETRY_SOURCE_SHA256, "parameters": asdict(parse_nacelle(params))}
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",", ":"),allow_nan=False).encode()).hexdigest()


def provenance():
    return {"scope":"X-57 Mod II local-wing / cruise nacelle reconstruction", "original_NASA_CAD":False,
            "manufacturing_validated":False,"CFD_solved":False,"source_url":SOURCE_URL,
            "source_location":"Figures 5–7, printed pages 7–8", "scale_url":SCALE_URL,
            "source_topology":["outrunner rotor/stator and cooling slots","twin tilted aft CMCs","HV fins and LV backplates","upper ear inlets","internal baffles and struts","lower nacelle outlet"],
            "source_scale":{"motor_diameter_mm":355.6,"prop_diameter_mm":1524.},
            "all_other_dimensions":"inferred editable reconstruction", "assumptions":ASSUMPTIONS}


def nacelle_catalog():
    defaults=asdict(NacelleParams())
    labels={"motor_diameter_mm":"Motor diameter", "prop_diameter_mm":"Propeller diameter", "nacelle_length_mm":"Nacelle length", "nacelle_width_mm":"Nacelle width", "nacelle_height_mm":"Nacelle height", "cmc_tilt_deg":"CMC aft tilt", "hv_fin_count":"HV fin count per CMC", "hv_fin_height_mm":"HV fin height", "main_inlet_height_mm":"Outer motor-bypass inlet height", "motor_bypass_gap_mm":"Motor bypass clearance", "upper_inlet_height_mm":"LV fresh-air inlet height", "outlet_area_mm2":"Lower outlet area", "motor_exhaust_area_mm2":"Motor upper exhaust area"}
    return {"schema":SCHEMA,"default_id":"modii_reconstruction","defaults":defaults,"parameters":[{"key":k,"label":labels.get(k,k.replace('_',' ')),"default":defaults[k],"min":v[0],"max":v[1],"step":1 if k=="hv_fin_count" else (100 if k.endswith('mm2') else .1),"unit":"count" if k=="hv_fin_count" else ("deg" if k.endswith('deg') else ("mm²" if k.endswith('mm2') else "mm")),"classification":"historical_scale_anchor" if k in ("motor_diameter_mm","prop_diameter_mm") else "inferred"} for k,v in LIMITS.items()],"presets":[{"id":"modii_reconstruction","label":"Mod II reconstructed baseline","parameters":defaults}],"coordinate_system":{"units":"mm","x":"aft","y":"spanwise","z":"up"},"provenance":provenance(),"kernel_available":importlib.util.find_spec('cadquery') is not None}

# Each primitive owns closed rings. Mesh and BRep use the same rings; ring lofts
# are ruled, so changing a dimension regenerates both outputs without mesh assets.

def _loft(rings):
    return {"kind":"loft", "rings":rings}


def _box(dx,dy,dz,center=(0.,0.,0.)):
    x,y,z=center
    return _loft([[[x+s*dx/2,y-dy/2,z-dz/2],[x+s*dx/2,y+dy/2,z-dz/2],[x+s*dx/2,y+dy/2,z+dz/2],[x+s*dx/2,y-dy/2,z+dz/2]] for s in (-1,1)])


def _tube(x0,x1,ro,ri=0.,n=64,cy=0.,cz=0.,a0=0.,a1=2*math.pi):
    full=abs(a1-a0-2*math.pi)<1e-8
    outer=[[cy+ro*math.cos(a0+(a1-a0)*i/n),cz+ro*math.sin(a0+(a1-a0)*i/n)] for i in range(n+1 if not full else n)]
    if full and ri:
        # Split into two half annuli to avoid a hole in a section wire.
        return _tube(x0,x1,ro,ri,n//2,cy,cz,0,math.pi)+_tube(x0,x1,ro,ri,n//2,cy,cz,math.pi,2*math.pi)
    inner=([[cy+ri*math.cos(a0+(a1-a0)*i/n),cz+ri*math.sin(a0+(a1-a0)*i/n)] for i in range(n,-1,-1)] if ri else ([[cy,cz]] if not full else []))
    return [_loft([[[x,*yz] for yz in outer+inner] for x in (x0,x1)])]


def _shell(stations,a0,a1,thick=3.,n=32):
    rings=[]
    for x,ry,rz,zc in stations:
        outer=[[x,ry*math.cos(a0+(a1-a0)*i/n),zc+rz*math.sin(a0+(a1-a0)*i/n)] for i in range(n+1)]
        inner=[[x,(ry-thick)*math.cos(a0+(a1-a0)*i/n),zc+(rz-thick)*math.sin(a0+(a1-a0)*i/n)] for i in range(n,-1,-1)]
        rings.append(outer+inner)
    return _loft(rings)


def _transform(parts,angle=0.,offset=(0,0,0),axis='y'):
    c,s=math.cos(angle),math.sin(angle)
    out=[]
    for part in parts:
        rings=[]
        for ring in part['rings']:
            points=[]
            for x,y,z in ring:
                if axis=='y': q=(c*x+s*z,y,-s*x+c*z)
                else: q=(x,c*y-s*z,s*y+c*z)
                points.append([q[i]+offset[i] for i in range(3)])
            rings.append(points)
        out.append(_loft(rings))
    return out


def _rod(a,b,r,n=16):
    d=[b[i]-a[i] for i in range(3)]; length=math.sqrt(sum(v*v for v in d)); u=[v/length for v in d]
    helper=[0.,0.,1.] if abs(u[2])<.9 else [0.,1.,0.]
    v=[u[1]*helper[2]-u[2]*helper[1],u[2]*helper[0]-u[0]*helper[2],u[0]*helper[1]-u[1]*helper[0]]
    vl=math.sqrt(sum(t*t for t in v)); v=[t/vl for t in v]
    w=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
    return _loft([[[pt[j]+r*(v[j]*math.cos(i*2*math.pi/n)+w[j]*math.sin(i*2*math.pi/n)) for j in range(3)] for i in range(n)] for pt in (a,b)])


def _foil(chord,thickness=.12,n=44):
    # Cosine stations; close trailing edge and maintain finite tip thickness.
    points=[]
    for sign,indices in ((1,range(n+1)),(-1,range(n-1,0,-1))):
        for i in indices:
            x=(1-math.cos(math.pi*i/n))/2
            yt=5*thickness*(.2969*math.sqrt(x)-.126*x-.3516*x*x+.2843*x**3-.1036*x**4)
            yc=(.02/.4**2*(.8*x-x*x) if x<.4 else .02/.6**2*((1-.8)+.8*x-x*x))
            points.append((x*chord,(yc+sign*yt)*chord))
    return points


def _component(identifier,label,group,parts,color,opacity=1.,explode=(0,0,0),thermal_node=None,material='aluminum',source_note='Inferred dimensions; topology from Mod II figures 5–7'):
    return {"id":identifier,"label":label,"group":group,"thermal_node":thermal_node,"color":list(color),"opacity":opacity,"explode":list(explode),"material":material,"density_kg_m3":DENSITIES[material],"source":{"classification":"inferred_reconstruction","note":source_note,"url":SOURCE_URL},"parts":parts}


@lru_cache(maxsize=16)
def _construction(p):
    C=[]; add=C.append; L=p.nacelle_length_mm; W=p.nacelle_width_mm/2; H=p.nacelle_height_mm/2; R=p.motor_diameter_mm/2
    scale=L/1470.
    # Crescent-shell lofts leave actual paired upper openings and lower outlet.
    def station(x):
        t=x/scale
        nodes=[(-25,R+p.main_inlet_height_mm,R+p.main_inlet_height_mm,0),(130,W*.92,H*.96,0),(270,W,H,0),(430,W,H,-3),(520,W*.97,H*.99,-4),(680,W*.85,H*.84,0),(920,W*.58,H*.55,28),(1180,W*.31,H*.29,48),(L/scale-25,7,8,59)]
        for a,b in zip(nodes,nodes[1:]):
            if a[0] <= t <= b[0]:
                f=(t-a[0])/(b[0]-a[0]); return (x,*[a[i]+f*(b[i]-a[i]) for i in range(1,4)])
        return (x,*nodes[-1][1:])
    def segment(xs,a,b):return _shell([station(x*scale) for x in xs],a,b)
    vent_length=p.motor_exhaust_area_mm2/150.
    vent_end=258.;vent_start=vent_end-vent_length/scale
    vent_mean_ry=(station(vent_start*scale)[1]+station(vent_end*scale)[1])/2
    vent_half=math.asin(75/vent_mean_ry)
    cuts=sorted(set([-25,65,130,vent_start,vent_end,270,350,430,520,680]));up=[]
    for x0,x1 in zip(cuts,cuts[1:]):
        mid=(x0+x1)/2;blocked=[]
        if vent_start<mid<vent_end:blocked.append((math.pi/2-vent_half,math.pi/2+vent_half))
        if 270<mid<430:blocked.extend([(.88,1.34),(1.80,2.26)])
        intervals=[(0.,math.pi)]
        for lo,hi in blocked:
            intervals=[piece for a,b in intervals for piece in [(a,min(lo,b)),(max(hi,a),b)] if piece[1]-piece[0]>1e-6]
        for a,b in intervals:up.append(segment([x0,x1],a,b))
    add(_component('cowling_upper','Upper removable cowling with twin scoop openings','shell',up,(.79,.85,.89),.18,(0,0,240),material='composite'))
    # Width of physical vent follows the outlet area; length remains 160 mm.
    opening_angle=2*math.asin(p.outlet_area_mm2/(2*(160*scale)*(.91*W)))
    low=[segment([-25,65,130,270,430,520],math.pi,2*math.pi)]
    low += [segment([520,600,680],math.pi,1.5*math.pi-opening_angle/2),segment([520,600,680],1.5*math.pi+opening_angle/2,2*math.pi)]
    add(_component('cowling_lower','Lower cowling with open nacelle exhaust','shell',low,(.66,.75,.82),.18,(0,0,-220),material='composite'))
    tail=[segment([680,800,920,1060,1180,L/scale-25],0,math.pi),segment([680,800,920,1060,1180,L/scale-25],math.pi,2*math.pi)]
    add(_component('cowling_tail','Tapered aft fairing / dead-space shell','shell',tail,(.84,.88,.91),.3,(190,0,90),material='composite'))
    # Local host wing deliberately remains local; no Mod IV distributed motors.
    wing=[]
    for side in (-1,1):
        rings=[]
        for y in (0.,side*p.wing_span_mm/2):
            sweep=abs(y)*.035; chord=p.wing_chord_mm*(1-.06*abs(y)/(p.wing_span_mm/2))
            rings.append([[635*scale+sweep+x,y,64+z+abs(y)*.025] for x,z in _foil(chord)])
        wing.append(_loft(rings))
    add(_component('local_wing','Local host-wing section, illustrative airfoil','wing',wing,(.83,.88,.92),.8,(0,0,0),material='composite',source_note='Illustrative NACA 2412 local host wing; original wing section is not supplied by cited nacelle figures'))
    spinner_stations=[(-275,3,3,0),(-245,48,48,0),(-205,80,80,0),(-150,100,100,0)]
    spinner=[_shell(spinner_stations,0,math.pi,2),_shell(spinner_stations,math.pi,2*math.pi,2)]
    # Three true open root slots in the spinner skirt; blades do not pass through
    # a fictional filled nose. The material arcs between slots remain closed.
    for i in range(3):
        a=math.pi/2+i*2*math.pi/3+.48;b=math.pi/2+(i+1)*2*math.pi/3-.48
        spinner.append(_shell([(-150,100,100,0),(-80,106,106,0),(-25,105,105,0)],a,b,2,20))
    add(_component('propeller_spinner','Hollow streamlined spinner with blade-root slots','propeller',spinner,(.92,.94,.96),1,(-110,0,0),material='composite'))
    add(_component('propeller_hub','Three-blade hub','propeller',_tube(-110,-56,98,22,64),(.23,.29,.34),1,(-80,0,0),material='steel'))
    for blade in range(3):
        rings=[]
        for r,chord,twist,sweep in [(85,65,42,0),(160,130,34,10),(320,155,24,20),(520,122,17,35),(p.prop_diameter_mm/2-28,74,11,49),(p.prop_diameter_mm/2,8,9,54)]:
            t=math.radians(twist); points=[]
            for u,v in _foil(chord,.16,20):
                u-=chord*.46
                points.append([-83+u*math.sin(t)+v*math.cos(t),u*math.cos(t)-v*math.sin(t)+sweep,r])
            rings.append(points)
        parts=_transform([_loft(rings)],blade*2*math.pi/3,axis='x')
        add(_component(f'propeller_blade_{blade+1}',f'Twisted cruise propeller blade {blade+1}','propeller',parts,(.17,.22,.28),1,(-90,0,0),material='composite',source_note='Three-blade visual reconstruction with inferred chord and twist; historical 5-foot diameter anchor'))
    add(_component('motor_shaft','Motor shaft','motor',_tube(-130,250,22,0,64),(.35,.39,.43),1,(-35,0,0),material='steel'))
    rotor=_tube(5,196,R,R-8)+_tube(184,196,92,22)
    for i in range(6):rotor+=_tube(184,196,R-8,92,3,a0=i*math.pi/3-.055,a1=i*math.pi/3+.055)
    add(_component('motor_rotor','Outrunner outer rotor / rear cup','motor',rotor,(.31,.37,.43),.6,(0,0,75)))
    add(_component('motor_magnet','Rotor magnet annulus','motor',_tube(24,177,R-8,R-18),(.51,.31,.59),1,(0,0,65),'motor_magnet','magnet_proxy'))
    stator_r=R-18-p.motor_gap_mm
    wind=[];teeth=[]
    for i in range(24):
        a=i*2*math.pi/24
        wind+=_tube(32,165,stator_r-8,96.6,4,a0=a+.018,a1=a+2*math.pi/24-.025)
        teeth+=_tube(27,171,stator_r,stator_r-7.6,3,a0=a+.012,a1=a+2*math.pi/24-.012)
    add(_component('motor_winding','Segmented stator windings / cooling slots','motor',wind,(.87,.39,.13),1,(-10,0,-30),'motor_winding','copper_proxy'))
    add(_component('motor_stator','Stator teeth / internal support','motor',teeth+_tube(27,171,96,68),(.27,.31,.34),1,(-10,0,-45),material='steel'))
    add(_component('motor_front_bearing','Front bearing carrier','motor',_tube(4,27,68,22),(.54,.60,.64),1,(-20,0,0),material='steel'))
    mount=_tube(201,214,157,145)+_tube(201,214,75,55)
    for i in range(4):mount+=_tube(201,214,145,75,3,a0=i*math.pi/2-.06,a1=i*math.pi/2+.06)
    add(_component('motor_rear_mount','Ventilated motor rear mounting flange','structure',mount,(.48,.56,.61),1,(40,0,0)))
    # Motor bypass shroud follows actual radial clearance knob.
    guide_front=R+min(p.motor_bypass_gap_mm,p.main_inlet_height_mm-3)+2
    guide_aft=R+p.motor_bypass_gap_mm+2
    guide_stations=[(18,guide_front,guide_front,0),(130,guide_aft,guide_aft,0),(188,guide_aft,guide_aft,0)]
    guide=[_shell(guide_stations,0,math.pi,2),_shell(guide_stations,math.pi,2*math.pi,2)]
    add(_component('motor_bypass_shroud','Tapered motor bypass annular guide','duct',guide,(.18,.53,.65),.27,(0,45,0)))
    inletR=R+p.main_inlet_height_mm
    add(_component('main_inlet_lip','Annular main inlet lip','duct',_tube(-35,-25,inletR+3,inletR),(.11,.57,.70),1,(-35,0,0)))
    # Angled controller pair: their local +z side is the LV/backplate side.
    tilt=math.radians(p.cmc_tilt_deg); cmc_x=455*scale; sep=p.cmc_width_mm/2+14
    for side,sy in [('left',-sep),('right',sep)]:
        origin=(cmc_x,sy,16)
        tr=lambda parts:_transform(parts,tilt,origin)
        sign=-1 if side=='left' else 1
        explode=(20,sign*170,20)
        length,width,thick=p.cmc_length_mm,p.cmc_width_mm,p.cmc_thickness_mm
        # Four case edge rails surround a hollow electronics envelope.
        rails=[_box(length,width,3,(0,0,-thick/2+1.5)),_box(length,4,thick-3,(0,-width/2+2,1.5)),_box(length,4,thick-3,(0,width/2-2,1.5)),_box(4,width-8,thick-3,(-length/2+2,0,1.5)),_box(4,width-8,thick-3,(length/2-2,0,1.5))]
        add(_component(f'cmc_{side}_case',f'{side.title()} CMC enclosure','cmc',tr(rails),(.30,.39,.44),.65,explode))
        # Base is contiguous with each fin; each fin is separately addressable in STEP.
        base_z=-thick/2-3
        hv=[_box(length,width,6,(0,0,base_z))]
        fin0=-width/2+6+p.hv_fin_thickness_mm/2
        for i in range(p.hv_fin_count):
            fy=fin0+i*(p.hv_fin_thickness_mm+p.hv_gap_mm)
            hv.append(_box(length,p.hv_fin_thickness_mm,p.hv_fin_height_mm,(0,fy,base_z-3-p.hv_fin_height_mm/2)))
        add(_component(f'cmc_{side}_hv',f'{side.title()} CMC HV finned heat sink','cmc',tr(hv),(.25,.60,.65),1,(explode[0]-60,explode[1],-65),f'cmc_{side}_hv'))
        lv_z=thick/2+2
        add(_component(f'cmc_{side}_lv',f'{side.title()} CMC LV backplate','cmc',tr([_box(length,width,4,(0,0,lv_z))]),(.41,.61,.77),1,(explode[0]+60,explode[1],75),f'cmc_{side}_lv'))
        for name,px,py,dx,dy in [('cpu',-45,-34,54,46),('acdc',65,20,72,60)]:
            add(_component(f'cmc_{side}_{name}',f'{side.title()} LV {name.upper()} thermal proxy','cmc',tr([_box(dx,dy,10,(px,py,thick/2-7))]),(.69,.37,.60) if name=='cpu' else (.62,.54,.26),1,(explode[0]+90,explode[1],110),f'cmc_{side}_{name}','electronics_proxy',source_note='Explicit lumped electronics proxy; package shape and placement are not source dimensions'))
        lid_z=thick/2+4+p.backplate_gap_mm+1
        lid=[_box(length-74,width-14,2,(-37,0,lid_z))]
        for edge in (-1,1):lid.append(_box(length-74,2,p.backplate_gap_mm,(-37,edge*(width/2-6),thick/2+4+p.backplate_gap_mm/2)))
        add(_component(f'cmc_{side}_lv_duct',f'{side.title()} LV backplate cooling channel lid','duct',tr(lid),(.31,.61,.72),.3,(explode[0]+100,explode[1],115)))
        # Three cable connectors on LV side, recognizable from source Fig. 5.
        for j in range(3):
            connector=_tube(-7,7,15,6,24)
            connector=_transform(connector,math.pi/2,(length/2-36,-width/2+34+j*(width-68)/2,thick/2+11))
            add(_component(f'cmc_{side}_connector_{j+1}',f'{side.title()} CMC connector {j+1}','cmc',tr(connector),(.16,.19,.22),1,explode))
        # HV channel side baffles and rear support rails.
        for edge in (-1,1):
            parts=tr([_box(length+14,3,p.hv_fin_height_mm+12,(0,edge*(width/2+4),-thick/2-8-p.hv_fin_height_mm/2))])
            add(_component(f'cmc_{side}_baffle_{edge:+d}',f'{side.title()} HV cooling side baffle','baffle',parts,(.59,.65,.68),.7,(0,sign*210,-35)))
        # Smooth duct walls: open section at both ends, not a filled airflow box.
        duct=[]
        scoop_z=H*.91
        h=p.upper_inlet_height_mm; w=74.
        for a0,a1 in [(0,math.pi),(math.pi,2*math.pi)]:
            rings=[]
            endpoint_local=(-length/2,0,thick/2+4+p.backplate_gap_mm/2)
            ex=cmc_x+math.cos(tilt)*endpoint_local[0]+math.sin(tilt)*endpoint_local[2]
            ez=16-math.sin(tilt)*endpoint_local[0]+math.cos(tilt)*endpoint_local[2]
            for j,(x,z,rz) in enumerate([(275*scale,scoop_z+h*.5,h*.5+4),(300*scale,scoop_z+h*.48,h*.5+4),(345*scale,scoop_z-8,h*.5+3),(ex,ez,p.backplate_gap_mm/2)]):
                slant=tilt if j==3 else 0.
                outer=[[x+math.sin(slant)*rz*math.sin(a0+(a1-a0)*i/16),sy+(w/2+3)*math.cos(a0+(a1-a0)*i/16),z+math.cos(slant)*rz*math.sin(a0+(a1-a0)*i/16)] for i in range(17)]
                inner=[[x+math.sin(slant)*(rz-3)*math.sin(a0+(a1-a0)*i/16),sy+(w/2)*math.cos(a0+(a1-a0)*i/16),z+math.cos(slant)*(rz-3)*math.sin(a0+(a1-a0)*i/16)] for i in range(16,-1,-1)]
                rings.append(outer+inner)
            duct.append(_loft(rings))
        add(_component(f'lv_inlet_{side}',f'{side.title()} upper ear inlet / LV fresh-air duct','duct',duct,(.20,.58,.74),.9,(0,sign*85,160)))
    # Tubular engine mount is routed outside both CMC envelopes, inside skin.
    for side in (-1,1):
        for z in (-1,1):
            route=[(211,side*142,z*61),(300*scale,side*223,z*65),(560*scale,side*223,z*65),(650*scale,side*185,65)]
            add(_component(f'mount_strut_{side:+d}_{z:+d}','Motor-to-wing routed mounting tube','structure',[_rod(a,b,6) for a,b in zip(route,route[1:])],(.43,.48,.52),1,(0,side*50,z*60),material='steel'))
        for z in (-1,1):
            a=(290*scale,side*216,z*70);b=(590*scale,side*216,z*70)
            add(_component(f'cmc_frame_{side:+d}_{z:+d}','CMC cradle longitudinal rail','structure',[_rod(a,b,5)],(.49,.55,.59),1,(0,side*60,z*40)))
    for name,x in [('front',290*scale),('rear',590*scale)]:
        route=[(x,-216,-70),(x,0,-185),(x,216,-70)]
        add(_component(f'cmc_frame_cross_{name}','Lower V-shaped CMC cradle crossmember','structure',[_rod(a,b,5) for a,b in zip(route,route[1:])],(.49,.55,.59),1,(0,0,-60)))
    # Four explicit CMC case-to-cradle attachment brackets close the load path.
    for side,sign in [('left',-1),('right',1)]:
        for name,z in [('upper',70.),('lower',-70.)]:
            u=(16-z)/math.sin(tilt);x=cmc_x+math.cos(tilt)*u
            add(_component(f'cmc_{side}_mount_{name}',f'{side.title()} CMC {name} mounting bracket','structure',[_rod((x,sign*(p.cmc_width_mm+12),z),(x,sign*216,z),4)],(.52,.58,.62),1,(0,sign*100,0)))
    # External top-center louvered CM exhaust, source p.8. Actual opening
    # in the upper cowling is 150 mm wide by area/150 longitudinally.
    eh=p.motor_exhaust_area_mm2/150.
    hood=[]
    zvent=H*.983
    for i in range(4):
        xx=vent_start*scale+(i+.5)*eh/4
        hood.append(_transform([_box(eh/5,145,2)],math.radians(-18),(xx,0,zvent+3))[0])
    add(_component('motor_upper_exhaust','External top-center motor exhaust louvers','duct',hood,(.21,.54,.59),.9,(0,0,85)))
    # Baffle between fresh LV duct and motor-heated lower/HV stream.
    for side in (-1,1):
        add(_component(f'flow_separator_{side:+d}','Motor / CMC stream separator','baffle',[_box(80,3,70,(280*scale,side*205,0))],(.58,.64,.67),.6,(0,side*100,0)))
    return C


def _triangulate_ring(ring):
    """Ear clipping of a planar convex/concave section, including half-annuli."""
    normal=[0.,0.,0.]
    for a,b in zip(ring,ring[1:]+ring[:1]):
        normal[0]+=(a[1]-b[1])*(a[2]+b[2]);normal[1]+=(a[2]-b[2])*(a[0]+b[0]);normal[2]+=(a[0]-b[0])*(a[1]+b[1])
    drop=max(range(3),key=lambda j:abs(normal[j]));axes=[j for j in range(3) if j!=drop]
    p=[(v[axes[0]],v[axes[1]]) for v in ring]
    cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]));sgn=1 if area>0 else -1
    idx=list(range(len(p)));result=[]
    while len(idx)>3:
        found=False
        for j,i in enumerate(idx):
            a,b,c=idx[j-1],i,idx[(j+1)%len(idx)]
            if sgn*cross(p[a],p[b],p[c]) <= 1e-8:continue
            inside=False
            for k in idx:
                if k in (a,b,c):continue
                if min(sgn*cross(p[a],p[b],p[k]),sgn*cross(p[b],p[c],p[k]),sgn*cross(p[c],p[a],p[k]))>1e-8:
                    inside=True;break
            if inside:continue
            result.append((a,b,c));idx.pop(j);found=True;break
        if not found:
            raise ValueError("Non-simple or degenerate geometry section")
    result.append(tuple(idx));return result


def _mesh_part(part):
    rings=part['rings'];n=len(rings[0]);vertices=[v for ring in rings for v in ring];tri=[]
    for j in range(len(rings)-1):
        for i in range(n):
            a=j*n+i;b=j*n+(i+1)%n;c=(j+1)*n+(i+1)%n;d=(j+1)*n+i
            tri.extend([(a,b,c),(a,c,d)])
    caps=_triangulate_ring(rings[0]);tri.extend((c,b,a) for a,b,c in caps)
    off=(len(rings)-1)*n;tri.extend((a+off,b+off,c+off) for a,b,c in _triangulate_ring(rings[-1]))
    # Normalize winding: reliable signed volume, without world-origin cancellation.
    origin=vertices[0]
    volume=0.
    for ids in tri:
        a,b,c=[[vertices[i][k]-origin[k] for k in range(3)] for i in ids]
        volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
    if volume<0:tri=[(a,c,b) for a,b,c in tri];volume=-volume
    return vertices,tri,volume


@lru_cache(maxsize=16)
def _meshed(p):
    result=[]
    for component in _construction(p):
        vertices=[];tri=[];volume=0.;part_volumes=[]
        for part in component['parts']:
            vv,tt,v=_mesh_part(part);off=len(vertices)
            vertices.extend(vv);tri.extend(tuple(i+off for i in t) for t in tt);volume+=v;part_volumes.append(v)
        out={k:v for k,v in component.items() if k!='parts'}
        out.update(vertices=[round(v,6) for point in vertices for v in point],triangles=[i for t in tri for i in t],volume_mm3=volume,volume_m3=volume*1e-9,mass_kg=volume*1e-9*component['density_kg_m3'],part_count=len(component['parts']),part_volumes_mm3=part_volumes,role='installation_context' if component['group']=='wing' else 'hardware')
        out['bounds_mm']={'min':[min(v[j] for v in vertices) for j in range(3)],'max':[max(v[j] for v in vertices) for j in range(3)]}
        result.append(out)
    return result


def _channel(area_mm2,perimeter_mm,length_mm,heated_mm2=0.,**extras):
    return dict(area_m2=area_mm2*1e-6,wetted_perimeter_m=perimeter_mm*1e-3,length_m=length_mm*1e-3,heated_area_m2=heated_mm2*1e-6,hydraulic_diameter_m=4*area_mm2/perimeter_mm*1e-3,method='same-parameter equivalent flow section; not CFD volume extraction',**extras)


@lru_cache(maxsize=32)
def _metrics(p):
    R=p.motor_diameter_mm/2; gap=p.motor_gap_mm; n=p.hv_fin_count-1; h=p.hv_fin_height_mm; w=p.hv_gap_mm; length=p.cmc_length_mm
    channels={
        'main_inlet':_channel(math.pi*((R-8)**2-105**2),2*math.pi*(R-8+105),60,reference_plane='Front axial annulus: 105 mm spinner skirt to rotor inner lip R-8; feeds stator slots and rotor gap'),
        'motor_internal':_channel(math.pi*((R-18)**2-(R-18-gap)**2),2*math.pi*(2*(R-18)-gap),150,2*math.pi*(R-18-gap)*150),
        'motor_bypass':_channel(math.pi*((R+p.motor_bypass_gap_mm)**2-R**2),2*math.pi*(2*R+p.motor_bypass_gap_mm),190,2*math.pi*R*179),
        'motor_top_exhaust':_channel(p.motor_exhaust_area_mm2,2*(150+p.motor_exhaust_area_mm2/150),84,reference_plane='XY projected cowling cutout before louvers; louver contraction is a loss coefficient'),
        'cmc_hv_left':_channel(n*w*h,n*2*(w+h),length,n*(w+2*h)*length,fin_count=p.hv_fin_count,fin_gap_m=w*1e-3,fin_height_m=h*1e-3,fin_thickness_m=p.hv_fin_thickness_mm*1e-3,base_area_m2=n*w*length*1e-6,fin_area_m2=2*n*h*length*1e-6),
        'cmc_hv_right':_channel(n*w*h,n*2*(w+h),length,n*(w+2*h)*length,fin_count=p.hv_fin_count,fin_gap_m=w*1e-3,fin_height_m=h*1e-3,fin_thickness_m=p.hv_fin_thickness_mm*1e-3,base_area_m2=n*w*length*1e-6,fin_area_m2=2*n*h*length*1e-6),
        'cmc_bypass':_channel((p.nacelle_width_mm-2*p.cmc_width_mm-38)*62,2*(p.nacelle_width_mm-2*p.cmc_width_mm-38+62),p.cmc_length_mm),
        'lv_fresh_left':_channel(math.pi*37*p.upper_inlet_height_mm/2,math.pi*(3*(37+p.upper_inlet_height_mm/2)-math.sqrt((3*37+p.upper_inlet_height_mm/2)*(37+3*p.upper_inlet_height_mm/2))),270+p.cmc_length_mm,p.cmc_width_mm*p.cmc_length_mm),
        'lv_fresh_right':_channel(math.pi*37*p.upper_inlet_height_mm/2,math.pi*(3*(37+p.upper_inlet_height_mm/2)-math.sqrt((3*37+p.upper_inlet_height_mm/2)*(37+3*p.upper_inlet_height_mm/2))),270+p.cmc_length_mm,p.cmc_width_mm*p.cmc_length_mm),
        'lower_outlet':_channel(p.outlet_area_mm2,2*(160*p.nacelle_length_mm/1470+p.outlet_area_mm2/(160*p.nacelle_length_mm/1470)),160*p.nacelle_length_mm/1470,reference_plane='XY projected lower-shell aperture; opening angle solved from ruled shell section widths'),
    }
    bypass_inlet=_channel(math.pi*((R+p.main_inlet_height_mm-3)**2-R**2),2*math.pi*(2*R+p.main_inlet_height_mm-3),43,2*math.pi*R*13,reference_plane='Outer CM radius to inner cowling lip; 3 mm shell wall removed')
    guide_gap_front=min(p.motor_bypass_gap_mm,p.main_inlet_height_mm-3)
    bypass_segments=[bypass_inlet]
    for i in range(4):
        local_gap=guide_gap_front+(p.motor_bypass_gap_mm-guide_gap_front)*(i+.5)/4
        bypass_segments.append(_channel(math.pi*((R+local_gap)**2-R**2),2*math.pi*(2*R+local_gap),28,2*math.pi*R*28,reference_plane=f'Midpoint equivalent of tapered guide x={18+28*i}..{46+28*i} mm'))
    bypass_segments.append(_channel(math.pi*((R+p.motor_bypass_gap_mm)**2-R**2),2*math.pi*(2*R+p.motor_bypass_gap_mm),66,2*math.pi*R*66,reference_plane='Straight guide130..188 mm plus exposed rotor exit188..196 mm'))
    heat_lengths=[13,28,28,28,28,66]
    equivalent_area=sum(c['area_m2']*length for c,length in zip(bypass_segments,heat_lengths))/191
    equivalent_perimeter=sum(c['wetted_perimeter_m']*length for c,length in zip(bypass_segments,heat_lengths))/191
    heat_exchange={'area_m2':equivalent_area,'wetted_perimeter_m':equivalent_perimeter,'hydraulic_diameter_m':4*equivalent_area/equivalent_perimeter,'length_m':.191,'heated_area_m2':2*math.pi*R*191*1e-6,'method':'heated-length-weighted representative annulus of same-geometry serial sections'}
    channels['motor_bypass'].update({key:bypass_inlet[key] for key in ('area_m2','wetted_perimeter_m','hydraulic_diameter_m')})
    channels['motor_bypass'].update(segments=bypass_segments,inlet=bypass_inlet,heat_exchange=heat_exchange,length_m=sum(c['length_m'] for c in bypass_segments),heated_area_m2=heat_exchange['heated_area_m2'],heated_surfaces_m2={'motor_magnet':heat_exchange['heated_area_m2']},reference_plane='Outer inlet aperture for local-loss K; four tapered guide sections and straight exit in series')
    # Axial stator cooling slots are real openings between the 24 segmented
    # winding sectors. They are a parallel branch, not added wetted area on gap.
    slot_ro=R-18-gap-8;slot_ri=96.6;slot_angle=.043;slot_length=133.
    slot_area=24*.5*slot_angle*(slot_ro**2-slot_ri**2)
    slot_perimeter=24*(2*(slot_ro-slot_ri)+slot_angle*(slot_ro+slot_ri))
    slot_heated=24*2*(slot_ro-slot_ri)*slot_length
    channels['motor_slots']=_channel(slot_area,slot_perimeter,slot_length,slot_heated,slot_count=24,slot_angle_rad=slot_angle,inner_radius_m=slot_ri*.001,outer_radius_m=slot_ro*.001,heated_surfaces_m2={'motor_winding':slot_heated*1e-6})
    gap_surfaces={'motor_winding':2*math.pi*(R-18-gap)*150*1e-6,'motor_magnet':2*math.pi*(R-18)*150*1e-6}
    channels['motor_internal'].update(heated_surfaces_m2=gap_surfaces,heated_area_m2=sum(gap_surfaces.values()))
    channels['motor_internal']['heated_surface_note']='Equivalent cylindrical stator outer envelope and magnet inner wall; winding-to-stator conduction is lumped'
    for side in ('left','right'):
        key='lv_fresh_'+side
        # Backplate jet/confinement path differs from scoop inlet hydraulic diameter.
        exchanger=_channel((p.cmc_width_mm-14)*p.backplate_gap_mm,2*(p.cmc_width_mm-14+p.backplate_gap_mm),p.cmc_length_mm,p.cmc_width_mm*p.cmc_length_mm)
        exchanger['gap_m']=p.backplate_gap_mm*.001
        scoop={k:v for k,v in channels[key].items() if k in ('area_m2','wetted_perimeter_m','length_m','heated_area_m2','hydraulic_diameter_m')}
        scoop.update(length_m=.180,heated_area_m2=0.)
        channels[key]['heat_exchange']=exchanger
        channels[key]['segments']=[scoop,exchanger]
        channels[key]['length_m']=scoop['length_m']+exchanger['length_m']
        channels[key]['heat_exchange_note']='Inferred nominal backplate standoff with open connector end; full-plate jet heat-transfer area, not a sealed CFD duct'
    comps={};volumes={};mass=0;volume=0
    for c in _meshed(p):
        v=c['volume_m3'];m=c['mass_kg']
        if c['role']=='hardware':
            mass+=m;volume+=v;volumes[c['material']]=volumes.get(c['material'],0)+v
        comps[c['id']]={'volume_m3':v,'mass_kg':m,'material':c['material'],'density_kg_m3':c['density_kg_m3'],'role':c['role']}
        if c['id'].endswith('_hv'):
            comps[c['id']].update(fin_count=p.hv_fin_count,fin_height_m=p.hv_fin_height_mm*1e-3,fin_thickness_m=p.hv_fin_thickness_mm*1e-3,fin_area_m2=2*(p.hv_fin_count-1)*p.hv_fin_height_mm*p.cmc_length_mm*1e-6)
        if c['thermal_node']:
            area=p.cmc_length_mm*p.cmc_width_mm*1e-6 if c['id'].startswith('cmc') else 2*math.pi*(R-18-gap)*150*1e-6
            path=.006 if c['id'].endswith('hv') else .004
            path_note='Effective full plate/package thickness, idealized one-dimensional conduction'
            if c['id']=='motor_winding':
                area=gap_surfaces['motor_winding']+slot_heated*1e-6
                path=(2*math.pi/24-.043)*(slot_ro+slot_ri)/4*1e-3
                path_note='Inferred conduction direction: half mean circumferential winding-sector width, derived from sector geometry; not calibrated winding insulation/contact resistance'
            if c['id']=='motor_magnet':
                area=2*math.pi*((R-8)+(R-18))*153*1e-6;path=.005
                path_note='Half the reconstructed 10 mm radial magnet thickness; separate inner/outer cylindrical conduction patches'
                comps[c['id']]['conduction_patch_areas_m2']={'inner':2*math.pi*(R-18)*153*1e-6,'outer':2*math.pi*(R-8)*153*1e-6}
            if c['id'].endswith('_cpu'):area=54*46*1e-6;path=.010
            if c['id'].endswith('_acdc'):area=72*60*1e-6;path=.010
            comps[c['id']].update(conduction_area_m2=area,conduction_length_m=path,conduction_provenance=path_note)
    return {'parameters':asdict(p),'fingerprint':nacelle_fingerprint(p),'channels':channels,'components':comps,'mass_kg':mass,'solid_volume_m3':volume,'material_volumes_m3':volumes,'component_count':len(comps),'method':'closed procedural loft volume and dimensional equivalent flow sections','assumptions':ASSUMPTIONS,'flow_geometry_role':'network_equivalent_sections_only; no volumetric CFD air mesh or air-solid mass','mass_scope':'nacelle hardware only, host wing installation-context volume excluded','installation_context_volume_m3':sum(c['volume_m3'] for c in _meshed(p) if c['role']=='installation_context')}


def nacelle_metrics(params=None):
    # Return independent containers so caller mutations cannot poison the cache.
    return json.loads(json.dumps(_metrics(parse_nacelle(params))))


def assembly_geometry(params=None):
    p=parse_nacelle(params);components=_meshed(p)
    bounds={'min':[min(c['bounds_mm']['min'][j] for c in components) for j in range(3)],'max':[max(c['bounds_mm']['max'][j] for c in components) for j in range(3)]}
    return {'schema':SCHEMA,'parameters':asdict(p),'fingerprint':nacelle_fingerprint(p),'construction_sha256':GEOMETRY_SOURCE_SHA256,'components':json.loads(json.dumps(components)),'metrics':nacelle_metrics(p),'provenance':provenance(),'bounds_mm':bounds,'coordinate_system':{'units':'mm','x':'aft','y':'spanwise','z':'up'},'preview_method':'parameterized_closed_surface_lofts','cad':nacelle_cad_status(p)}


def _load_kernel():
    try:import cadquery as cq
    except (ImportError,OSError) as exc:raise RuntimeError('Fresh STEP generation requires optional CadQuery 2.7.0; the checked-in baseline STEP works without it') from exc
    return cq


def _shape_for_part(cq,part):
    wires=[cq.Wire.makePolygon([cq.Vector(*pt) for pt in ring],close=True) for ring in part['rings']]
    return cq.Solid.makeLoft(wires,ruled=True)


def build_nacelle(params=None):
    """Actual named BRep assembly; no hidden air boxes are exported as hardware."""
    p=parse_nacelle(params);cq=_load_kernel();assembly=cq.Assembly(name='X57_ModII_local_reconstruction');shapes={}
    for c in _construction(p):
        solids=[_shape_for_part(cq,part) for part in c['parts']]
        for i,solid in enumerate(solids):
            if not solid.isValid() or len(solid.Solids())!=1 or solid.Volume()<=0:
                raise RuntimeError(f"Invalid BRep solid {c['id']} part {i}")
        shape=cq.Compound.makeCompound(solids)
        shapes[c['id']]=shape
        assembly.add(shape,name=c['id'],color=cq.Color(*c['color'],c['opacity']))
    return assembly,shapes


def _read_step_artifact(directory, artifact):
    """Strict, bounded stdlib reassembly of one gzip member into one STEP file.

    Chunk sequence, file sizes and hashes are verified before decompression.
    No missing-part fallback or unchecked monolithic file is ever accepted.
    """
    if not isinstance(artifact, Mapping) or artifact.get('storage') != 'ordered_chunks_v1' or artifact.get('compression') != 'gzip':
        raise RuntimeError('Unsupported nacelle STEP artifact storage format')
    expected_compressed=artifact.get('compressed_bytes');expected_plain=artifact.get('bytes')
    for value,limit,label in ((expected_compressed,STEP_COMPRESSED_MAX_BYTES,'compressed'),(expected_plain,STEP_UNCOMPRESSED_MAX_BYTES,'uncompressed')):
        if type(value) is not int or not 0 < value <= limit:
            raise RuntimeError(f'Invalid nacelle STEP {label} size')
    chunks=artifact.get('chunks')
    expected_count=(expected_compressed+STEP_CHUNK_MAX_BYTES-1)//STEP_CHUNK_MAX_BYTES
    if not isinstance(chunks,list) or len(chunks)!=expected_count or artifact.get('chunk_max_bytes')!=STEP_CHUNK_MAX_BYTES:
        raise RuntimeError('Invalid nacelle STEP chunk count or limit')
    root=Path(directory).resolve();parts=[];seen=set();remaining=expected_compressed
    for index,chunk in enumerate(chunks):
        if not isinstance(chunk,Mapping) or type(chunk.get('index')) is not int or chunk['index']!=index:
            raise RuntimeError('Nacelle STEP chunks are missing or out of order')
        name=chunk.get('file');size=chunk.get('bytes')
        if not isinstance(name,str) or not name or name in seen or Path(name).name!=name or name in ('.','..') or '/' in name or '\\' in name:
            raise RuntimeError('Invalid or repeated nacelle STEP chunk filename')
        seen.add(name);path=root/name
        if path.resolve().parent!=root:
            raise RuntimeError('Nacelle STEP chunk path leaves artifact directory')
        if type(size) is not int or size!=min(STEP_CHUNK_MAX_BYTES,remaining):
            raise RuntimeError('Invalid nacelle STEP chunk size')
        try:
            if path.stat().st_size!=size:
                raise RuntimeError(f'Nacelle STEP chunk size mismatch: {name}')
            with path.open('rb') as handle:
                data=handle.read(size+1)
        except OSError as exc:
            raise RuntimeError(f'Nacelle STEP chunk unavailable: {name}') from exc
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=chunk.get('sha256'):
            raise RuntimeError(f'Nacelle STEP chunk checksum mismatch: {name}')
        parts.append(data);remaining-=size
    compressed=b''.join(parts)
    if len(compressed)!=expected_compressed or hashlib.sha256(compressed).hexdigest()!=artifact.get('compressed_sha256'):
        raise RuntimeError('Stored nacelle STEP combined compressed checksum mismatch')
    try:
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        payload=decoder.decompress(compressed,expected_plain+1)
    except zlib.error as exc:
        raise RuntimeError('Invalid nacelle STEP gzip stream') from exc
    if len(payload)!=expected_plain or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
        raise RuntimeError('Nacelle STEP decompressed size, completeness or member count mismatch')
    if hashlib.sha256(payload).hexdigest()!=artifact.get('sha256'):
        raise RuntimeError('Stored nacelle STEP checksum mismatch')
    return payload


def _artifact(params):
    path=CAD_DIR/'manifest.json'
    if not path.is_file():return None
    manifest=json.loads(path.read_text())
    if manifest.get('fingerprint')!=nacelle_fingerprint(params):return None
    if manifest.get('geometry_module_sha256')!=GEOMETRY_SOURCE_SHA256:return None
    v=manifest.get('validation',{});r=manifest.get('roundtrip',{})
    if not(v.get('passed') and v.get('intersection_audit_complete') and v.get('unexpected_intersection_count')==0 and r.get('passed') and manifest.get('mesh_validation',{}).get('passed')):return None
    return _read_step_artifact(CAD_DIR,manifest['artifacts']['step'])


def nacelle_cad_status(params=None):
    p=parse_nacelle(params);installed=importlib.util.find_spec('cadquery') is not None;stored=False;verified=False
    try:
        stored=_artifact(p) is not None
        if stored:verified=json.loads((CAD_DIR/'manifest.json').read_text()).get('validation',{}).get('passed',False)
    except (OSError,ValueError,KeyError,RuntimeError):pass
    return {'kernel_available':installed,'stored_step_available':stored,'step_available':installed or stored,'verification':'verified_baseline_BRep' if verified else 'procedural_mesh_only','custom_fit_status':'Baseline full interference/contact audit only; custom shapes are range/forward-clearance checked but require a fresh full BRep audit','fingerprint':nacelle_fingerprint(p),'download_filename':'x57-modii-nacelle.step'}


def generate_nacelle_step(params=None,force_regenerate=False):
    p=parse_nacelle(params)
    if not force_regenerate:
        blob=_artifact(p)
        if blob is not None:return blob
    assembly,_=build_nacelle(p)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'x57-modii-nacelle.step'
        assembly.save(str(path),exportType='STEP',mode='default')
        return path.read_bytes()


def mesh_audit(params=None):
    result=[]
    for c in _meshed(parse_nacelle(params)):
        edges=Counter();tri=c['triangles']
        for j in range(0,len(tri),3):
            a,b,d=tri[j:j+3]
            for u,v in ((a,b),(b,d),(d,a)):edges[tuple(sorted((u,v)))]+=1
        closed=all(count==2 for count in edges.values())
        result.append({'id':c['id'],'closed_indexed_mesh':closed,'volume_mm3':c['volume_mm3'],'parts':c['part_count'],'vertex_count':len(c['vertices'])//3,'triangle_count':len(tri)//3})
    return {'passed':all(c['closed_indexed_mesh'] and c['volume_mm3']>0 for c in result),'components':result,'method':'edge incidence and signed tetrahedral volume for each closed primitive'}


def inspect_nacelle_brep(shapes,params=None,check_intersections=True,progress=None):
    """Independent kernel volume/validity plus explicitly classified interference.

    The declared structural attachment pairs are tested and recorded, rather than
    accepted because their group names happen to be similar. Small coincident
    contacts have zero volume. Nonzero overlaps remain visible in the report.
    """
    p=parse_nacelle(params);expected={c['id']:c for c in _meshed(p)};checks=[]
    for key,shape in shapes.items():
        target=expected[key]['volume_mm3'];actual=shape.Volume();error=abs(actual-target)/max(target,1)
        checks.append({'id':key,'valid':shape.isValid(),'solid_count':len(shape.Solids()),'closed_shells':all(s.Closed() for s in shape.Shells()),'volume_mm3':actual,'mesh_volume_mm3':target,'relative_volume_error':error,'passed':shape.isValid() and all(s.Closed() for s in shape.Shells()) and actual>0 and error<.018})
    intersections=[];tested=0;context_junctions=[]
    if check_intersections:
        keys=list(shapes)
        solid_parts={key:[(solid,solid.BoundingBox()) for solid in shape.Solids()] for key,shape in shapes.items()}
        for i,a in enumerate(keys):
            ba=shapes[a].BoundingBox()
            for b in keys[i+1:]:
                bb=shapes[b].BoundingBox()
                if any(min(getattr(ba,d+'max'),getattr(bb,d+'max'))-max(getattr(ba,d+'min'),getattr(bb,d+'min'))<.05 for d in 'xyz'):continue
                if expected[a]['role']=='installation_context' or expected[b]['role']=='installation_context':
                    context_junctions.append({'a':a,'b':b,'method':'overlapping installation-context bounds; not a hardware collision or mass contribution'})
                    continue
                tested+=1
                if progress:progress(f'Checking interference {tested}: {a} / {b}')
                vol=0.
                for sa,bsa in solid_parts[a]:
                    for sb,bsb in solid_parts[b]:
                        if any(min(getattr(bsa,d+'max'),getattr(bsb,d+'max'))-max(getattr(bsa,d+'min'),getattr(bsb,d+'min'))<.05 for d in 'xyz'):continue
                        vol+=sa.intersect(sb).Volume()
                if vol<.5:continue
                reason=_intersection_reason(a,b)
                intersections.append({'a':a,'b':b,'intersection_mm3':vol,'allowed':reason is not None,'reason':reason or 'unresolved geometric overlap'})
    contact_pairs=[('motor_shaft','motor_rotor'),('motor_shaft','propeller_hub'),('main_inlet_lip','cowling_upper')]
    for side in ('left','right'):
        contact_pairs.extend([(f'lv_inlet_{side}',f'cmc_{side}_lv'),(f'lv_inlet_{side}',f'cmc_{side}_lv_duct')])
        sign=-1 if side=='left' else 1
        for name,z in [('upper',1),('lower',-1)]:
            contact_pairs.extend([(f'cmc_{side}_mount_{name}',f'cmc_{side}_case'),(f'cmc_{side}_mount_{name}',f'cmc_frame_{sign:+d}_{z:+d}'),(f'mount_strut_{sign:+d}_{z:+d}','local_wing')])
    contacts=[{'a':a,'b':b,'minimum_distance_mm':shapes[a].distance(shapes[b])} for a,b in contact_pairs]
    for item in contacts:item['passed']=item['minimum_distance_mm']<.1
    return {'passed':all(c['passed'] for c in checks) and all(i['allowed'] for i in intersections) and all(c['passed'] for c in contacts),'method':'independent OpenCascade BRep volume, closed-shell and interference measurement','components':checks,'component_count':len(checks),'solid_count':sum(c['solid_count'] for c in checks),'volume_mm3':sum(c['volume_mm3'] for c in checks),'mesh_relative_volume_tolerance':.018,'intersections':intersections,'intersection_pairs_tested':tested,'context_junctions':context_junctions,'mechanical_contact_checks':contacts,'unexpected_intersection_count':sum(not i['allowed'] for i in intersections),'limitations':['Ruled polygonal BRep sections approximate smooth manufactured contours','Explicitly allowed attachment penetrations are visual structural joints, not engineered fasteners','Interference audit does not establish structural or manufacturing validity']}


def _intersection_reason(a,b):
    pair=frozenset((a,b))
    # Specific intentional joints; no blanket motor/controller exemptions.
    for side in ('left','right'):
        sign=-1 if side=='left' else 1
        for name,z in [('upper',1),('lower',-1)]:
            bracket=f'cmc_{side}_mount_{name}'
            if pair in (frozenset((bracket,f'cmc_{side}_case')),frozenset((bracket,f'cmc_frame_{sign:+d}_{z:+d}'))):return 'Explicit inferred CMC mounting bracket seats into case and cradle attachment envelopes'
        if pair==frozenset(('cowling_upper',f'lv_inlet_{side}')):return 'Thin scoop wall seats through cowling opening edge as an attachment flange'
    for side in (-1,1):
        if pair==frozenset((f'mount_strut_{side:+d}_-1',f'mount_strut_{side:+d}_+1')):return 'Upper and lower support tubes converge at the same inferred wing attachment node'
        for z in (-1,1):
            if pair==frozenset(('motor_rear_mount',f'mount_strut_{side:+d}_{z:+d}')):return 'Motor support tube seats into the inferred mounting-flange attachment envelope'
            if pair==frozenset((f'mount_strut_{side:+d}_{z:+d}',f'cmc_frame_{side:+d}_{z:+d}')):return 'Longitudinal support/cradle shared welded attachment envelope; detailed clamp hardware omitted'
        if any(pair==frozenset((f'mount_strut_{side:+d}_-1',f'cmc_frame_cross_{name}')) for name in ('front','rear')):return 'Cradle crossmember / motor support attachment envelope'
        for name in ('front','rear'):
            if pair==frozenset((f'cmc_frame_{side:+d}_-1',f'cmc_frame_cross_{name}')):return 'Welded tubular CMC cradle corner joint'
    if pair==frozenset(('local_wing','cowling_tail')):return 'Aft fairing intersects host-wing root at the modeled attachment boundary'
    if pair==frozenset(('propeller_spinner','propeller_hub')):return 'Spinner shell / hub interface is represented by overlapping attachment envelopes'
    if 'propeller_hub' in pair and any(x.startswith('propeller_blade_') for x in pair):return 'Blade root is seated inside the propeller hub'
    if 'propeller_spinner' in pair and any(x.startswith('propeller_blade_') for x in pair):return 'Blade root passes through inferred spinner attachment aperture'
    if pair==frozenset(('motor_shaft','propeller_spinner')):return 'Spinner nose internal shaft attachment envelope'
    return None
