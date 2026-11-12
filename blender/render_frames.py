"""Draws the frames written by characters.export as soft toys, in one Blender session (Cycles). Run with a Python
that has bpy 4.2 (characters.blender.PYTHON); `characters.film.Film.render(finish="fur")` runs it for you.

usage: python render_frames.py <frames folder> <png folder> <options.json>
options: finish ("fur": real pile on the furry cloth | "terry": the same cloth with no hairs, faster | "vinyl" |
         "lowpoly": few flat facets; facet = their size in metres, columns and rows = the most round and along a part,
         shade = how much one facet's colour differs from the next (parts that say how they break, see _faceted(),
         keep `residual` of it: light tells their facets apart); relief = their depth, as a share of what the
         part asks; break = the smallest piece that breaks about a point of its own, as a share of the facet's
         size; wander = how far from its middle that point may lie; key, fill, rim, bounce = a lamp as [degrees
         round from the camera, degrees up, metres away, size, watts, r, g, b]; sky and top = the strength of the
         light from everywhere and of the lamp that casts the floor's shadow; ao, ao_reach = how much and how
         far (metres) surfaces darken each other; satin, satin_rough = the share and the roughness of the gloss on
         a satin material, see lowpoly_material(); alpha = true writes RGBA frames with a transparent film: the
         figure and its shadow on the ground and no backdrop, for characters.bridge; low poly only),
         device ("OPTIX" | "CUDA" | "CPU"), samples, scale (share of the film's size that is rendered),
         density (hairs per m2, as a share of 42000), children (hairs drawn per hair grown), radius (hair width).
Frames already drawn are skipped, so an interrupted render picks up where it stopped.
"""
import json, math, sys, time, zlib
from pathlib import Path

import bpy
from mathutils import Vector, kdtree

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
opt = {"finish": "fur", "device": "OPTIX", "samples": 8, "scale": 0.66, "density": 0.15, "children": 20, "radius": 2.0,
       **json.loads(Path(sys.argv[3]).read_text())}
meta = json.loads((src / "export.json").read_text())
files = sorted(f for f in src.glob("[0-9]*.json"))
W, H = meta["size"]
FUR = opt["finish"] == "fur"
VINYL = opt["finish"] == "vinyl"
LOWPOLY = opt["finish"] == "lowpoly"      # every part redrawn with few flat facets (see facets())

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
materials: dict = {}


def srgb(hex_):
    h = hex_.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]


def principled(name, colour, rough=0.9, sheen=0.0, metallic=0.0, sss=0.0, glow=0.0):
    if name in materials:
        return materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = colour
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Sheen Roughness"].default_value = 0.5
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (0.02, 0.012, 0.008)
    if glow:
        b.inputs["Emission Color"].default_value = colour
        b.inputs["Emission Strength"].default_value = glow
    materials[name] = mat
    return mat


def pile_material(name, colour):
    if name in materials:
        return materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    o, h = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    h.parametrization = "COLOR"
    h.inputs["Color"].default_value = [c ** 1.5 for c in colour[:3]] + [1.0]   # dense pile reads paler than its colour
    h.inputs["Roughness"].default_value = 0.55
    h.inputs["Radial Roughness"].default_value = 0.75
    nt.links.new(h.outputs["BSDF"], o.inputs["Surface"])
    materials[name] = mat
    return mat


def terry_material(name, colour):
    """Furry cloth with no hairs: a soft nap read from its bumps, and a paler halo at grazing angles."""
    if name in materials:
        return materials[name]
    mat = principled(name, colour, rough=1.0, sheen=1.0)
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    tc, v, bump = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeTexVoronoi"), nt.nodes.new("ShaderNodeBump")
    v.feature = "SMOOTH_F1"
    v.inputs["Scale"].default_value = 620
    bump.inputs["Strength"].default_value, bump.inputs["Distance"].default_value = 1.0, 0.003
    nt.links.new(tc.outputs["Object"], v.inputs["Vector"])
    nt.links.new(v.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    lw, mix, amount = nt.nodes.new("ShaderNodeLayerWeight"), nt.nodes.new("ShaderNodeMixRGB"), nt.nodes.new("ShaderNodeMath")
    lw.inputs["Blend"].default_value = 0.35
    mix.inputs["Color1"].default_value = colour
    mix.inputs["Color2"].default_value = [min(1.0, c * 1.5 + 0.15) for c in colour[:3]] + [1]
    amount.operation = "MULTIPLY"
    amount.inputs[1].default_value = 0.45
    nt.links.new(lw.outputs["Facing"], amount.inputs[0])
    nt.links.new(amount.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(mix.outputs["Color"], b.inputs["Base Color"])
    return mat


def vinyl_material(name, colour, rough=0.46):
    """Moulded vinyl, as a collectible toy: matte with a soft sheen, a little light inside it, a thin clear coat."""
    if name in materials:
        return materials[name]
    mat = principled(name, colour, rough=rough, sss=0.1)
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Coat Weight"].default_value = 0.18
    b.inputs["Coat Roughness"].default_value = 0.35
    b.inputs["Subsurface Radius"].default_value = (0.012, 0.008, 0.006)
    return mat


def by_kind(kind, material, hex_):
    """The material of a part that has no pile, by what characters.cloth says it is."""
    colour = srgb(hex_)
    name = f"{kind}:{material}"
    if kind in ("vinyl", "satin") or (VINYL and kind == "felt"):      # satin is the low-poly finish's: vinyl in the others
        return vinyl_material("vinyl:" + material, colour)
    if VINYL and kind == "stitch":      # painted on the toy
        return vinyl_material("paint:" + material, [c * 0.75 for c in colour[:3]] + [1], rough=0.55)
    if kind == "eye":
        return principled(name, (0.012, 0.01, 0.01, 1), rough=0.28)
    if kind == "shine":
        return principled(name, (0.95, 0.95, 0.93, 1), rough=0.4)
    if kind == "metal":
        return principled(name, colour, rough=0.28, metallic=1.0)
    if kind == "plastic":
        return principled(name, colour, rough=0.35, sss=0.05)
    if kind == "glow":
        return principled(name, colour, rough=0.4, glow=2.5)
    if kind == "gloss":
        return principled(name, colour, rough=0.1)
    if kind == "stitch":
        return principled(name, [c * 0.7 for c in colour[:3]] + [1], rough=0.85, sheen=0.3)
    return principled(name, colour, rough=1.0, sheen=0.8, sss=0.15)        # felt


def lowpoly_material(name, colour, satin=False):
    """Matte; a facet is told from the next by the light it takes. What is drawn into the colour is little: the
    mesh's "Shade" attribute (a facet a touch lighter or darker), a gradient up the figure, and a darkening
    where surfaces close on each other. `satin` (a cap's peak, polished leather) adds a soft light where a lamp
    is mirrored: a small fixed share (option `satin`, 0.01) of a rough gloss (`satin_rough`, 0.35) over the same
    matte colour. The share does not grow at grazing angles as a real gloss's does, so no facet becomes a mirror:
    a dark peak whose whole top mirrors a lamp goes to a middle grey (127 of 255 as measured; 183 with 0.03)."""
    if name in materials:
        return materials[name]
    mat = principled(name, colour, rough=0.8)
    nt = mat.node_tree
    if satin:
        gloss, both = nt.nodes.new("ShaderNodeBsdfGlossy"), nt.nodes.new("ShaderNodeMixShader")
        gloss.inputs["Roughness"].default_value = float(opt.get("satin_rough", 0.35))
        both.inputs["Fac"].default_value = float(opt.get("satin", 0.01))
        nt.links.new(nt.nodes["Principled BSDF"].outputs["BSDF"], both.inputs[1])
        nt.links.new(gloss.outputs["BSDF"], both.inputs[2])
        nt.links.new(both.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
    shade, mix = nt.nodes.new("ShaderNodeVertexColor"), nt.nodes.new("ShaderNodeMixRGB")
    shade.layer_name, mix.blend_type = "Shade", "MULTIPLY"
    mix.inputs["Fac"].default_value = 1.0
    mix.inputs["Color1"].default_value = colour
    nt.links.new(shade.outputs["Color"], mix.inputs["Color2"])
    # and a little lighter toward the top of the figure than at its feet, as a painted palette's gradient strip is
    geo, split, ramp, tone = (nt.nodes.new(n) for n in ("ShaderNodeNewGeometry", "ShaderNodeSeparateXYZ",
                                                       "ShaderNodeMapRange", "ShaderNodeMixRGB"))
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.0, 1.0
    ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 0.86, 1.07
    tone.blend_type = "MULTIPLY"
    tone.inputs["Fac"].default_value = 1.0
    nt.links.new(geo.outputs["Position"], split.inputs[0])
    nt.links.new(split.outputs["Z"], ramp.inputs["Value"])
    nt.links.new(mix.outputs["Color"], tone.inputs["Color1"])
    nt.links.new(ramp.outputs["Result"], tone.inputs["Color2"])
    close = float(opt.get("ao", 0.45))
    if close <= 0:
        nt.links.new(tone.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        return mat
    # and darker where another surface is near: in a crease, under a collar, between an arm and the body. One
    # ray a sample is enough (a picture has many samples), and more cost a third of the render's time.
    near, dark, shut = (nt.nodes.new(n) for n in ("ShaderNodeAmbientOcclusion", "ShaderNodeMapRange", "ShaderNodeMixRGB"))
    near.samples, near.inputs["Distance"].default_value = int(opt.get("ao_samples", 1)), float(opt.get("ao_reach", 0.07))
    dark.inputs["From Min"].default_value, dark.inputs["From Max"].default_value = 0.0, 1.0
    dark.inputs["To Min"].default_value, dark.inputs["To Max"].default_value = 1.0 - close, 1.0
    shut.blend_type = "MULTIPLY"
    shut.inputs["Fac"].default_value = 1.0
    nt.links.new(near.outputs["AO"], dark.inputs["Value"])
    nt.links.new(tone.outputs["Color"], shut.inputs["Color1"])
    nt.links.new(dark.outputs["Result"], shut.inputs["Color2"])
    nt.links.new(shut.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    return mat


def to_blender(p):
    """The SDK's space (y up, +z to the front, and +x on the LEFT of a camera on +z: left-handed) in Blender's
    (z up, right-handed). x changes sign, or the whole picture comes out mirrored."""
    return (-p[0], -p[2], p[1])


def grid(part):
    nu, nv, flat = part["nu"], part["nv"], part["verts"]
    verts = [to_blender(flat[i:i + 3]) for i in range(0, len(flat), 3)]
    faces = [[j * nu + i, j * nu + (i + 1) % nu, (j + 1) * nu + (i + 1) % nu, (j + 1) * nu + i]
             for j in range(nv) for i in range(nu)]
    return verts, faces


def _keep(points, most, least, flat, closed):
    """Which of these points hold the line's shape: the one that stands least off the line through its neighbours
    goes first (Visvalingam's rule, by height), until `most` are left, and on down to `least` while what goes
    stands off by less than `flat` metres. A point is a tuple of vectors, so several lines are simplified as one."""
    live = list(range(len(points)))

    def cost(n):
        i, j, k = live[n - 1], live[n], live[(n + 1) % len(live)]
        worst = 0.0
        for a, b, c in zip(points[i], points[j], points[k]):
            base = (c - a).length
            worst = max(worst, (b - a).cross(c - a).length / base if base > 1e-9 else (b - a).length)
        return worst

    while len(live) > least:
        span = range(len(live)) if closed else range(1, len(live) - 1)
        if not span:
            break
        n = min(span, key=cost)
        if len(live) <= most and cost(n) >= flat:
            break
        live.pop(n)
    return live


def facets(part):
    """A part as low poly: only the rows and columns of its grid that hold its shape (its corners and edges, found
    by simplifying its outline along and around), joined by large flat triangles. A row or a column that changes
    nothing is not drawn, so a straight limb is one band and a flat end one fan. The choice is made on the part's
    own shape and gives the same rows and columns on every frame, so the facets ride the figure as it moves.
    A `drawn` part keeps all of its grid, and one that also says how its sides break (`facet`) is cut by
    _faceted(). Gives the points, the triangles, whether it is shaded smooth (paint), whether it was cut so."""
    nu, nv, flat = part["nu"], part["nv"], part["verts"]
    at = lambda i, j: Vector(to_blender(flat[3 * (j * nu + i % nu):3 * (j * nu + i % nu) + 3]))
    # what is drawn on a face (eyes, brows, the mouth's line) keeps a round outline and is shaded smooth, as paint is
    paint = part["kind"] in ("eye", "shine", "stitch") or part["material"] in ("m.mouth", "m.tongue")
    quarter = [round(nu * q / 4) for q in range(4)]
    run = [0.0]
    for j in range(nv):
        run.append(run[-1] + max((at(i, j + 1) - at(i, j)).length for i in quarter))
    girth = [sum((at(i + 1, j) - at(i, j)).length for i in range(nu)) for j in range(nv + 1)]
    size = float(opt.get("facet", 0.045))
    tol = float(opt.get("flat", 0.0025))                         # a bend smaller than this is not a facet
    drawn = bool(part.get("drawn")) and not paint               # it says where its facets are: all of its grid
    if drawn:
        pass
    elif paint:
        line = max(girth) < 0.06                                 # a stroke: a thin tube, one of many end to end
    else:
        least_v = 3
        most_u = max(4, min(int(opt.get("columns", 8)), nu, round(max(girth) / size)))
        least_u = 6 if max(girth) > 0.2 else 4                   # a limb is round: six sides at least; small parts four
        most_v = max(3, min(int(opt.get("rows", 7)), nv, round(run[-1] / 0.06) + 2))
        most_u = max(most_u, least_u)
    if drawn:
        rows, cols = list(range(nv + 1)), list(range(nu))
    elif paint and line:         # a stroke's tube: four sides, its two ends and where each end's rounding starts
        rows, cols = [0, round(nv / 3), round(2 * nv / 3), nv], [round(i * nu / 4) for i in range(4)]
    elif paint:                  # an eye: its grid thinned evenly, so it stays as round and as domed as it was
        step_u, step_v = max(1, round(nu / 12)), max(1, round(nv / 6))
        rows, cols = sorted({*range(0, nv, step_v), nv}), list(range(0, nu, step_u))
    else:
        rows = _keep([tuple(at(i, j) for i in quarter) for j in range(nv + 1)], most_v + 1, least_v, tol, closed=False)
        thick = sorted(range(nv + 1), key=lambda j: -girth[j])[:3]   # the rows where the section is widest
        cols = _keep([tuple(at(i, j) for j in thick) for i in range(nu)], most_u, least_u, tol, closed=True)
    lu, lv = len(cols), len(rows) - 1
    verts, tris = [], []
    for r in rows:
        ring = [at(i, r) for i in cols]
        # few points drawn inside a round section make it thinner: grow the ring to the area the section has
        centre = sum(ring, Vector()) / lu
        full = [at(i, r) for i in range(nu)]
        area = lambda ps: sum(((ps[n] - centre).cross(ps[(n + 1) % len(ps)] - centre) for n in range(len(ps))), Vector()).length
        had, has = area(full), area(ring)
        grow = min(1.3, math.sqrt(had / has)) if has > 1e-12 and not paint and not drawn else 1.0
        verts += [centre + (p - centre) * grow for p in ring]
    facet = part.get("facet") if drawn else None                # it also says how its sides break: see _faceted()
    if facet:
        verts, tris = _faceted(verts, lu, lv, facet, facet.get("key", part["id"]))
        return verts, tris, paint, True
    for j in range(lv):
        a, b = j * lu, (j + 1) * lu
        for i in range(lu):
            k = (i + 1) % lu
            pair = ((a + i, a + k, b + k), (a + i, b + k, b + i)) if (i + j) % 2 == 0 else \
                   ((a + i, a + k, b + i), (a + k, b + k, b + i))
            for t in pair:
                p, q, r_ = (verts[n] for n in t)
                if min((p - q).length, (q - r_).length, (r_ - p).length) > 1e-6:     # a pole's rows are one point
                    tris.append(t)
    return verts, tris, paint, False


def _chance(ident, n):
    """A number from 0 to 1 that is the same on every frame for the same place of the same part."""
    return (zlib.crc32(f"{ident}:{n}".encode()) % 10007) / 10007.0


def _plan(facet, verts, lu, lv):
    """How many pieces each side (round) and each band (along) of a faceted part is cut into, and whether a
    piece is large enough to break about a point of its own: (pieces, breaks, the piece's length in metres).
    Read from the part's own measures when its tag gives them (the same on every frame, so no facet appears or
    goes as the figure moves), else from this frame's corners."""
    size = facet["size"]
    sides, bands = facet.get("sides"), facet.get("bands")
    P = lambda i, j: verts[j * lu + i % lu]
    girth = [sum((P(i + 1, j) - P(i, j)).length for i in range(lu)) for j in range(lv + 1)]
    pole = [j in (0, lv) and girth[j] < 0.01 for j in range(lv + 1)]        # an end closed to (almost) a point
    if not sides or len(sides) != lu or not bands or len(bands) != lv:
        real = [j for j in range(lv) if not (pole[j] or pole[j + 1])]
        tall = [sum((P(i, j + 1) - P(i, j)).length for i in range(lu)) / lu for j in range(lv)]
        run = sum(tall[j] for j in real) or 1.0
        sides = [round(sum(((P(i + 1, j) - P(i, j)).length + (P(i + 1, j + 1) - P(i, j + 1)).length) / 2 * tall[j]
                           for j in real) / run, 3) for i in range(lu)]
        bands = [round(tall[j], 3) for j in range(lv)]
    least = float(opt.get("break", 0.4)) * size                 # a piece smaller than this stays flat
    most = int(opt.get("pieces", 6))

    def cut(length):
        n = max(1, min(most, int(length / size + 0.513)))
        return n, length / n >= least, length / n

    cols = [cut(w) for w in sides]
    rows = [(1, False, bands[j]) if pole[j] or pole[j + 1] else cut(bands[j]) for j in range(lv)]
    return cols, rows, pole


def _faceted(verts, lu, lv, facet, ident):
    """The sides of a lofted part as cloth and muscle break: each side between four of its corners is cut into a
    small grid of pieces about `size` across (see _plan); the grid's points slide along the side's edges, and
    inside the side they move within it and in or out of it by up to `depth`; a piece that is large enough breaks
    about a point of its own, pushed in or out as well; the others are cut by one diagonal or the other. Every
    choice is a number drawn from the part's id and the place (_chance), so the same facets ride the figure on
    every frame. The loft's corners and the straight edges between them stay exactly where they are: what is
    seated on the part still lies on it, and its outline is what was drawn. A point on an edge belongs to the
    edge, so the two sides that share it meet with no crack. The closed ends are left flat."""
    size, depth = facet["size"], facet["depth"] * float(opt.get("relief", 1.0))
    cols, rows, pole = _plan(facet, verts, lu, lv)
    wander = float(opt.get("wander", 0.56))                     # the share of a piece, about its middle, its own point lies in
    out = list(verts)
    P = lambda i, j: j * lu + i % lu
    middle = sum(verts, Vector()) / len(verts)
    turn = sum(((verts[P(i + 1, j)] - verts[P(i, j)]).cross(verts[P(i, j + 1)] - verts[P(i, j)])
                .dot((verts[P(i, j)] + verts[P(i + 1, j + 1)]) / 2 - middle) for j in range(lv) for i in range(lu)), 0.0)
    turn = 1.0 if turn >= 0 else -1.0                          # which way the grid winds: its normals point out

    def push(key, scale):
        """How far a point inside a side leaves it: never by little, or its facets would lie as their neighbours
        do and take the same light. Seven in ten go in, as cloth dents between its seams; the others come out
        by a third as much, so the outline and what is seated on the part keep their place."""
        far = depth * min(1.5, scale / size) * (0.5 + 0.5 * _chance(key, "d"))
        return -far if _chance(key, "o") < 0.7 else 0.3 * far

    def edge(a, b, n, key, closed):
        """The points along one edge of the grid, from corner to corner: shared by the sides on both hands."""
        ids = [a]
        for k in range(1, n):
            if closed:                   # a pole: its points are its two corners
                ids.append(a if 2 * k <= n else b)
                continue
            t = (k + 0.5 * (_chance(key, k) - 0.5)) / n
            out.append(out[a].lerp(out[b], t))
            ids.append(len(out) - 1)
        return ids + [b]

    across = {(i, j): edge(P(i, j), P(i + 1, j), cols[i][0], f"{ident}:h:{i}:{j}", pole[j])
              for j in range(lv + 1) for i in range(lu)}
    along = {(i, j): edge(P(i, j), P(i, j + 1), rows[j][0], f"{ident}:v:{i}:{j}", False)
             for j in range(lv) for i in range(lu)}
    tris = []
    for j in range(lv):
        m, tall, high = rows[j]
        for i in range(lu):
            n, wide, broad = cols[i]
            A, B, C, D = (verts[x] for x in (P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)))
            normal = (C - A).cross(D - B) * turn
            if normal.length < 1e-12:
                continue
            normal.normalize()
            key = f"{ident}:{i}:{j}"
            low, top, left, right = across[(i, j)], across[(i, j + 1)], along[(i, j)], along[((i + 1) % lu, j)]
            at = lambda u, v: (A + (B - A) * u) * (1 - v) + (D + (C - D) * u) * v
            cell = min(broad, high)
            grid = [low]
            for row in range(1, m):
                line = [left[row]]
                for col in range(1, n):
                    u = (col + 0.56 * (_chance(key, f"u{col}.{row}") - 0.5)) / n
                    v = (row + 0.56 * (_chance(key, f"v{col}.{row}") - 0.5)) / m
                    out.append(at(u, v) + normal * push(f"{key}:{col}.{row}", 1.4 * cell))
                    line.append(len(out) - 1)
                grid.append(line + [right[row]])
            grid.append(top)
            for row in range(m):
                for col in range(n):
                    a, b, c, d = grid[row][col], grid[row][col + 1], grid[row + 1][col + 1], grid[row + 1][col]
                    here = f"{key}:c{col}.{row}"
                    if len({a, b, c, d}) < 4:                    # against a pole: one triangle, or none
                        ring = [x for k, x in enumerate((a, b, c, d)) if x not in (a, b, c, d)[:k]]
                        if len(ring) == 3:
                            tris.append(tuple(ring))
                    elif wide and tall:                          # it breaks about a point of its own
                        s, t = 0.5 + wander * (_chance(here, "s") - 0.5), 0.5 + wander * (_chance(here, "t") - 0.5)
                        inside = (out[a].lerp(out[b], s)).lerp(out[d].lerp(out[c], s), t)
                        out.append(inside + normal * push(here, cell))
                        x = len(out) - 1
                        tris.extend(((a, b, x), (b, c, x), (c, d, x), (d, a, x)))
                    elif _chance(here, "x") < 0.5:
                        tris.extend(((a, b, c), (a, c, d)))
                    else:
                        tris.extend(((a, b, d), (b, c, d)))
    if turn < 0:
        tris = [(a, c, b) for a, b, c in tris]
    return out, tris


def _planes(verts, tris, within=7.0):
    """Triangles grouped into the planes they lie in: neighbours across an edge whose faces turn by less than
    `within` degrees are one plane, and are shaded as one, so a flat side reads as one polygon, not as its triangles."""
    normals = []
    for a, b, c in tris:
        n = (verts[b] - verts[a]).cross(verts[c] - verts[a])
        normals.append(n.normalized() if n.length > 1e-12 else Vector((0, 0, 1)))
    group = list(range(len(tris)))

    def find(x):
        while group[x] != x:
            group[x] = group[group[x]]
            x = group[x]
        return x

    edges: dict = {}
    limit = math.cos(math.radians(within))
    for t, tri in enumerate(tris):
        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            key = (min(e), max(e))
            if key in edges:
                other = edges[key]
                if normals[t].dot(normals[other]) > limit:
                    group[find(t)] = find(other)
            else:
                edges[key] = t
    return [find(t) for t in range(len(tris))]


def facet_object(name, groups, material):
    """Flat-shaded triangles of several parts in one object; each facet's shade is fixed by its part and place."""
    verts, tris, shades = [], [], []
    amount = float(opt.get("shade", 0.1))
    smooth = []
    for ident, v, t, soft, faceted in groups:
        base = len(verts)
        verts += v
        tris += [tuple(base + n for n in tri) for tri in t]
        if faceted:      # each triangle lies at its own angle to the light, which tells it from the next: no two
            # are shaded as one, and what is left of the drawn shade only keeps two that lie alike from merging
            swing, planes = amount * float(opt.get("residual", 0.25)), range(len(t))
        else:
            swing, planes = amount, _planes(v, t, float(opt.get("plane", 7.0)))
        shades += [1.0 if soft else 1.0 + ((zlib.crc32(f"{ident}:{k}".encode()) % 1000) / 1000.0 - 0.62) * 2 * swing
                   for k in planes]
        smooth += [soft] * len(t)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], tris)
    mesh.update()
    col = mesh.color_attributes.new("Shade", "FLOAT_COLOR", "CORNER")
    col.data.foreach_set("color", [c for g in shades for _ in range(3) for c in (g, g, g, 1.0)])
    mesh.polygons.foreach_set("use_smooth", smooth)
    mesh.materials.append(material)
    ob = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(ob)
    return ob


counted: list = []       # the first frame's triangles are reported once: FRAMES triangles ...


def build_lowpoly(data):
    groups: dict = {}
    tally: dict = {}
    for part in data["parts"]:
        v, t, soft, faceted = facets(part)
        key = part["figure"] + " " + part["name"].split("/")[0].rstrip("0123456789_-lr")
        tally[key] = tally.get(key, 0) + len(t)
        groups.setdefault((part["kind"], part["material"], part["colour"]), []).append(((part.get("facet") or {}).get("key", part["id"]), v, t, soft, faceted))
    for (kind, material, hex_), parts in groups.items():
        plain = kind in ("eye", "shine", "metal", "glow", "gloss")
        mat = by_kind(kind, material, hex_) if plain else lowpoly_material("lowpoly:" + material, srgb(hex_), kind == "satin")
        made.append(facet_object(f"{kind}:{material}", parts, mat))
        figure.objects.link(made[-1])
    if not counted:
        counted.append(True)
        top = sorted(tally.items(), key=lambda kv: -kv[1])
        print(f"FRAMES triangles {sum(tally.values())} in {len(data['parts'])} parts: "
              + ", ".join(f"{k} {n}" for k, n in top[:14]), flush=True)
    for prop in data.get("props", ()):
        flat = prop["verts"]
        verts = [to_blender(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        ob = mesh_object(prop["id"], verts, prop["faces"], smooth=False)
        ob.data.materials.append(principled("prop:" + prop["material"], srgb(prop["colour"]), rough=0.9))
        made.append(ob)
        figure.objects.link(ob)


def mesh_object(name, verts, faces, smooth=True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-5)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    if smooth:
        bpy.ops.object.shade_smooth()
    ob.select_set(False)
    return ob


made: list = []          # this frame's objects and particle settings, removed before the next


def clear():
    for ob in [o for o in made if isinstance(o, bpy.types.Object)]:
        mesh = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    for ps in [o for o in made if isinstance(o, bpy.types.ParticleSettings)]:
        bpy.data.particles.remove(ps)
    made.clear()


def build(data):
    if LOWPOLY:
        return build_lowpoly(data)
    furry = [p for p in data["parts"] if p["kind"] == "fur"]
    other: dict = {}
    for part in data["parts"]:
        if part["kind"] == "fur":
            continue
        verts, faces = grid(part)
        g = other.setdefault((part["kind"], part["material"], part["colour"]), ([], []))
        base = len(g[0])
        g[0].extend(verts)
        g[1].extend([[base + i for i in f] for f in faces])
    for (kind, material, hex_), (verts, faces) in other.items():
        ob = mesh_object(f"{kind}:{material}", verts, faces)
        ob.data.materials.append(by_kind(kind, material, hex_))
        made.append(ob)
    for prop in data.get("props", ()):
        flat = prop["verts"]
        verts = [to_blender(flat[i:i + 3]) for i in range(0, len(flat), 3)]
        ob = mesh_object(prop["id"], verts, prop["faces"], smooth=len(verts) > 8)
        ob.data.materials.append(principled("prop:" + prop["material"], srgb(prop["colour"]), rough=0.9))
        made.append(ob)
    if not FUR:
        for part in furry:
            verts, faces = grid(part)
            ob = mesh_object(part["id"], verts, faces)
            colour = srgb(part["colour"])
            ob.data.materials.append(vinyl_material("vinyl:" + part["material"], colour) if VINYL
                                     else terry_material("terry:" + part["material"], colour))
            made.append(ob)
        return
    # the pile is short round what is sewn on it (stitching, felt, beads) and flat under a patch of another cloth
    features = kdtree.KDTree(sum(len(v) for v, _f in other.values()) or 1)
    k = 0
    for verts, _faces in other.values():
        for v in verts:
            features.insert(v, k)
            k += 1
    features.balance()
    grids = {part["id"]: grid(part) for part in furry}
    main = {}                                                   # each figure's own fur: the material on its body
    for part in furry:
        if part["name"] == "body/body":
            main[part["figure"]] = part["material"]
    patches = [v for part in furry if part["material"] != main.get(part["figure"]) for v in grids[part["id"]][0]]
    cover = kdtree.KDTree(len(patches) or 1)
    for j, v in enumerate(patches):
        cover.insert(v, j)
    cover.balance()
    for part in furry:
        verts, faces = grids[part["id"]]
        ob = mesh_object(part["id"], verts, faces)
        colour = srgb(part["colour"])
        ob.data.materials.append(principled("cloth:" + part["material"], [c * 0.75 for c in colour[:3]] + [1], rough=1.0, sheen=0.4))
        ob.data.materials.append(pile_material("pile:" + part["material"], colour))
        vg = ob.vertex_groups.new(name="pile")
        under = bool(patches) and part["material"] == main.get(part["figure"])
        for v in ob.data.vertices:
            w = max(0.0, min(1.0, (features.find(v.co)[2] - 0.004) / 0.022))
            if under:
                w = min(w, max(0.0, min(1.0, (cover.find(v.co)[2] - 0.012) / 0.02)))
            vg.add([v.index], w, "REPLACE")
        area = sum(p.area for p in ob.data.polygons)
        ps = bpy.data.particles.new(part["id"])
        ps.type = "HAIR"
        ps.count = max(40, int(area * 42000 * opt["density"]))
        ps.hair_step = ps.display_step = ps.render_step = 3
        ps.emit_from, ps.use_emit_random = "FACE", True
        unit = part.get("pile", 0.0075) / 4.0       # in Blender a hair's length is its emission velocity times four
        ps.normal_factor, ps.tangent_factor, ps.tangent_phase = unit, 0.35 * unit, 0.25
        ps.factor_random, ps.brownian_factor = 0.2 * unit, 0.0
        ps.child_type = "INTERPOLATED"
        ps.rendered_child_count, ps.child_percent, ps.child_length = int(opt["children"]), 4, 1.0
        ps.clump_factor = 0.12
        ps.roughness_1, ps.roughness_1_size, ps.roughness_endpoint, ps.roughness_2 = 0.0015, 0.01, 0.002, 0.001
        ps.root_radius, ps.tip_radius, ps.radius_scale = 0.42, 0.12, 0.0012 * opt["radius"]
        ps.material = 2
        mod = ob.modifiers.new("pile", "PARTICLE_SYSTEM")
        mod.particle_system.settings = ps
        mod.particle_system.vertex_group_length = "pile"
        mod.particle_system.seed = zlib.crc32(part["id"].encode()) % 100000     # the same hairs on every frame
        made.extend([ob, ps])


# ---- the studio, once: a sweep of warm paper, a big soft key from the upper left, a fill, a rim
verts, n = [], 24
for i in range(n + 1):
    a = math.pi / 2 * i / n
    verts += [(-12, 1.6 + 0.9 * math.sin(a), 0.9 - 0.9 * math.cos(a)), (12, 1.6 + 0.9 * math.sin(a), 0.9 - 0.9 * math.cos(a))]
verts = [(-12, -12, 0), (12, -12, 0)] + verts + [(-12, 2.5, 12), (12, 2.5, 12)]
mesh = bpy.data.meshes.new("sweep")
mesh.from_pydata(verts, [], [[2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2] for i in range(len(verts) // 2 - 1)])
sweep = bpy.data.objects.new("sweep", mesh)
scene.collection.objects.link(sweep)
for p in mesh.polygons:
    p.use_smooth = True
sweep.data.materials.append(principled("paper", srgb(opt.get("backdrop", "#FDECD9" if LOWPOLY else "#F6EADC" if VINYL else "#C9B49C")), rough=0.95))
for name, at, size, power, colour in (("key", (-1.6, -1.5, 1.9), 1.6, 190, (1.0, 0.93, 0.82)),
                                      ("fill", (1.8, -1.6, 0.9), 2.2, 30, (0.86, 0.92, 1.0)),
                                      ("rim", (1.1, 1.0, 1.5), 0.8, 110, (1.0, 0.9, 0.78))):
    if LOWPOLY:      # low poly is lit by its own lamps, below
        break
    light = bpy.data.lights.new(name, "AREA")
    light.shape, light.size, light.energy, light.color = "DISK", size, power, colour
    ob = bpy.data.objects.new(name, light)
    ob.location = at
    ob.rotation_euler = (Vector((0, 0, 0.45)) - Vector(at)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(ob)
figure = floor_only = None
if LOWPOLY:
    # The facets are told apart by light, so the light has a side: one key from the upper left of the picture, low
    # enough to rake the facets and small enough to cast the figure's shadow on itself (a sleeve on an arm, a
    # collar on a chest); a weak cool fill from the other side, a rim behind, and a warm bounce from below the
    # front, as a pale floor gives. Those three cast no shadow. The lamps stand far and are large, so the light
    # is even from head to foot. None of them lights the floor: the one shadow on it is a wide lamp's straight
    # overhead, the soft dark patch a figure stands in on a model sheet (that lamp lights nothing but the floor).
    figure, floor_only = bpy.data.collections.new("figure"), bpy.data.collections.new("floor")
    lamp = lambda name, default: [float(x) for x in opt.get(name, default)]
    for name, (turn, rise, far, size, power, r, g, b), shadow in (
            ("key", lamp("key", (-35, 48, 9.0, 2.4, 2000, 1.0, 0.97, 0.92)), True),
            ("fill", lamp("fill", (50, 12, 9.0, 6.0, 110, 0.93, 0.96, 1.0)), False),
            ("rim", lamp("rim", (150, 50, 8.0, 2.0, 500, 1.0, 0.95, 0.89)), False),
            ("bounce", lamp("bounce", (8, -38, 6.0, 5.0, 100, 1.0, 0.86, 0.72)), False)):
        light = bpy.data.lights.new(name, "AREA")
        light.shape, light.size, light.energy, light.color = "DISK", size, power, (r, g, b)
        light.use_shadow = shadow
        if hasattr(light, "cycles") and hasattr(light.cycles, "cast_shadow"):
            light.cycles.cast_shadow = shadow
        ob = bpy.data.objects.new(name, light)
        a, e = math.radians(turn), math.radians(rise)            # round from the camera's side, and up
        ob.location = (far * math.sin(a) * math.cos(e), -far * math.cos(a) * math.cos(e), 0.5 + far * math.sin(e))
        ob.rotation_euler = (Vector((0, 0, 0.5)) - ob.location).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(ob)
        ob.light_linking.receiver_collection = figure
    top = bpy.data.lights.new("top", "AREA")
    top.shape, top.size, top.energy, top.color = "DISK", 2.6, float(opt.get("top", 620.0)), (1.0, 0.98, 0.95)
    ob = bpy.data.objects.new("top", top)
    ob.location = (0.0, 0.0, 6.0)
    scene.collection.objects.link(ob)
    ob.light_linking.receiver_collection = floor_only
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.42, 0.34, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.12
if LOWPOLY:      # a little warm light from everywhere: what the lamps leave in shade is dark, not black
    world.node_tree.nodes["Background"].inputs[0].default_value = (1.0, 0.95, 0.9, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = float(opt.get("sky", 0.1))
scene.world = world

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
if meta.get("gate", "vertical") == "vertical":
    cam.data.sensor_fit, cam.data.sensor_height = "VERTICAL", 24.0
else:
    cam.data.sensor_fit, cam.data.sensor_width = "HORIZONTAL", 36.0
cam.data.dof.use_dof, cam.data.dof.aperture_fstop = not LOWPOLY, float(opt.get("fstop", 9.0 if VINYL else 4.0))   # low poly is drawn sharp
scene.collection.objects.link(cam)
scene.camera = cam

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
device = str(opt["device"]).upper()
if device != "CPU":
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = device
    prefs.get_devices()
    found = False
    for d in prefs.devices:
        d.use = d.type == device
        found = found or d.use
    if found:
        scene.cycles.device = "GPU"
    else:
        print(f"FRAMES no {device} device: rendering on the CPU", flush=True)
        device = "CPU"
scene.cycles.samples, scene.cycles.use_adaptive_sampling, scene.cycles.use_denoising = int(opt["samples"]), False, True
scene.cycles.denoiser = "OPTIX" if device == "OPTIX" else "OPENIMAGEDENOISE"
if LOWPOLY:      # flat facets need few samples to settle, and a denoiser softens their edges: draw more, denoise nothing
    scene.cycles.samples, scene.cycles.use_denoising = max(96, int(opt["samples"]) * 3), False
scene.cycles.max_bounces, scene.cycles.diffuse_bounces, scene.cycles.glossy_bounces = 5, 2, 2
scene.cycles.transmission_bounces, scene.cycles.transparent_max_bounces = 4, 4
scene.cycles_curves.shape = "RIBBONS"                      # flat ribbons: far cheaper than round strands
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.resolution_percentage = int(float(opt["scale"]) * 100)
scene.view_settings.view_transform, scene.view_settings.look = "AgX", "AgX - Medium High Contrast"
if LOWPOLY:    # flat colour as it was chosen: no film curve over it
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"
    scene.view_settings.exposure = float(opt.get("exposure", -0.95))
elif VINYL:      # a toy's colours are saturated and its light even: less exposure, a punchier curve
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = float(opt.get("exposure", -0.3))
scene.render.image_settings.file_format = "PNG"
if LOWPOLY:      # the figure and its shadow over one flat colour, as on a model sheet: the backdrop only catches shadow
    sweep.hide_render = True             # no wall behind: a flat floor alone, so only the figure's own shadow shows
    floor_mesh = bpy.data.meshes.new("floor")
    floor_mesh.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [[0, 1, 2, 3]])
    floor = bpy.data.objects.new("floor", floor_mesh)
    scene.collection.objects.link(floor)
    floor_only.objects.link(floor)
    floor.is_shadow_catcher = True
    # it catches the shadow and gives nothing back: the light a pale floor throws up is the `bounce` lamp's, which
    # can be set; left to the floor it is as strong as the key and lights every facet alike from below
    floor.visible_diffuse = floor.visible_glossy = False
    scene.render.film_transparent = True
    if opt.get("alpha"):
        # A cutout for another film (characters.bridge): the film stays transparent and the frame is written with
        # its alpha, straight (PNG's own). No backdrop is laid under it, so no backdrop colour is mixed into the
        # figure's edge; the floor is still there as a shadow catcher, and the figure's shadow on the ground is
        # black with the alpha of how dark it is. No dither: it puts noise in the colour of clear pixels, which
        # nothing sees and which made a frame nine times the bytes (919 KiB against 96 for one figure in 1080x1920).
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.dither_intensity = 0.0
    else:
        scene.use_nodes = True
        tree = scene.node_tree
        tree.nodes.clear()
        layers, over, out = (tree.nodes.new(n) for n in ("CompositorNodeRLayers", "CompositorNodeAlphaOver", "CompositorNodeComposite"))
        gain = 2.0 ** -scene.view_settings.exposure                 # the exposure is applied after this: undo it here
        over.inputs[1].default_value = [c * gain for c in srgb(opt.get("backdrop", "#FDECD9"))[:3]] + [1.0]
        tree.links.new(layers.outputs["Image"], over.inputs[2])
        tree.links.new(over.outputs["Image"], out.inputs["Image"])
        scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.compression = 15

dst.mkdir(parents=True, exist_ok=True)
todo = [f for f in files if not (dst / f"{f.stem}.png").exists()]
print(f"FRAMES {len(todo)} of {len(files)} to draw, {opt['finish']} on {device}", flush=True)
t0 = time.time()
for done, f in enumerate(todo, 1):
    data = json.loads(f.read_text())
    clear()
    build(data)
    c = data["camera"]
    eye, aim = Vector(to_blender(c["eye"])), Vector(to_blender(c["look_at"]))
    cam.location = eye
    cam.rotation_euler = (aim - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = c["lens"]
    cam.data.dof.focus_distance = c["focus"]
    scene.render.filepath = str(dst / f"{f.stem}.png")
    bpy.ops.render.render(write_still=True)
    if done <= 2 or done % 24 == 0 or done == len(todo):
        each = (time.time() - t0) / done
        print(f"FRAMES {done}/{len(todo)}: {each:.1f} s a frame, {each * (len(todo) - done) / 60:.0f} min left", flush=True)
print(f"FRAMES done in {(time.time() - t0) / 60:.1f} min", flush=True)
