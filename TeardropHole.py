# TeardropHole.py
#
# Fusion 360 Add-In that adds a "Teardrop-Loch" button to the Modify panel
# (Solid workspace). It turns a selected round hole into a "teardrop" hole:
# it replaces the top of the circular cross-section with two straight walls
# that meet in a point, so every wall stays at or below your printer's safe
# overhang angle (45 degrees by default) - no support material needed for
# holes with a horizontal axis when 3D printing (FDM).
#
#   _____              ^
#  /     \     -->     /|\      (pointed top, safe overhang angle)
# |       |           /   \
#  \_____/            |   |     (circle continues as before)
#                       \_/
#
# INSTALL
#   Copy this whole "TeardropHole" folder (containing this .py file and the
#   matching .manifest file) into Fusion 360's Scripts and Add-Ins dialog
#   the same way as any script/add-in (Shift+S -> "+" -> select this
#   folder). It will show up under "Alle Skripte und Zusatzmodule" with a
#   toggle switch (it's an Add-In, not a one-shot script). Turn the switch
#   on - a "Teardrop-Loch" button then appears in the SOLID tab, MODIFY
#   panel, for as long as the Add-In is enabled. Check "Beim Start
#   ausführen" if you want the button to always be there.
#
# USE
#   Click "Teardrop-Loch", pick one or more cylindrical hole faces, set the
#   overhang angle (45 is the standard safe value for FDM), click OK. If
#   "up" in your model isn't the global Z axis, pick a straight edge that
#   points the way you want the teardrop's point to extend (e.g. an edge
#   running along the print's vertical build direction) in the "Oben-
#   Richtung" field - otherwise it defaults to global Z. Tick "Ausgeschnit-
#   tenes Stück (Dreieck) als Körper behalten" if you also want the little
#   wedge-shaped piece that gets cut off kept as its own separate body,
#   optionally shrunk by a "Spiel" (clearance) allowance so it fits back
#   into the real hole with some play as a printed test plug.
#
# NOTES / LIMITATIONS
#   - Works on cylindrical faces belonging to a solid body.
#   - Intended for holes whose axis is roughly horizontal relative to
#     "up". A hole whose axis points straight along "up"/"down" already
#     prints fine as a plain circle and will be skipped with a message.
#   - Works for through-holes as well as blind holes (Sacklöcher) - flat-
#     bottomed or pointed. Depth is auto-detected from the selected
#     hole's own geometry unless you enter an explicit "Lochtiefe" value.
#     If there's no real hole there yet (still solid material), leave the
#     depth field at 0 and it cuts generously through the whole part.
#   - Needs an existing flat wall face right next to the hole to sketch
#     on. Also needs recorded design history (Chronik) if no such
#     adjacent flat face exists, since building a construction plane
#     without one requires it.
#   - For a through-hole with such a face on both ends, the one currently
#     facing the camera (i.e. the side you're looking at when you run the
#     command) is used - so an explicit "Lochtiefe" is measured going
#     into the part from the visible side, not from the far end.
#   - Each converted hole adds a sketch (and, in documents without a
#     recorded design history, possibly a construction plane, and a
#     construction point if "als Körper behalten" + clearance was used)
#     to the timeline/browser tree. That's normal - Fusion needs it to
#     build the cut.

import adsk.core
import adsk.fusion
import math
import traceback

VERSION = '2.6.3-debug'

CMD_ID = 'TeardropHoleCmd'
CMD_NAME = 'Teardrop-Loch'
CMD_DESCRIPTION = ('Wandelt runde Lochflächen in Tränenform um, damit sie '
                    'beim 3D-Druck ohne Stützmaterial auskommen.')
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidModifyPanel'
COMMAND_BESIDE_ID = ''

_app = None
_ui = None
_handlers = []
_debug_lines = []


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        cmd_defs = _ui.commandDefinitions
        existing = cmd_defs.itemById(CMD_ID)
        if existing:
            existing.deleteMe()
        cmd_def = cmd_defs.addButtonDefinition(CMD_ID, CMD_NAME, CMD_DESCRIPTION, '')

        on_created = CommandCreatedHandler()
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)

        workspace = _ui.workspaces.itemById(WORKSPACE_ID)
        panel = workspace.toolbarPanels.itemById(PANEL_ID)
        control = panel.controls.itemById(CMD_ID)
        if not control:
            control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)
            control.isPromoted = True
            control.isPromotedByDefault = True
    except Exception:
        if _ui:
            _ui.messageBox('TeardropHole konnte nicht gestartet werden:\n{}'.format(traceback.format_exc()))


def stop(context):
    try:
        workspace = _ui.workspaces.itemById(WORKSPACE_ID)
        panel = workspace.toolbarPanels.itemById(PANEL_ID)
        control = panel.controls.itemById(CMD_ID)
        if control:
            control.deleteMe()
        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
    except Exception:
        if _ui:
            _ui.messageBox('TeardropHole konnte nicht sauber beendet werden:\n{}'.format(traceback.format_exc()))


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            selection_input = inputs.addSelectionInput(
                'faces', 'Lochflächen',
                'Wähle eine oder mehrere zylindrische Lochflächen aus')
            selection_input.setSelectionLimits(1, 0)
            try:
                selection_input.addSelectionFilter('CylindricalFaces')
            except Exception:
                selection_input.addSelectionFilter('Faces')

            up_input = inputs.addSelectionInput(
                'upEdge', 'Oben-Richtung (optional)',
                'Optional: eine gerade Kante anklicken, die in deinem Modell nach '
                '"oben" (Druckrichtung) zeigt. Leer lassen = globale Z-Achse.')
            up_input.setSelectionLimits(0, 1)
            up_input.addSelectionFilter('LinearEdges')
            up_input.isEnabled = True

            default_angle = adsk.core.ValueInput.createByReal(math.radians(45.0))
            inputs.addValueInput('angle', 'Überhangwinkel (von der Vertikalen)', 'deg', default_angle)

            default_depth = adsk.core.ValueInput.createByReal(0.0)
            depth_input = inputs.addValueInput(
                'depth', 'Lochtiefe (0 = automatisch erkennen)', 'mm', default_depth)
            depth_input.tooltip = (
                'Wie tief das Loch werden soll. 0 = automatisch erkennen (an der '
                'Tiefe des ausgewählten Lochs, falls vorhanden, sonst durch das '
                'ganze Bauteil). Trage einen Wert ein, wenn du z.B. ein Sackloch '
                'mit fester Tiefe willst.')

            cutout_input = inputs.addBoolValueInput(
                'keepCutout', 'Ausgeschnittenes Stück (Dreieck) als Körper behalten', True, '', False)
            cutout_input.tooltip = (
                'Erstellt das kleine, keilförmige Stück, das oben abgeschnitten wird, '
                'zusätzlich als eigenen (separaten) Körper - z.B. zum Ansehen oder '
                'Weiterverwenden. Der Schnitt am Loch selbst passiert trotzdem ganz normal.')

            default_clearance = adsk.core.ValueInput.createByReal(0.01)  # 0.1 mm in cm
            clearance_input = inputs.addValueInput(
                'clearance', 'Spiel (Ausschnitt-Körper kleiner)', 'mm', default_clearance)
            clearance_input.tooltip = (
                'Nur relevant, wenn oben "als Körper behalten" angehakt ist: um wie '
                'viel der separate Körper rundum kleiner gemacht wird, damit er beim '
                'FDM-Druck als Testeinsatz mit etwas Spiel in das echte Loch passt. '
                '0.1 mm ist ein üblicher Startwert - je nach Drucker/Kalibrierung '
                'anpassen.')

            on_execute = CommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_destroy = CommandDestroyHandler()
            cmd.destroy.add(on_destroy)
            _handlers.append(on_destroy)
        except Exception:
            if _ui:
                _ui.messageBox('Fehler beim Aufbau des Dialogs:\n{}'.format(traceback.format_exc()))


class CommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        pass


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            selection_input = inputs.itemById('faces')
            up_input = inputs.itemById('upEdge')
            angle_input = inputs.itemById('angle')
            depth_input = inputs.itemById('depth')
            cutout_input = inputs.itemById('keepCutout')
            clearance_input = inputs.itemById('clearance')
            angle_rad = angle_input.value  # already in radians (internal unit)
            depth_override = depth_input.value  # cm (internal unit), 0 = auto
            keep_cutout = cutout_input.value if cutout_input else False
            clearance = clearance_input.value if clearance_input else 0.0  # cm

            if not (0.0 < angle_rad < math.radians(90.0)):
                _ui.messageBox('Der Überhangwinkel muss zwischen 0 und 90 Grad liegen.')
                return

            up_vector = adsk.core.Vector3D.create(0.0, 0.0, 1.0)
            if up_input.selectionCount > 0:
                up_edge = adsk.fusion.BRepEdge.cast(up_input.selection(0).entity)
                start_pt = up_edge.startVertex.geometry
                end_pt = up_edge.endVertex.geometry
                up_vector = start_pt.vectorTo(end_pt)
            up_vector.normalize()

            faces = [selection_input.selection(i).entity for i in range(selection_input.selectionCount)]

            processed = 0
            errors = []
            _debug_lines.clear()
            for face in faces:
                face = adsk.fusion.BRepFace.cast(face)
                try:
                    if make_teardrop_hole(face, angle_rad, up_vector, depth_override, keep_cutout, clearance):
                        processed += 1
                except Exception:
                    errors.append(traceback.format_exc())

            debug_text = '\n'.join(_debug_lines)
            if errors:
                _ui.messageBox('[v{}] {} von {} Loch/Löchern umgewandelt.\n\nFehler bei den restlichen:\n{}\n\nDEBUG:\n{}'.format(
                    VERSION, processed, len(faces), '\n---\n'.join(errors), debug_text))
            elif processed:
                _ui.messageBox('[v{}] {} Loch/Löcher in Tränenform umgewandelt.\n\nDEBUG:\n{}'.format(
                    VERSION, processed, debug_text))
        except Exception:
            if _ui:
                _ui.messageBox('Ausführung fehlgeschlagen:\n{}'.format(traceback.format_exc()))


def make_teardrop_hole(face, angle_rad, up_world, depth_override=0.0, keep_cutout=False, clearance=0.0):
    """Replace the round hole represented by `face` with a teardrop shape.
    `up_world` is the direction the point of the teardrop should extend
    towards (a normalized Vector3D in the document's root/world space).
    `depth_override`, in cm (Fusion's internal unit), is how deep to cut;
    0 or less means auto-detect from the selected hole's own geometry.
    `keep_cutout`, if True, also creates the small wedge-shaped piece that
    gets cut off as its own separate body, in addition to doing the cut.
    `clearance`, in cm, shrinks that separate body uniformly (a fit
    allowance for using it as a printed test plug) - only used if
    `keep_cutout` is True.
    Returns True if a cut was made, False if the selection was skipped."""

    geom = face.geometry
    if not isinstance(geom, adsk.core.Cylinder):
        _ui.messageBox('Eine ausgewählte Fläche ist nicht zylindrisch - übersprungen.')
        return False

    body = face.body
    comp = body.parentComponent
    radius = geom.radius

    # Find every full circular edge of the selected face, and, for each,
    # whichever flat wall face (if any) borders it - a through-hole has
    # one such pair at each end. The circle edge and the wall face we
    # sketch on MUST come from the SAME pair: picking a wall face facing
    # the camera while still computing the teardrop's geometry from a
    # DIFFERENT (unrelated) circle would place the sketch nowhere near
    # that face, producing nonsense (huge, misplaced cuts).
    pairs = []
    for edge in face.edges:
        edge_geom = edge.geometry
        if not isinstance(edge_geom, adsk.core.Circle3D):
            continue
        neighbor = None
        for other_face in edge.faces:
            if other_face == face:
                continue
            if isinstance(other_face.geometry, adsk.core.Plane):
                neighbor = other_face
                break
        pairs.append((edge, edge_geom, neighbor))

    if not pairs:
        _ui.messageBox('Auf einer Fläche wurde keine volle Kreiskante gefunden - übersprungen.')
        return False

    pairs_with_host = [p for p in pairs if p[2] is not None]
    n_pairs_with_host_raw = len(pairs_with_host)

    # A blind hole's flat BOTTOM is also a planar neighbor of its bottom
    # circular edge - but it's a bare disk face whose only boundary is
    # that same circle, not a real wall. Looking straight down into the
    # hole, that bottom disk's outward normal points back out toward the
    # camera too (often even more directly than the true opening), which
    # made the camera-facing test above pick the BOTTOM as the sketch
    # host - placing the teardrop at the bottom of the hole and, since
    # the auto-detected depth then gets cut again from there, punching
    # a blind hole into a through-hole. A real wall face has more than
    # just the hole's own circle as its boundary, so prefer those.
    def is_bare_disk(f):
        try:
            return f.edges.count <= 1
        except Exception:
            return False

    real_wall_pairs = [p for p in pairs_with_host if not is_bare_disk(p[2])]
    if real_wall_pairs:
        pairs_with_host = real_wall_pairs

    chosen = None
    if len(pairs_with_host) == 1:
        chosen = pairs_with_host[0]
    elif len(pairs_with_host) > 1:
        # A through-hole usually has such a pair at BOTH ends - of those,
        # pick the one whose wall face currently faces the camera (i.e.
        # the side you're actually looking at), so an explicit "Lochtiefe"
        # is measured going into the part from that visible face.
        try:
            eye = _app.activeViewport.camera.eye
            best_score = None
            for pair in pairs_with_host:
                neighbor = pair[2]
                try:
                    point_on_face = neighbor.pointOnFace
                    ok, normal = neighbor.evaluator.getNormalAtPoint(point_on_face)
                    if not ok:
                        continue
                    to_eye = point_on_face.vectorTo(eye)
                    if to_eye.length < 1e-9:
                        continue
                    to_eye.normalize()
                    score = normal.dotProduct(to_eye)
                except Exception:
                    continue
                if best_score is None or score > best_score:
                    best_score = score
                    chosen = pair
        except Exception:
            chosen = None
        if chosen is None:
            chosen = pairs_with_host[0]
    else:
        # No circular edge has an adjacent flat wall face at all - use the
        # first circle found; a construction plane will be built for it
        # further down.
        chosen = pairs[0]

    hole_edge, circle_edge, sketch_host = chosen

    _debug_lines.append(
        'host: kreiskanten={} davon_mit_wand={} nach_bare_disk_filter={} '
        'sketch_host_kanten={} kreis_mitte=({:.4f}, {:.4f}, {:.4f})'.format(
            len(pairs), n_pairs_with_host_raw, len(pairs_with_host),
            (sketch_host.edges.count if sketch_host is not None else -1),
            circle_edge.center.x, circle_edge.center.y, circle_edge.center.z))

    center = circle_edge.center
    axis = circle_edge.normal
    axis.normalize()

    up_world = up_world.copy()
    up_world.normalize()

    dot = up_world.dotProduct(axis)
    along_axis = axis.copy()
    along_axis.scaleBy(dot)
    up_in_plane = up_world.copy()
    up_in_plane.subtract(along_axis)

    if up_in_plane.length < 1e-6:
        _ui.messageBox("Ein Loch hat eine zur UP_VECTOR-Richtung parallele Achse (senkrechtes "
                        "Loch) - das druckt schon als Kreis problemlos und braucht keine "
                        "Tränenform. Übersprungen.")
        return False
    up_in_plane.normalize()

    right_in_plane = axis.crossProduct(up_in_plane)
    right_in_plane.normalize()

    def point_at(u, v):
        p = center.copy()
        r = right_in_plane.copy()
        r.scaleBy(u)
        p.translateBy(r)
        uv = up_in_plane.copy()
        uv.scaleBy(v)
        p.translateBy(uv)
        return p

    sin_a = math.sin(angle_rad)
    cos_a = math.cos(angle_rad)

    p_right = point_at(radius * sin_a, radius * cos_a)
    p_left = point_at(-radius * sin_a, radius * cos_a)
    p_apex = point_at(0.0, radius / cos_a)
    p_bottom = point_at(0.0, -radius)

    # sketch_host was already picked above, paired with this same
    # circle_edge/hole_edge. If none of the hole's circular edges had an
    # adjacent flat wall face, fall back to building a construction plane
    # through 3 points on THIS circle. Only works in documents with
    # design history enabled.
    if sketch_host is None:
        p3a = point_at(radius, 0.0)
        p3b = point_at(-radius * 0.5, radius * 0.8660254037844386)
        p3c = point_at(-radius * 0.5, -radius * 0.8660254037844386)

        try:
            cps = comp.constructionPoints
            construction_points = []
            for pt in (p3a, p3b, p3c):
                cp_input = cps.createInput()
                cp_input.setByPoint(pt)
                construction_points.append(cps.add(cp_input))

            plane_input = comp.constructionPlanes.createInput()
            plane_input.setByThreePoints(construction_points[0], construction_points[1], construction_points[2])
            sketch_host = comp.constructionPlanes.add(plane_input)
        except Exception:
            _ui.messageBox(
                'Für dieses Loch gibt es keine angrenzende ebene Fläche, und '
                'Konstruktionsebenen lassen sich in diesem Dokument nicht per '
                'Skript anlegen (vermutlich läuft es ohne Verlauf/Chronik - '
                'Direktmodus). Bitte "Konstruktionsverlauf aufzeichnen" für '
                'dieses Dokument aktivieren, oder ein Loch wählen, das direkt '
                'an eine ebene Wandfläche grenzt.')
            return False

    sketch = comp.sketches.add(sketch_host)
    sketch.name = 'Teardrop hole sketch'

    s_right = sketch.modelToSketchSpace(p_right)
    s_left = sketch.modelToSketchSpace(p_left)
    s_apex = sketch.modelToSketchSpace(p_apex)
    s_bottom = sketch.modelToSketchSpace(p_bottom)

    lines = sketch.sketchCurves.sketchLines

    # Project the real, existing circular edge into the sketch instead of
    # drawing a brand new arc on top of it. Two curves that nearly (but not
    # exactly) coincide confuse Fusion's profile finder - it can end up
    # treating them as separate overlapping regions instead of one clean
    # circle, which is what caused the wrong (missing point, or tiny
    # sliver-only) shapes in earlier attempts. Projecting reuses the real
    # edge as a single, unambiguous curve.
    projected_ok = False
    try:
        projected = sketch.project(hole_edge)
        if projected.count > 0 and isinstance(projected.item(0), adsk.fusion.SketchCircle):
            projected_ok = True
    except Exception:
        projected_ok = False

    if not projected_ok:
        # Fallback: draw our own arc, reusing ITS OWN endpoints for the two
        # lines (not just matching coordinates) so there is a real shared
        # vertex between them.
        arcs = sketch.sketchCurves.sketchArcs
        arc = arcs.addByThreePoints(s_right, s_bottom, s_left)
        lines.addByTwoPoints(arc.endSketchPoint, s_apex)
        lines.addByTwoPoints(s_apex, arc.startSketchPoint)
    else:
        lines.addByTwoPoints(s_left, s_apex)
        lines.addByTwoPoints(s_apex, s_right)

    if sketch.profiles.count == 0:
        _ui.messageBox('Für ein Loch konnte kein geschlossenes Profil erzeugt werden - übersprungen.')
        return False

    # Fusion refuses to split the (projected) circle into two arcs at the
    # tangent points just because two line endpoints sit exactly on it - it
    # keeps offering the full, untouched circle as its own closed profile
    # no matter what. Trying to find a single "big disk + point" profile
    # therefore never works. Instead of fighting that, use it: cut the
    # round part and the point as TWO separate profiles instead of one -
    # (1) the plain circle (already reliably present as its own profile -
    # a no-op if that area is already void, i.e. an existing hole) and
    # (2) the little "spike" cap bounded by the two tangent lines and the
    # short arc between them, which is reliably formed as its own profile
    # too and is exactly the extra sliver of material that turns a plain
    # round hole into a teardrop.
    theta_minor = 2.0 * angle_rad
    segment_area = 0.5 * radius * radius * (theta_minor - math.sin(theta_minor))
    circle_area = math.pi * radius * radius
    base = 2.0 * radius * sin_a
    tri_height = (radius / cos_a) - radius * cos_a
    triangle_area = 0.5 * base * tri_height
    cap_area = triangle_area - segment_area

    candidates = []
    for i in range(sketch.profiles.count):
        candidate = sketch.profiles.item(i)
        candidates.append((candidate, candidate.areaProperties().area))

    def pick_closest(target, exclude=None):
        best = None
        best_diff = None
        for candidate, area in candidates:
            if exclude is not None and candidate == exclude:
                continue
            diff = abs(area - target)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best = candidate
        return best

    profile_circle = pick_closest(circle_area)
    profile_cap = pick_closest(cap_area, exclude=profile_circle)

    if profile_circle is None or profile_cap is None:
        _ui.messageBox('Für ein Loch konnten nicht beide Teilflächen (Rundung + Spitze) '
                        'gefunden werden - übersprungen.')
        return False

    # How deep to cut: an explicit value wins if given. Otherwise, try to
    # auto-detect from the selected hole's own geometry.
    if depth_override and depth_override > 1e-6:
        hole_depth = depth_override
        auto_detected = False
    else:
        auto_detected = True
        hole_depth = None
        precise_depth = False

        # Best method: read the actual trimmed length of the selected
        # cylindrical FACE itself along its own axis, straight from its
        # surface parametrization. This works no matter how the far end of
        # the hole is shaped - a flat blind-hole bottom, a drill-style
        # conical tip, or a clean through-hole - because it measures the
        # real face, not a second circular edge that might not exist (a
        # conical tip has no circular edge at all, which is what silently
        # made blind holes with a pointed bottom fall through to the "cut
        # generously through the whole body" fallback below and come out
        # as a through-hole instead of staying blind).
        try:
            evaluator = face.evaluator
            ok, param_box = evaluator.getParametricExtents()
            if ok:
                v_len = abs(param_box.maxPoint.y - param_box.minPoint.y)
                if v_len > 1e-6:
                    hole_depth = v_len
                    precise_depth = True
        except Exception:
            hole_depth = None

        if hole_depth is None:
            # Fallback: distance between two circular edges of the face
            # (works for a simple flat-bottomed blind hole or a
            # through-hole with rims on both ends).
            circle_centers = []
            for edge in face.edges:
                edge_geom = edge.geometry
                if isinstance(edge_geom, adsk.core.Circle3D):
                    circle_centers.append(edge_geom.center)
            if len(circle_centers) >= 2:
                hole_depth = max(circle_centers[0].distanceTo(c) for c in circle_centers[1:])
                precise_depth = True

        if hole_depth is None:
            # Last resort: nothing to measure against (e.g. there was no
            # real hole there yet) - cut generously through the whole body
            # so the result is at least a valid through-hole.
            bbox = body.boundingBox
            hole_depth = bbox.minPoint.distanceTo(bbox.maxPoint)
            if hole_depth < radius * 10.0:
                hole_depth = radius * 10.0
            precise_depth = False

    # A small margin used to be added here so the cut fully clears the far
    # end instead of leaving a paper-thin uncut sliver there. That's fine
    # for a generous "no real hole yet, cut through the whole body" guess -
    # but for a hole whose depth was PRECISELY measured (an existing blind
    # or through hole), it means deliberately cutting a bit past that real,
    # measured end - which, for a blind hole, is exactly the remaining
    # material behind it. That margin is what turned auto-detected blind
    # holes into through-holes. So: no margin when the depth came from a
    # precise measurement (auto-detected on a real hole, or an explicit
    # value you typed in) - only the generous last-resort guess still gets
    # one, since there it's cutting through open-ended, not-yet-hollow
    # material anyway.
    if (depth_override and depth_override > 1e-6) or precise_depth:
        safe_len = hole_depth
    else:
        safe_len = hole_depth * 1.02

    _debug_lines.append(
        'depth: override={:.4f}cm auto_detected={} precise_depth={} hole_depth={:.4f}cm safe_len={:.4f}cm'.format(
            depth_override, auto_detected, precise_depth if auto_detected else 'n/a', hole_depth, safe_len))

    extrudes = comp.features.extrudeFeatures
    distance = adsk.core.ValueInput.createByReal(safe_len)

    cutout_body = None

    if keep_cutout:
        # Extrude the little wedge-shaped cap profile as its own new body
        # (same shape as the real cut's own profile_cap - proven reliable),
        # before the real cut below consumes that same profile.
        #
        # One-sided, into the material only, using the real hole depth -
        # NOT a symmetric extent split half-and-half around the sketch
        # plane. Symmetric is fine for the CUT tool below (the half that
        # lands in open air in front of the face just cuts nothing there),
        # but for this KEPT body it means it pokes out of the wall by half
        # its length. Which of the two possible one-sided directions is
        # "into the material" is worked out by comparing the sketch's own
        # normal against the hosting wall face's true outward-facing
        # normal (from its evaluator, not just its raw plane geometry,
        # which isn't reliably oriented outward).
        try:
            cutout_input = extrudes.createInput(profile_cap, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

            cutout_distance = hole_depth
            if isinstance(sketch_host, adsk.fusion.BRepFace):
                try:
                    ok, outward_normal = sketch_host.evaluator.getNormalAtPoint(sketch_host.pointOnFace)
                    sketch_normal = sketch.xDirection.crossProduct(sketch.yDirection)
                    if ok and sketch_normal.dotProduct(outward_normal) > 0:
                        # A positive distance would extrude outward (same
                        # way as the wall's own outward normal) - flip it.
                        cutout_distance = -cutout_distance
                except Exception:
                    pass
                cutout_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(cutout_distance))
            else:
                # No real wall face to read a direction from (construction-
                # plane fallback) - symmetric is the best we can do here,
                # at least with the correct total length instead of double.
                cutout_input.setSymmetricExtent(adsk.core.ValueInput.createByReal(cutout_distance), True)

            cutout_feature = extrudes.add(cutout_input)

            if cutout_feature.bodies.count > 0:
                cutout_body = cutout_feature.bodies.item(0)
                cutout_body.name = 'Teardrop-Ausschnitt'
            else:
                _debug_lines.append('keep_cutout: keine Koerper aus profile_cap erzeugt')
        except Exception:
            _debug_lines.append('keep_cutout fehlgeschlagen: {}'.format(traceback.format_exc()))

    try:
        # Preferred: both profiles cut together as one feature. This MUST
        # happen right after the cutout body above with nothing else
        # (like a sketch point or scale) inserted in between - any extra
        # feature there was found to invalidate profile_circle/profile_cap
        # and make this cut fail outright ("invalid profile(s)"). The
        # clearance scale-down further below, once the cut here is done,
        # doesn't have that problem since nothing still needs these two
        # profile references by then.
        profile_collection = adsk.core.ObjectCollection.create()
        profile_collection.add(profile_circle)
        profile_collection.add(profile_cap)
        extrude_input = extrudes.createInput(profile_collection, adsk.fusion.FeatureOperations.CutFeatureOperation)
        extrude_input.participantBodies = [body]
        extrude_input.setSymmetricExtent(distance, False)
        extrudes.add(extrude_input)
    except Exception:
        # Fallback: two separate cut features, one per profile.
        for prof in (profile_circle, profile_cap):
            extrude_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
            extrude_input.participantBodies = [body]
            extrude_input.setSymmetricExtent(distance, False)
            extrudes.add(extrude_input)

    if cutout_body is not None and clearance > 1e-6 and radius > 1e-6:
        # Shrink the cutout body uniformly by `clearance` (a "fits with
        # play" test-plug allowance) via a Scale about the hole's own
        # center point - done now, AFTER the real cut, so it can no
        # longer disturb profile_circle/profile_cap. An Offset Face on
        # every face of the body at once was tried first and fails
        # outright (Fusion needs at least one untouched reference face to
        # offset against, and the pointed tip would self-intersect
        # immediately besides) - Scale handles the pointed tip fine and
        # needs no such reference.
        try:
            scale_factor = 1.0 - (clearance / radius)
            if scale_factor < 0.05:
                # Clearance larger than the hole itself - keep a small,
                # sane minimum instead of an inverted/degenerate shape.
                scale_factor = 0.05

            # ScaleFeatureInput needs a real reference point entity
            # (vertex/sketch point), not a raw Point3D - "invalid ref
            # point" otherwise. A construction point would work too, but
            # comp.constructionPoints.add() needs a document with
            # recorded design history (Parametrik) and throws
            # "Environment is not supported" without one. A sketch point
            # added to the already-existing `sketch` sidesteps both
            # problems - sketch geometry works fine in this document
            # regardless, and by now nothing else still needs that
            # sketch's profiles.
            center_sketch_point = sketch.sketchPoints.add(sketch.modelToSketchSpace(center))

            body_collection = adsk.core.ObjectCollection.create()
            body_collection.add(cutout_body)

            scales = comp.features.scaleFeatures
            scale_input = scales.createInput(
                body_collection, center_sketch_point,
                adsk.core.ValueInput.createByReal(scale_factor))
            scales.add(scale_input)
        except Exception:
            _debug_lines.append('Spiel-Skalierung fehlgeschlagen: {}'.format(traceback.format_exc()))

    return True
