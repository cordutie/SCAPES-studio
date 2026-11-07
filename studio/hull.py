"""Left-plane geometry for the app: which point of the plane is selectable, with which weights, the mean at that
point, the zone of the placed dots and the closest point of the zone to a given point. Pure numpy and scipy for the
geometry. No UI.

Rules:
- 0 dots: nothing. 1 dot: only the dot.
- 2 dots, or 3 or more collinear dots: the segment between the two extreme dots.
- 3 or more non-collinear dots: the convex hull, triangulated by Delaunay.
- Snapping (locate): a dot within the dot tolerance wins; else a point within the edge tolerance of a hull
  boundary edge (or of the line) is projected onto it; else a point inside the hull uses its triangle.
- project_to_zone(p, dots) is the closest point of the zone to p, so the control point can be kept inside it.
Dots are given as a list with one entry per cluster (K entries, up to 32), each (x, y) or None;
indices refer to positions in that list. The mean inside a triangle is the nested slerp.
"""
import numpy as np
from scipy.spatial import ConvexHull, Delaunay


# spherical interpolation between unit vectors a and b at t in [0, 1]
def slerp(a, b, t):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    theta = np.arccos(np.clip(a @ b, -1.0, 1.0))
    if theta < 1e-6:
        return a
    sin_theta = np.sin(theta)
    return (np.sin((1 - t) * theta) / sin_theta) * a + (np.sin(t * theta) / sin_theta) * b


# snapping tolerances in plane units: 12 px (a dot) and 8 px (an edge) on the 520 px panel of [-1, 1]^2.
# These are the server's snap; the page's grab radius for a dot is 9 px (GRAB_PX in app.py)
DOT_TOL = 12 * 2 / 520
EDGE_TOL = 8 * 2 / 520


# distinct placed dots: indices (ascending) and positions; of two dots at the same place the lowest index wins
def unique_dots(dots):
    ids = []
    pts = []
    for i, d in enumerate(dots):
        if d is None:
            continue
        p = np.asarray(d, dtype=np.float64)
        if any(np.linalg.norm(p - q) < 1e-12 for q in pts):
            continue
        ids.append(i)
        pts.append(p)
    if not ids:
        return np.zeros(0, dtype=int), np.zeros((0, 2))
    return np.array(ids, dtype=int), np.array(pts)


# True if all the points (n, 2) lie on one line (n of 2 always does)
def is_collinear(pts):
    if len(pts) <= 2:
        return True
    X = pts - pts.mean(axis=0)
    s = np.linalg.svd(X, compute_uv=False)
    return bool(s[1] <= 1e-9 * max(s[0], 1e-300))


# the line through collinear points: centre, unit direction, and the order of the points along it
def line_order(pts):
    c = pts.mean(axis=0)
    direction = np.linalg.svd(pts - c)[2][0]
    t = (pts - c) @ direction
    order = np.argsort(t, kind="stable")
    return c, direction, order, t[order]


# weights for a point on a segment between two dots a < b, the point at fraction t from a towards b
def segment_result(ida, idb, t):
    lam = (1.0 - t, t)
    pairs = sorted(zip((int(ida), int(idb)), lam))
    return tuple(p[0] for p in pairs), tuple(float(p[1]) for p in pairs)


# which point of the plane is selectable: None, or (idx, lam) with idx ascending and lam summing to 1
def locate(p, dots, dot_tol, edge_tol):
    ids, pts = unique_dots(dots)
    if len(ids) == 0:
        return None
    p = np.asarray(p, dtype=np.float64)
    # 1. a dot within the dot tolerance (nearest one; the lowest index on a tie)
    dist = np.linalg.norm(pts - p, axis=1)
    k = int(np.argmin(dist))
    if dist[k] <= dot_tol:
        return (int(ids[k]),), (1.0,)
    if len(ids) == 1:
        return None
    # 2. two dots, or collinear dots: the segment between the two extremes
    if is_collinear(pts):
        c, direction, order, t_sorted = line_order(pts)
        tp = float((p - c) @ direction)
        perp = float(np.linalg.norm((p - c) - tp * direction))
        if perp > edge_tol or tp < t_sorted[0] or tp > t_sorted[-1]:
            return None
        # the two neighbouring dots along the line that bracket the point
        j = int(np.searchsorted(t_sorted, tp, side="right")) - 1
        j = min(max(j, 0), len(order) - 2)
        ta, tb = t_sorted[j], t_sorted[j + 1]
        t = (tp - ta) / (tb - ta)
        return segment_result(ids[order[j]], ids[order[j + 1]], float(np.clip(t, 0.0, 1.0)))
    # 3. non-collinear: a point within the edge tolerance of a hull boundary edge is projected onto it
    hull = ConvexHull(pts)
    best = None
    for a, b in hull.simplices:
        A, B = pts[a], pts[b]
        e = B - A
        t = float(np.clip((p - A) @ e / (e @ e), 0.0, 1.0))
        d = float(np.linalg.norm(p - (A + t * e)))
        if best is None or d < best[0]:
            best = (d, a, b, t)
    if best[0] <= edge_tol:
        _, a, b, t = best
        return segment_result(ids[a], ids[b], t)
    # 4. inside the hull: the triangle of the Delaunay triangulation, with barycentric weights
    tri = Delaunay(pts)
    k = int(tri.find_simplex(p[None])[0])
    if k < 0:
        return None
    T = tri.transform[k, :2]
    r = tri.transform[k, 2]
    b2 = T @ (p - r)
    lam = np.array([b2[0], b2[1], 1.0 - b2[0] - b2[1]])
    lam = np.clip(lam, 0.0, 1.0)
    lam = lam / lam.sum()
    verts = tri.simplices[k]
    order = np.argsort(ids[verts])
    idx = tuple(int(ids[verts[o]]) for o in order)
    return idx, tuple(float(lam[o]) for o in order)


# outline of the placed dots: hull vertices counter-clockwise; the two extremes for a line; [] for none
def outline(dots):
    ids, pts = unique_dots(dots)
    if len(ids) == 0:
        return []
    if len(ids) == 1:
        return [int(ids[0])]
    if is_collinear(pts):
        _, _, order, _ = line_order(pts)
        return [int(ids[order[0]]), int(ids[order[-1]])]
    hull = ConvexHull(pts)
    return [int(ids[v]) for v in hull.vertices]


# mean of a selection: one dot (its mean), two dots (slerp), or a triangle (nested slerp)
def mean_at(mu, idx, lam):
    idx = tuple(int(i) for i in idx)
    lam = tuple(float(w) for w in lam)
    if len(idx) == 1:
        return np.asarray(mu[idx[0]], dtype=np.float64).copy()
    if len(idx) == 2:
        a, b = idx
        t = lam[1] / (lam[0] + lam[1])
        return slerp(mu[a], mu[b], t)
    # nested slerp: m23 on the edge 2-3, then slerp from vertex 1 towards it (order of idx matters)
    l1, l2, l3 = lam
    i1, i2, i3 = idx
    if l2 + l3 > 0:
        m23 = slerp(mu[i2], mu[i3], l3 / (l2 + l3))
    else:
        m23 = np.asarray(mu[i2], dtype=np.float64)
    return slerp(mu[i1], m23, 1.0 - l1)


# the closest point of the zone of the dots to p. The zone: the dot (one dot); the segment between the two extremes
# (two dots or collinear dots); else the convex hull. A point inside the hull (or on its border) is returned as it
# is; outside, the nearest point of the hull's boundary. None without dots
def project_to_zone(p, dots):
    ids, pts = unique_dots(dots)
    if len(ids) == 0:
        return None
    p = np.asarray(p, dtype=np.float64)
    if len(ids) == 1:
        return pts[0].copy()
    # two dots, or collinear dots: the closest point of the segment between the extremes
    if is_collinear(pts):
        _, _, order, _ = line_order(pts)
        a = pts[order[0]]
        e = pts[order[-1]] - a
        t = float(np.clip((p - a) @ e / (e @ e), 0.0, 1.0))
        return a + t * e
    # three or more non-collinear dots: inside the hull (every facet has p on its inner side) gives p itself
    hull = ConvexHull(pts)
    if np.all(hull.equations[:, :2] @ p + hull.equations[:, 2] <= 1e-12):
        return p.copy()
    # outside: the closest point of each boundary edge, and the nearest of those
    best = None
    for a, b in hull.simplices:
        A, B = pts[a], pts[b]
        e = B - A
        t = float(np.clip((p - A) @ e / (e @ e), 0.0, 1.0))
        q = A + t * e
        d = float(np.linalg.norm(p - q))
        if best is None or d < best[0]:
            best = (d, q)
    return best[1]
