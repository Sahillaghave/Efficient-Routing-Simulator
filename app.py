# -*- coding: utf-8 -*-
"""
Efficient Routing in Computer Networks - Interactive Network Routing Simulator
==============================================================================
A Streamlit dashboard that simulates a small computer network and shows how
Dijkstra's shortest-path algorithm picks the minimum-cost route between two
routers.

Run (Windows):   python -m streamlit run app.py

How the code is organised (top to bottom)
  1. Configuration      - routers, layout positions, default links
  2. Graph + Dijkstra   - build_graphs(), dijkstra(), simulate()
  3. HTML helpers       - small functions that build styled cards/tables
  4. Plotly figure      - make_figure() draws the topology
  5. State + callbacks  - every button changes st.session_state in a callback
  6. UI sections A-G    - the page itself, built in main()

NOTE: this is a SOFTWARE SIMULATION of routing decisions. Nothing here talks
to real routers, and "link cost" is just a configurable number.
"""
import copy
import heapq
import html
import itertools
import math
import time

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

ss = st.session_state  # short alias used everywhere below

# =============================================================================
# 1. CONFIGURATION
# =============================================================================
ROUTERS = ["A", "B", "C", "D", "E", "F"]

# Fixed (x, y) positions so the picture never jumps around when links change.
POSITIONS = {
    "A": (0.0, 1.0), "B": (1.5, 2.0), "C": (1.5, 0.0),
    "D": (3.0, 2.0), "E": (3.0, 0.0), "F": (4.5, 1.0),
}

# Links are stored as {"A-B": {"cost": 4, "active": True}}.
# The key is always the two router names in alphabetical order.
DEFAULT_LINKS = {
    "A-B": {"cost": 4, "active": True},
    "A-C": {"cost": 2, "active": True},
    "B-C": {"cost": 1, "active": True},
    "B-D": {"cost": 5, "active": True},
    "C-D": {"cost": 8, "active": True},
    "C-E": {"cost": 10, "active": True},
    "D-E": {"cost": 2, "active": True},
    "D-F": {"cost": 6, "active": True},
    "E-F": {"cost": 3, "active": True},
    "B-E": {"cost": 7, "active": True},
}

# Where the cost label sits along a link (0.5 = middle). Crossing links get
# shifted labels so two numbers never land on top of each other.
LABEL_T = {"B-E": 0.30, "C-D": 0.30, "B-F": 0.38, "C-F": 0.38}

MAX_COST = 999
TIMING_RUNS = 200  # Dijkstra is run this many times and averaged for timing


def link_key(a, b):
    """Canonical key for an undirected link: routers in alphabetical order."""
    return "-".join(sorted((a, b)))


def pretty(key):
    """'A-B' -> 'A ↔ B'"""
    a, b = key.split("-")
    return a + " ↔ " + b


def validate_cost(value):
    """Return (cost_as_int, None) if valid, otherwise (None, error_message)."""
    if value is None:
        return None, "Please enter a link cost."
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, "Link cost must be a number."
    if math.isnan(number) or math.isinf(number):
        return None, "Link cost must be a finite number."
    if number < 0:
        return None, ("Negative link costs are not allowed. Dijkstra's "
                      "algorithm only works with non-negative weights.")
    if number != int(number):
        return None, "Please use a whole number for the link cost."
    if number < 1:
        return None, "Link cost must be at least 1."
    if number > MAX_COST:
        return None, "Link cost must be at most " + str(MAX_COST) + "."
    return int(number), None


# =============================================================================
# 2. GRAPH + DIJKSTRA
# =============================================================================
def build_graphs(links):
    """
    Build two NetworkX graphs from the link table:
      g_all    - every link (used for drawing and counting)
      g_active - only links that are NOT disabled (used for routing)
    A disabled link stays in g_all but is invisible to the routing algorithm.
    """
    g_all, g_active = nx.Graph(), nx.Graph()
    g_all.add_nodes_from(ROUTERS)
    g_active.add_nodes_from(ROUTERS)
    for key, data in links.items():
        a, b = key.split("-")
        g_all.add_edge(a, b, weight=data["cost"], active=data["active"])
        if data["active"]:
            g_active.add_edge(a, b, weight=data["cost"])
    return g_all, g_active


def dijkstra(adj, source, target, record=False):
    """
    Dijkstra's shortest-path algorithm with a priority queue (heapq).

    adj    : {router: [(neighbour, cost), ...]}  (active links only)
    record : when True, every step is logged together with a snapshot of the
             table (router / distance / previous / status). The steps shown in
             the dashboard come from here - they are never typed in by hand.

    Idea: keep the best-known ("tentative") distance to every router. Always
    finalise the unvisited router with the smallest tentative distance, then
    check whether going through it gives a cheaper way to its neighbours.
    We stop as soon as the destination is finalised.
    """
    INF = math.inf
    dist = {n: INF for n in adj}      # tentative distance from the source
    prev = {n: None for n in adj}     # router just before n on the best path
    visited = set()                   # routers whose distance is final
    heap = []                         # priority queue of (distance, router)
    steps = []

    def fmt(d):
        return "∞" if d == INF else str(d)

    def queue_view():
        live = sorted((d, n) for d, n in heap if n not in visited and d == dist[n])
        return ", ".join(n + ":" + str(d) for d, n in live) or "(empty)"

    def snapshot(current=None, on_path=()):
        rows = []
        for n in sorted(adj):
            if n in on_path:
                status = "On shortest path"
            elif n == current:
                status = "Current"
            elif n in visited:
                status = "Visited"
            elif dist[n] != INF:
                status = "In queue"
            else:
                status = "Unvisited"
            rows.append((n, fmt(dist[n]), prev[n] or "—", status))
        return rows

    def log(title, detail, current=None, on_path=()):
        steps.append({"title": title, "detail": detail,
                      "queue": queue_view(), "table": snapshot(current, on_path)})

    # Step 1 - initialise every router
    if record:
        log("Initialize", "Set the distance of every router to ∞ and its previous router to none.")
    # Step 2 - the source costs nothing to reach
    dist[source] = 0
    heapq.heappush(heap, (0, source))
    if record:
        log("Set source distance", "distance[" + source + "] = 0. Router " + source +
            " goes into the priority queue.")

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited or d > dist[u]:
            continue  # outdated queue entry (a cheaper one was found earlier)
        if record:
            log("Select router " + u,
                "Router " + u + " has the lowest tentative distance (" + str(d) +
                ") among unvisited routers, so its distance is now final.", current=u)
        visited.add(u)
        if u == target:
            if record:
                log("Destination reached",
                    "Router " + u + " is the destination, so the search can stop.", current=u)
            break
        for v, w in adj[u]:  # examine every neighbour of u
            if v in visited:
                if record:
                    log("Examine neighbour " + v,
                        "Link " + u + "–" + v + " (cost " + str(w) + "): " + v +
                        " is already final, skip it.", current=u)
                continue
            candidate = d + w  # cost of reaching v by going through u
            if candidate < dist[v]:
                old = dist[v]
                dist[v], prev[v] = candidate, u
                heapq.heappush(heap, (candidate, v))
                if record:
                    log("Update router " + v,
                        "Link " + u + "–" + v + " (cost " + str(w) + "): " + str(d) + " + " +
                        str(w) + " = " + str(candidate) + " is cheaper than " + fmt(old) +
                        ". Set distance[" + v + "] = " + str(candidate) + " and previous[" +
                        v + "] = " + u + ".", current=u)
            elif record:
                log("Examine neighbour " + v,
                    "Link " + u + "–" + v + " (cost " + str(w) + "): " + str(d) + " + " +
                    str(w) + " = " + str(candidate) + " is not cheaper than " + fmt(dist[v]) +
                    ". No change.", current=u)

    reachable = target in visited
    if record and not reachable:
        log("Priority queue empty",
            "No reachable unvisited router is left, and " + target + " was never reached.")

    # Walk the 'previous' pointers backwards to rebuild the path.
    path = []
    if reachable:
        node = target
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()

    if record:
        if reachable:
            log("Final result", "Shortest path " + " → ".join(path) +
                " with total cost " + str(dist[target]) + ".", on_path=tuple(path))
        else:
            log("Final result", "Destination Unreachable: no active path from " + source +
                " to " + target + ".")
    return {"dist": dist, "prev": prev, "path": path, "reachable": reachable, "steps": steps}


def signature(links, src, dst):
    """A fingerprint of (selection + network). If it changes, old results are stale."""
    return (src, dst, tuple(sorted((k, v["cost"], v["active"]) for k, v in links.items())))


def simulate(links, src, dst, repeats=TIMING_RUNS):
    """Run the whole simulation for the CURRENT links and return every result."""
    g_all, g_active = build_graphs(links)
    adj = {n: sorted((nbr, d["weight"]) for nbr, d in g_active[n].items()) for n in g_active}

    # Measure real execution time: average of several runs (one run is microseconds).
    start = time.perf_counter_ns()
    for _ in range(repeats):
        dijkstra(adj, src, dst, record=False)
    time_us = (time.perf_counter_ns() - start) / repeats / 1000.0

    res = dijkstra(adj, src, dst, record=True)  # same algorithm, now with a step log

    # Alternative routes: next-best loop-free paths found by NetworkX.
    alternatives = []
    if res["reachable"]:
        try:
            for p in itertools.islice(nx.shortest_simple_paths(g_active, src, dst, weight="weight"), 6):
                if p == res["path"]:
                    continue
                cost = sum(g_active[a][b]["weight"] for a, b in zip(p, p[1:]))
                alternatives.append({"path": p, "cost": cost, "hops": len(p) - 1})
                if len(alternatives) == 3:
                    break
        except nx.NetworkXNoPath:
            pass

    # Cross-check our own Dijkstra against NetworkX's implementation.
    if res["reachable"]:
        verified = nx.dijkstra_path_length(g_active, src, dst, weight="weight") == res["dist"][dst]
    else:
        verified = not nx.has_path(g_active, src, dst)

    active = sum(1 for v in links.values() if v["active"])
    return {
        "signature": signature(links, src, dst), "src": src, "dst": dst,
        "reachable": res["reachable"], "path": res["path"],
        "cost": res["dist"][dst] if res["reachable"] else None,
        "hops": len(res["path"]) - 1 if res["reachable"] else None,
        "steps": res["steps"], "alternatives": alternatives, "verified": verified,
        "time_us": time_us, "repeats": repeats,
        "n_routers": len(ROUTERS), "n_active": active, "n_disabled": len(links) - active,
    }


# =============================================================================
# 3. HTML HELPERS (styled cards, tables, callouts)
# =============================================================================
def esc(x):
    return html.escape(str(x))


def callout(kind, text):
    """kind: ok | err | warn | info. `text` may contain simple HTML like <b>."""
    icon = {"ok": "✔", "err": "✖", "warn": "!", "info": "i"}[kind]
    return ('<div class="nt-callout nt-' + kind + '"><span class="nt-ico">' + icon +
            '</span><div>' + text + '</div></div>')


def section(letter, title, sub):
    st.markdown('<div class="nt-section"><div class="nt-secbadge">' + letter +
                '</div><div><div class="nt-sectitle">' + esc(title) +
                '</div><div class="nt-secsub">' + esc(sub) + '</div></div></div>',
                unsafe_allow_html=True)


def metric_card(label, value, sub=""):
    return ('<div class="nt-metric"><div class="nt-metric-label">' + esc(label) +
            '</div><div class="nt-metric-value">' + esc(value) +
            '</div><div class="nt-metric-sub">' + esc(sub) + '</div></div>')


def route_html(path):
    parts = []
    for i, n in enumerate(path):
        parts.append('<span class="nt-node">' + esc(n) + '</span>')
        if i < len(path) - 1:
            parts.append('<span class="nt-arrow">→</span>')
    return '<div class="nt-route">' + "".join(parts) + '</div>'


def html_table(headers, rows, row_classes=None):
    """Cells in `rows` must already be HTML-safe (use esc() on text)."""
    head = "".join("<th>" + esc(h) + "</th>" for h in headers)
    body = []
    for i, row in enumerate(rows):
        cls = row_classes[i] if row_classes else ""
        body.append('<tr class="' + cls + '">' + "".join("<td>" + c + "</td>" for c in row) + "</tr>")
    return ('<div class="nt-tablewrap"><table class="nt-table"><thead><tr>' + head +
            "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>")


STATUS_STYLE = {  # status -> (row class, badge class)
    "Current": ("r-cur", "b-cur"), "Visited": ("r-vis", "b-vis"),
    "In queue": ("", "b-que"), "Unvisited": ("", "b-unv"), "On shortest path": ("r-path", "b-path"),
}


def step_table_html(table):
    rows, classes = [], []
    for router, dist, prev, status in table:
        row_cls, badge_cls = STATUS_STYLE[status]
        rows.append(["<b>" + esc(router) + "</b>", esc(dist), esc(prev),
                     '<span class="nt-bstat ' + badge_cls + '">' + esc(status) + "</span>"])
        classes.append(row_cls)
    return html_table(["Router", "Tentative distance", "Previous router", "Status"], rows, classes)


def route_card(sim, label):
    if sim["reachable"]:
        body = (route_html(sim["path"]) + '<div class="nt-msub">Cost <b>' + str(sim["cost"]) +
                "</b> &nbsp;·&nbsp; " + str(sim["hops"]) + " hop(s)</div>")
    else:
        body = '<div class="nt-unreach">Destination Unreachable</div>'
    return '<div class="nt-mini"><div class="nt-mtitle">' + esc(label) + "</div>" + body + "</div>"


def compare_text(before, after):
    """Describe what changed between two simulation results."""
    if before["reachable"] and after["reachable"]:
        same_route = before["path"] == after["path"]
        delta = after["cost"] - before["cost"]
        route_txt = "The route stayed the <b>same</b>. " if same_route else "The route <b>changed</b>. "
        if delta == 0:
            cost_txt = "Total cost is unchanged (" + str(after["cost"]) + ")."
        else:
            cost_txt = "Total cost changed from " + str(before["cost"]) + " to " + str(after["cost"]) + \
                       " (" + ("+" if delta > 0 else "") + str(delta) + ")."
        return "info", route_txt + cost_txt
    if before["reachable"] and not after["reachable"]:
        return "err", "<b>Destination Unreachable.</b> No route remains after this change."
    if not before["reachable"] and after["reachable"]:
        return "ok", "A route now exists again. Total cost " + str(after["cost"]) + "."
    return "err", "<b>Destination still unreachable.</b>"


def fmt_link(key):
    data = ss.links.get(key)
    if data is None:
        return pretty(key)
    return pretty(key) + "   (cost " + str(data["cost"]) + ("" if data["active"] else ", DISABLED") + ")"


# =============================================================================
# 4. PLOTLY FIGURE
# =============================================================================
def make_figure(links, path, src, dst):
    """Draw routers, links, failed links and the highlighted shortest path."""
    path_edges = {link_key(a, b) for a, b in zip(path, path[1:])}
    on_path = set(path)

    def edge_xy(keys):  # None separates the individual line segments
        xs, ys = [], []
        for k in keys:
            a, b = k.split("-")
            xs += [POSITIONS[a][0], POSITIONS[b][0], None]
            ys += [POSITIONS[a][1], POSITIONS[b][1], None]
        return xs, ys

    normal = sorted(k for k, v in links.items() if v["active"] and k not in path_edges)
    failed = sorted(k for k, v in links.items() if not v["active"])
    best = sorted(k for k in path_edges if k in links)

    fig = go.Figure()
    gx, gy = edge_xy(best)  # soft glow under the path
    fig.add_trace(go.Scatter(x=gx, y=gy, mode="lines", hoverinfo="skip", showlegend=False,
                             line=dict(color="rgba(34,229,201,0.25)", width=16)))
    x, y = edge_xy(normal)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", hoverinfo="skip", name="Active link",
                             line=dict(color="#4f7cc4", width=3)))
    x, y = edge_xy(failed)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", hoverinfo="skip", name="Failed link (disabled)",
                             line=dict(color="#f43f5e", width=3, dash="dash")))
    fig.add_trace(go.Scatter(x=gx, y=gy, mode="lines", hoverinfo="skip", name="Shortest path",
                             line=dict(color="#22e5c9", width=7)))

    # Cost labels (annotations) + invisible hover points for link details.
    annotations, hx, hy, htext = [], [], [], []
    for k, v in sorted(links.items()):
        a, b = k.split("-")
        t = LABEL_T.get(k, 0.5)
        lx = POSITIONS[a][0] + (POSITIONS[b][0] - POSITIONS[a][0]) * t
        ly = POSITIONS[a][1] + (POSITIONS[b][1] - POSITIONS[a][1]) * t
        if not v["active"]:
            border, color, text, state = "#f43f5e", "#fda4af", str(v["cost"]) + " ✕", "DISABLED"
        elif k in path_edges:
            border, color, text, state = "#22e5c9", "#22e5c9", "<b>" + str(v["cost"]) + "</b>", "On shortest path"
        else:
            border, color, text, state = "#4f7cc4", "#d6e4ff", str(v["cost"]), "Active"
        annotations.append(dict(x=lx, y=ly, text=text, showarrow=False, font=dict(size=15, color=color),
                                bgcolor="#0a1329", bordercolor=border, borderwidth=1.5, borderpad=4))
        hx.append(lx)
        hy.append(ly)
        htext.append("Link " + a + " ↔ " + b + "<br>Cost: " + str(v["cost"]) + "<br>Status: " + state)
    fig.add_trace(go.Scatter(x=hx, y=hy, mode="markers", marker=dict(size=26, opacity=0),
                             hovertext=htext, hoverinfo="text", showlegend=False))

    # Routers: one trace per role so the legend explains the colours.
    def role(n):
        if n == src:
            return "Source"
        if n == dst:
            return "Destination"
        return "On shortest path" if n in on_path else "Router"

    def node_hover(n):
        act = sum(1 for k, v in links.items() if n in k.split("-") and v["active"])
        off = sum(1 for k, v in links.items() if n in k.split("-") and not v["active"])
        return "Router " + n + "<br>Active links: " + str(act) + "<br>Disabled links: " + str(off)

    styles = {"Source": ("#16a34a", "#86efac"), "Destination": ("#d97706", "#fcd34d"),
              "On shortest path": ("#0e7490", "#22e5c9"), "Router": ("#1d4ed8", "#7fb0ff")}
    for r, (fill, border) in styles.items():
        names = [n for n in ROUTERS if role(n) == r]
        fig.add_trace(go.Scatter(
            x=[POSITIONS[n][0] for n in names], y=[POSITIONS[n][1] for n in names],
            mode="markers+text", text=names, textposition="middle center",
            textfont=dict(color="white", size=20), name=r,
            marker=dict(size=58, color=fill, line=dict(color=border, width=3)),
            hovertext=[node_hover(n) for n in names], hoverinfo="text"))

    fig.update_layout(
        height=540, margin=dict(l=10, r=10, t=10, b=60), dragmode="pan",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#cfe0ff"),
        xaxis=dict(visible=False, range=[-0.7, 5.2]), yaxis=dict(visible=False, range=[-0.7, 2.7]),
        annotations=annotations, hoverlabel=dict(bgcolor="#0d1730", font_color="#e6edf7"),
        legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5,
                    bgcolor="rgba(10,19,41,0.7)", bordercolor="#1e3358", borderwidth=1))
    return fig


# =============================================================================
# 5. SESSION STATE + CALLBACKS
# =============================================================================
# Streamlit reruns the whole script on every click. Buttons use on_click
# callbacks, which run BEFORE the rerun, so the graph and tables drawn next
# always show the updated network (no stale picture).
def init_state():
    if "links" not in ss:
        ss.links = copy.deepcopy(DEFAULT_LINKS)
        ss.sim = None                              # last simulation result
        ss.exp = {"cost": None, "fail": None}      # last experiment results
        ss.src, ss.dst = "A", "F"
        ss.add_a, ss.add_b, ss.add_cost = "A", "D", 5
        ss.step_idx = 1


def sync_edit_cost():
    k = ss.get("edit_link")
    if k in ss.links:
        ss.edit_cost = ss.links[k]["cost"]


def sync_exp_cost():
    k = ss.get("exp_cost_link")
    if k in ss.links:
        ss.exp_cost_val = ss.links[k]["cost"]


def ensure_widget_defaults():
    """Keep every link-selector pointing at a link that still exists."""
    all_keys = sorted(ss.links)
    active_keys = sorted(k for k, v in ss.links.items() if v["active"])
    for wkey, options, syncer in (("edit_link", all_keys, sync_edit_cost), ("rm_link", all_keys, None),
                                  ("exp_cost_link", all_keys, sync_exp_cost),
                                  ("exp_fail_link", active_keys, None)):
        if options and ss.get(wkey) not in options:
            ss[wkey] = options[0]
            if syncer:
                syncer()
        elif not options and wkey in ss:
            del ss[wkey]


def flash(kind, msg):
    ss["flash"] = (kind, msg)


def set_sim(sim):
    ss.sim = sim
    ss.step_idx = 1


def cb_run():
    if ss.src == ss.dst:
        flash("warn", "Source and destination must be <b>different</b> routers.")
        return
    set_sim(simulate(ss.links, ss.src, ss.dst))


def cb_edit_cost():
    key = ss.get("edit_link")
    if key not in ss.links:
        flash("err", "Select a link first.")
        return
    cost, err = validate_cost(ss.get("edit_cost"))
    if err:
        flash("err", err)
        return
    old = ss.links[key]["cost"]
    if cost == old:
        flash("info", "The cost is already " + str(old) + ". Nothing changed.")
        return
    ss.links[key]["cost"] = cost
    flash("ok", "Link <b>" + pretty(key) + "</b> cost changed from " + str(old) + " to " + str(cost) +
          ". Click <b>RUN ROUTING SIMULATION</b> to recalculate the route.")


def cb_add_link():
    a, b = ss.get("add_a"), ss.get("add_b")
    if a == b:
        flash("err", "A link needs two <b>different</b> routers.")
        return
    cost, err = validate_cost(ss.get("add_cost"))
    if err:
        flash("err", err)
        return
    key = link_key(a, b)
    if key in ss.links:
        d = ss.links[key]
        state = "active" if d["active"] else "disabled"
        flash("warn", "Link <b>" + pretty(key) + "</b> already exists (" + state + ", cost " + str(d["cost"]) +
              "). Edit its cost or restore it instead of adding it again.")
        return
    ss.links[key] = {"cost": cost, "active": True}
    flash("ok", "Added link <b>" + pretty(key) + "</b> with cost " + str(cost) +
          ". Click <b>RUN ROUTING SIMULATION</b> to recalculate.")


def cb_remove_link():
    key = ss.get("rm_link")
    if key not in ss.links:
        flash("err", "Select a link to remove.")
        return
    del ss.links[key]
    _, g_active = build_graphs(ss.links)
    note = "" if nx.is_connected(g_active) else \
        " The network is now <b>disconnected</b>, so some routers may be unreachable."
    flash("warn" if note else "ok", "Removed link <b>" + pretty(key) + "</b>." + note)


def cb_reset():
    ss.links = copy.deepcopy(DEFAULT_LINKS)
    ss.exp = {"cost": None, "fail": None}
    set_sim(None)
    sync_edit_cost()
    sync_exp_cost()
    flash("ok", "Network reset to the original 10-link configuration.")


def cb_exp_cost():
    """Experiment 1: change a link cost and compare the route before/after."""
    key = ss.get("exp_cost_link")
    if key not in ss.links:
        flash("err", "Select a link first.")
        return
    cost, err = validate_cost(ss.get("exp_cost_val"))
    if err:
        flash("err", err)
        return
    if ss.src == ss.dst:
        flash("warn", "Choose <b>different</b> source and destination routers first.")
        return
    old = ss.links[key]["cost"]
    if cost == old:
        flash("info", "The new cost equals the current cost. Enter a different value.")
        return
    before = simulate(ss.links, ss.src, ss.dst)   # route on the current network
    ss.links[key]["cost"] = cost                  # apply the change
    after = simulate(ss.links, ss.src, ss.dst)    # recalculate from scratch
    ss.exp["cost"] = {"key": key, "old": old, "new": cost, "src": ss.src, "dst": ss.dst,
                      "before": before, "after": after}
    set_sim(after)
    sync_edit_cost()
    flash("ok", "Link <b>" + pretty(key) + "</b> cost changed " + str(old) + " → " + str(cost) +
          " and the route was recalculated.")


def cb_exp_fail():
    """Experiment 2: disable a link (it stays in the table) and recompute."""
    key = ss.get("exp_fail_link")
    if key not in ss.links or not ss.links[key]["active"]:
        flash("err", "Select an active link to disable.")
        return
    if ss.src == ss.dst:
        flash("warn", "Choose <b>different</b> source and destination routers first.")
        return
    before = simulate(ss.links, ss.src, ss.dst)
    ss.links[key]["active"] = False
    after = simulate(ss.links, ss.src, ss.dst)
    ss.exp["fail"] = {"key": key, "src": ss.src, "dst": ss.dst, "before": before, "after": after}
    set_sim(after)
    if after["reachable"]:
        flash("ok", "Link <b>" + pretty(key) + "</b> failed. Traffic was re-routed using the remaining links.")
    else:
        flash("err", "Link <b>" + pretty(key) + "</b> failed. <b>Destination Unreachable.</b>")


def cb_restore_all():
    count = 0
    for d in ss.links.values():
        if not d["active"]:
            d["active"] = True
            count += 1
    flash("ok" if count else "info",
          "Restored " + str(count) + " failed link(s). Click <b>RUN ROUTING SIMULATION</b> to recalculate."
          if count else "There are no failed links to restore.")


# =============================================================================
# 6. USER INTERFACE
# =============================================================================
CSS = """
<style>
:root{--line:#1e3358;--text:#e6edf7;--muted:#8da2c4;--accent:#38bdf8;--cyan:#22e5c9;}
.stApp{background:radial-gradient(1100px 560px at 8% -8%,#10234a 0%,rgba(6,11,22,0) 60%),radial-gradient(900px 500px at 100% 0%,#0b2a3f 0%,rgba(6,11,22,0) 55%),#060b16;color:var(--text);font-family:"Segoe UI",system-ui,sans-serif;}
[data-testid="stHeader"]{background:transparent;}
footer{visibility:hidden;}
.block-container{padding-top:1.6rem;padding-bottom:3rem;max-width:1500px;}
.stApp p,.stApp li,.stApp label,.stApp h1,.stApp h2,.stApp h3{color:var(--text);}
[data-testid="stWidgetLabel"] p{color:var(--muted) !important;}
div[data-baseweb="select"] > div,div[data-baseweb="input"],div[data-baseweb="base-input"],.stNumberInput input{background-color:#0a1329 !important;border-color:var(--line) !important;color:var(--text) !important;}
div[data-baseweb="select"] *{color:var(--text) !important;}
div[data-baseweb="select"] svg{fill:var(--muted) !important;}
div[data-baseweb="popover"] > div,ul[role="listbox"],div[data-baseweb="menu"]{background-color:#0d1730 !important;}
div[data-baseweb="popover"] *,ul[role="listbox"] *{color:var(--text) !important;}
li[role="option"]:hover,li[aria-selected="true"]{background-color:#16294f !important;}
.stNumberInput button{background:#0a1329 !important;color:var(--text) !important;border-color:var(--line) !important;}
.stButton{width:100%;}
.stButton > button{width:100%;border-radius:10px;border:1px solid var(--line);background:#0f1d3a;font-weight:600;padding:.55rem 1rem;}
.stButton > button p{color:var(--text) !important;}
.stButton > button:hover{border-color:var(--accent);background:#14264b;}
.stButton > button[kind="primary"],button[data-testid="stBaseButton-primary"]{background:linear-gradient(90deg,#0ea5e9,#22e5c9);border:none;padding:.85rem 1rem;box-shadow:0 0 24px rgba(34,229,201,.35);}
.stButton > button[kind="primary"] p,button[data-testid="stBaseButton-primary"] p{color:#04121f !important;font-size:1.05rem;font-weight:800;letter-spacing:.04em;}
[data-testid="stExpander"],[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line) !important;border-radius:14px;}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{color:var(--text) !important;}
.stTabs [data-baseweb="tab-list"]{border-bottom:1px solid var(--line);gap:.3rem;}
.stTabs button[data-baseweb="tab"] p{color:var(--muted) !important;}
.stTabs button[aria-selected="true"] p{color:var(--cyan) !important;font-weight:700;}
[data-testid="stSlider"] *{color:var(--text);}
.nt-hero{padding:1.3rem 1.7rem;border:1px solid var(--line);border-radius:16px;background:linear-gradient(135deg,rgba(18,32,63,.92),rgba(8,16,34,.92));margin-bottom:1rem;box-shadow:0 0 40px rgba(56,189,248,.08);}
.nt-title{font-size:2.5rem;font-weight:800;line-height:1.15;background:linear-gradient(90deg,#e6f1ff,#38bdf8 60%,#22e5c9);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;}
.nt-subtitle{font-size:1.25rem;color:#9db6dd;margin-top:.15rem;}
.nt-hero-note{margin-top:.7rem;font-size:.88rem;color:#8da2c4;}
.nt-section{display:flex;align-items:center;gap:.8rem;margin:1.9rem 0 .7rem;}
.nt-secbadge{min-width:2.1rem;height:2.1rem;border-radius:9px;background:rgba(56,189,248,.14);border:1px solid rgba(56,189,248,.5);color:var(--accent);font-weight:800;display:flex;align-items:center;justify-content:center;}
.nt-sectitle{font-size:1.4rem;font-weight:700;color:var(--text);}
.nt-secsub{font-size:.9rem;color:var(--muted);}
.nt-callout{display:flex;gap:.7rem;align-items:flex-start;padding:.75rem 1rem;border-radius:12px;border:1px solid;margin:.5rem 0;font-size:.95rem;line-height:1.45;}
.nt-ico{min-width:1.4rem;height:1.4rem;border-radius:50%;border:1.5px solid currentColor;display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:800;}
.nt-ok{background:rgba(34,197,94,.1);border-color:rgba(34,197,94,.45);color:#c9f7d8;}
.nt-err{background:rgba(244,63,94,.1);border-color:rgba(244,63,94,.5);color:#ffd0d8;}
.nt-warn{background:rgba(245,158,11,.1);border-color:rgba(245,158,11,.5);color:#ffe6b3;}
.nt-info{background:rgba(56,189,248,.08);border-color:rgba(56,189,248,.4);color:#cdeeff;}
.nt-metric{background:linear-gradient(160deg,rgba(18,32,63,.95),rgba(10,19,41,.95));border:1px solid var(--line);border-radius:14px;padding:.9rem 1.1rem;margin-bottom:.6rem;}
.nt-metric-label{color:var(--muted);font-size:.85rem;}
.nt-metric-value{font-size:2rem;font-weight:800;color:#fff;line-height:1.25;}
.nt-metric-sub{font-size:.8rem;color:#7f95ba;}
.nt-route{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin:.5rem 0;}
.nt-node{display:inline-flex;align-items:center;justify-content:center;width:2.6rem;height:2.6rem;border-radius:50%;background:#0e7490;border:2px solid var(--cyan);color:#fff;font-weight:800;font-size:1.1rem;box-shadow:0 0 14px rgba(34,229,201,.4);}
.nt-arrow{color:var(--cyan);font-size:1.4rem;font-weight:700;}
.nt-tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;margin:.4rem 0 .8rem;}
.nt-table{width:100%;border-collapse:collapse;font-size:.95rem;}
.nt-table th{background:#0f1d3a;color:#9fb8e0;text-align:left;padding:.55rem .8rem;font-size:.82rem;font-weight:600;}
.nt-table td{padding:.5rem .8rem;border-top:1px solid #172a4a;color:var(--text);}
.nt-table tr.r-cur td{background:rgba(56,189,248,.16);}
.nt-table tr.r-path td{background:rgba(34,229,201,.12);}
.nt-table tr.r-vis td{background:rgba(34,197,94,.06);}
.nt-table tr.r-bad td{background:rgba(244,63,94,.1);}
.nt-bstat{padding:.12rem .6rem;border-radius:999px;font-size:.8rem;font-weight:700;border:1px solid;}
.b-cur{color:#7dd3fc;border-color:#38bdf8;background:rgba(56,189,248,.15);}
.b-vis{color:#86efac;border-color:#22c55e;}
.b-que{color:#fcd34d;border-color:#f59e0b;}
.b-unv{color:#7f95ba;border-color:#34496d;}
.b-path{color:#5eead4;border-color:#22e5c9;background:rgba(34,229,201,.15);}
.nt-step{background:rgba(13,23,48,.85);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:12px;padding:.8rem 1.1rem;margin:.4rem 0 .6rem;}
.nt-step-head{font-weight:700;font-size:1.1rem;color:#fff;}
.nt-step-detail{color:#cfe0ff;margin-top:.25rem;}
.nt-step-queue{color:#fcd34d;margin-top:.35rem;font-size:.9rem;}
.nt-log{max-height:420px;overflow-y:auto;border:1px solid var(--line);border-radius:12px;padding:.4rem .9rem;background:rgba(10,19,41,.7);}
.nt-logrow{padding:.5rem 0;border-bottom:1px solid #172a4a;color:#cfe0ff;font-size:.92rem;}
.nt-logrow b{color:#fff;}
.nt-pair{display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin:.5rem 0;}
.nt-mini{background:rgba(13,23,48,.85);border:1px solid var(--line);border-radius:12px;padding:.7rem .9rem;}
.nt-mtitle{color:var(--muted);font-size:.85rem;margin-bottom:.2rem;}
.nt-msub{color:#cfe0ff;font-size:.92rem;}
.nt-unreach{color:#fda4af;font-weight:800;font-size:1.1rem;padding:.6rem 0;}
.nt-h3{font-size:1.15rem;font-weight:700;color:#fff;margin-bottom:.2rem;}
.nt-desc{color:var(--muted);font-size:.9rem;margin-bottom:.5rem;}
.nt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:.8rem;}
.nt-edu{background:rgba(13,23,48,.85);border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem;}
.nt-edu-q{color:var(--cyan);font-weight:700;margin-bottom:.25rem;}
.nt-edu-a{color:#cfe0ff;font-size:.92rem;line-height:1.5;}
</style>
"""

EDUCATION = [
    ("What is routing?",
     "Routing is choosing the path that data packets take from a source to a destination through many "
     "connected routers. Every router decides where to send a packet next."),
    ("What is Dijkstra's algorithm?",
     "A greedy algorithm that finds the cheapest path from one router to all others. It always finalises the "
     "unvisited router with the smallest known distance, then checks if going through it gives a cheaper path "
     "to its neighbours. It needs non-negative costs. Link-state protocols such as OSPF use this idea."),
    ("What are nodes, edges and link costs?",
     "A node is a router. An edge is a link between two routers. A link cost is a number given to a link; "
     "a lower number means a more preferred link. Here it is only a configurable simulation value, "
     "not automatically delay or bandwidth."),
    ("What is a shortest path?",
     "The route whose link costs add up to the smallest total. It is not always the route with the fewest hops: "
     "two cheap links can beat one expensive link."),
    ("Why can the route change when costs change?",
     "The algorithm compares the total cost of every possible route. If one link becomes more expensive, "
     "another route can become cheaper, so the winner changes."),
    ("What happens when a link fails?",
     "The failed link can no longer be used, so the algorithm runs again on the remaining links. If another route "
     "exists, traffic moves to it (usually at a higher or equal cost). If no route is left, the destination is unreachable."),
]


def render_hero():
    st.markdown(
        '<div class="nt-hero"><div class="nt-title">Efficient Routing in Computer Networks</div>'
        '<div class="nt-subtitle">Interactive Network Routing Simulator</div>'
        '<div class="nt-hero-note">A software simulation of routing decisions. It is not connected to real '
        'physical routers.</div></div>', unsafe_allow_html=True)


def render_topology(links, path, src, dst):
    section("A", "Network topology",
            "Routers are nodes, links are edges, and the number on a link is its cost. Hover for details.")
    st.plotly_chart(make_figure(links, path, src, dst), key="topology_chart")


def render_controls(links, sim_valid, sim_stale):
    section("B", "Routing controls", "Choose the route to calculate and edit the network.")
    c1, c2 = st.columns(2)
    c1.selectbox("Source router", ROUTERS, key="src")
    c2.selectbox("Destination router", ROUTERS, key="dst")
    st.button("RUN ROUTING SIMULATION", type="primary", on_click=cb_run, key="btn_run")
    if ss.src == ss.dst:
        st.markdown(callout("warn", "Source and destination are the same router. Pick two different routers."),
                    unsafe_allow_html=True)
    elif sim_valid:
        st.markdown(callout("ok", "Results below are up to date for <b>" + ss.src + " → " + ss.dst + "</b>."),
                    unsafe_allow_html=True)
    elif sim_stale:
        st.markdown(callout("warn", "The network or selection changed. Click <b>RUN ROUTING SIMULATION</b> "
                                    "to recalculate."), unsafe_allow_html=True)

    t1, t2, t3, t4 = st.tabs(["Edit cost", "Add link", "Remove link", "Reset"])
    with t1:
        if links:
            st.selectbox("Link", sorted(links), format_func=fmt_link, key="edit_link", on_change=sync_edit_cost)
            st.number_input("New cost", min_value=1, max_value=MAX_COST, step=1, key="edit_cost")
            st.button("Update link cost", on_click=cb_edit_cost, key="btn_edit")
        else:
            st.markdown(callout("info", "There are no links to edit."), unsafe_allow_html=True)
    with t2:
        a, b = st.columns(2)
        a.selectbox("Router 1", ROUTERS, key="add_a")
        b.selectbox("Router 2", ROUTERS, key="add_b")
        st.number_input("Cost of new link", min_value=1, max_value=MAX_COST, step=1, key="add_cost")
        st.button("Add link", on_click=cb_add_link, key="btn_add")
    with t3:
        if links:
            st.selectbox("Link to remove", sorted(links), format_func=fmt_link, key="rm_link")
            st.button("Remove link", on_click=cb_remove_link, key="btn_rm")
        else:
            st.markdown(callout("info", "There are no links to remove."), unsafe_allow_html=True)
    with t4:
        st.markdown('<div class="nt-desc">Restores the original 10 links, costs and active state, and clears '
                    'all results.</div>', unsafe_allow_html=True)
        st.button("Reset network", on_click=cb_reset, key="btn_reset")

    rows, classes = [], []
    for k in sorted(links):
        d = links[k]
        rows.append([esc(pretty(k)), str(d["cost"]), "Active" if d["active"] else "Disabled"])
        classes.append("" if d["active"] else "r-bad")
    st.markdown(html_table(["Link", "Cost", "State"], rows, classes), unsafe_allow_html=True)


def render_result(sim, sim_valid, sim_stale):
    section("C", "Simulation result", "Calculated by Dijkstra's algorithm from the current links every time.")
    if not sim_valid:
        if sim_stale:
            msg = ("The network or router selection changed since the last run. Click "
                   "<b>RUN ROUTING SIMULATION</b> for a fresh result.")
        else:
            msg = "Pick a source and a destination, then click <b>RUN ROUTING SIMULATION</b>."
        st.markdown(callout("warn" if sim_stale else "info", msg), unsafe_allow_html=True)
        return
    if not sim["reachable"]:
        st.markdown(callout("err", "<b>Destination Unreachable.</b> No path exists from router " + sim["src"] +
                            " to router " + sim["dst"] + " using the active links."), unsafe_allow_html=True)
        return
    st.markdown(callout("ok", "Minimum-cost route found from <b>" + sim["src"] + "</b> to <b>" + sim["dst"] +
                        "</b>."), unsafe_allow_html=True)
    st.markdown(route_html(sim["path"]), unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown(metric_card("Total path cost", sim["cost"], "sum of the link costs on the route"),
                unsafe_allow_html=True)
    c2.markdown(metric_card("Hop count", sim["hops"], "links traversed"), unsafe_allow_html=True)
    c3.markdown(metric_card("Cross-check", "Verified" if sim["verified"] else "Mismatch",
                            "same cost as NetworkX dijkstra_path_length"), unsafe_allow_html=True)
    st.markdown('<div class="nt-h3">Alternative routes</div>', unsafe_allow_html=True)
    if sim["alternatives"]:
        rows = []
        for alt in sim["alternatives"]:
            extra = alt["cost"] - sim["cost"]
            rows.append([esc(" → ".join(alt["path"])), str(alt["cost"]), str(alt["hops"]),
                         "equal cost" if extra == 0 else "+" + str(extra)])
        st.markdown(html_table(["Route", "Total cost", "Hops", "Compared with best"], rows),
                    unsafe_allow_html=True)
    else:
        st.markdown(callout("info", "No other loop-free route exists with the active links."),
                    unsafe_allow_html=True)


def render_algorithm(sim, sim_valid):
    section("D", "Algorithm execution",
            "Every step and table below is recorded from the real run of Dijkstra's algorithm.")
    if not sim_valid:
        st.markdown(callout("info", "Run the simulation to see the algorithm step by step."),
                    unsafe_allow_html=True)
        return
    steps = sim["steps"]
    n = len(steps)
    tab1, tab2, tab3 = st.tabs(["Step through", "Full execution log", "Final table"])
    with tab1:
        if n > 1:
            if ss.get("step_idx", 1) > n:
                ss.step_idx = n
            idx = st.slider("Algorithm step", 1, n, key="step_idx")
        else:
            idx = 1
        step = steps[idx - 1]
        st.markdown('<div class="nt-step"><div class="nt-step-head">Step ' + str(idx) + " of " + str(n) +
                    " · " + esc(step["title"]) + '</div><div class="nt-step-detail">' + esc(step["detail"]) +
                    '</div><div class="nt-step-queue">Priority queue (router:distance): ' +
                    esc(step["queue"]) + "</div></div>", unsafe_allow_html=True)
        st.markdown(step_table_html(step["table"]), unsafe_allow_html=True)
    with tab2:
        rows = "".join('<div class="nt-logrow"><b>' + str(i) + ". " + esc(s["title"]) + "</b><br>" +
                       esc(s["detail"]) + "</div>" for i, s in enumerate(steps, 1))
        st.markdown('<div class="nt-log">' + rows + "</div>", unsafe_allow_html=True)
    with tab3:
        st.markdown(step_table_html(steps[-1]["table"]), unsafe_allow_html=True)
        st.markdown('<div class="nt-desc">Tentative distance = lowest known total cost from ' + esc(sim["src"]) +
                    ". The search stops when the destination is finalised, so routers farther away may still show "
                    "tentative values or ∞.</div>", unsafe_allow_html=True)


def render_experiments(links):
    section("E", "Network failure & cost change experiment",
            "Change the network, then watch the route get recalculated.")
    st.markdown(callout("info", "This is a <b>software simulation</b> of routing decisions on a graph stored "
                                "in memory. It is not connected to any real physical router."),
                unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")

    with left, st.container(border=True):
        st.markdown('<div class="nt-h3">1. Link cost change</div><div class="nt-desc">Raise or lower the cost of '
                    'a link, then compare the previous and new route for the selected source and destination.'
                    '</div>', unsafe_allow_html=True)
        if links:
            st.selectbox("Link to modify", sorted(links), format_func=fmt_link, key="exp_cost_link",
                         on_change=sync_exp_cost)
            st.number_input("New link cost", min_value=1, max_value=MAX_COST, step=1, key="exp_cost_val")
            st.button("Apply cost change & recompute", on_click=cb_exp_cost, key="btn_exp_cost")
        e = ss.exp["cost"]
        if e:
            kind, text = compare_text(e["before"], e["after"])
            st.markdown('<div class="nt-desc">Last experiment: link <b>' + pretty(e["key"]) + "</b> cost " +
                        str(e["old"]) + " → " + str(e["new"]) + " (route " + e["src"] + " → " + e["dst"] +
                        ')</div><div class="nt-pair">' + route_card(e["before"], "Previous route") +
                        route_card(e["after"], "New route") + "</div>" + callout(kind, text),
                        unsafe_allow_html=True)

    with right, st.container(border=True):
        st.markdown('<div class="nt-h3">2. Link failure</div><div class="nt-desc">Disable a link without deleting '
                    'it. It turns into a red dashed line and the route is recalculated with the remaining '
                    'links.</div>', unsafe_allow_html=True)
        if any(v["active"] for v in links.values()):
            st.selectbox("Link to disable", sorted(k for k, v in links.items() if v["active"]),
                         format_func=fmt_link, key="exp_fail_link")
            st.button("Disable link & recompute", on_click=cb_exp_fail, key="btn_exp_fail")
        else:
            st.markdown(callout("err", "Every link is already disabled."), unsafe_allow_html=True)
        down = sorted(k for k, v in links.items() if not v["active"])
        if down:
            st.markdown('<div class="nt-desc">Currently failed: <b>' + ", ".join(pretty(k) for k in down) +
                        "</b></div>", unsafe_allow_html=True)
            st.button("Restore all failed links", on_click=cb_restore_all, key="btn_restore")
        e = ss.exp["fail"]
        if e:
            kind, text = compare_text(e["before"], e["after"])
            st.markdown('<div class="nt-desc">Last experiment: link <b>' + pretty(e["key"]) + "</b> disabled (route " +
                        e["src"] + " → " + e["dst"] + ')</div><div class="nt-pair">' +
                        route_card(e["before"], "Route before failure") +
                        route_card(e["after"], "Route after failure") + "</div>" + callout(kind, text),
                        unsafe_allow_html=True)


def render_metrics(links, sim, sim_valid):
    section("F", "Performance metrics", "All values are calculated from the current graph and the measured run.")
    active = sum(1 for v in links.values() if v["active"])
    ok = sim_valid and sim["reachable"]
    c = st.columns(3)
    c[0].markdown(metric_card("Total route cost", sim["cost"] if ok else "—",
                              "from the last run" if ok else "run the simulation"), unsafe_allow_html=True)
    c[1].markdown(metric_card("Hop count", sim["hops"] if ok else "—",
                              "links on the route" if ok else "run the simulation"), unsafe_allow_html=True)
    c[2].markdown(metric_card("Routers in network", len(ROUTERS), "nodes in the graph"), unsafe_allow_html=True)
    d = st.columns(3)
    d[0].markdown(metric_card("Active links", active, "available for routing"), unsafe_allow_html=True)
    d[1].markdown(metric_card("Disabled links", len(links) - active, "failed, but not deleted"),
                  unsafe_allow_html=True)
    d[2].markdown(metric_card("Computation time", f"{sim['time_us']:.1f} µs" if sim_valid else "—",
                              ("average of " + str(sim["repeats"]) + " runs of Dijkstra") if sim_valid
                              else "run the simulation"), unsafe_allow_html=True)
    st.markdown(callout("info", "<b>Link cost</b> is a configurable simulation metric. It does not automatically "
                                "represent real-world delay or bandwidth. The computation time is tiny because the "
                                "graph is tiny; it is measured on this computer, not estimated."),
                unsafe_allow_html=True)


def comparison_rows(links, src, dst):
    def row(name, s, note):
        if s is None:
            return [esc(name), "—", "—", "—", "—", esc(note)], ""
        if s["reachable"]:
            cells = [esc(s["src"] + " → " + s["dst"]), esc(" → ".join(s["path"])), str(s["cost"]), str(s["hops"])]
            cls = ""
        else:
            cells = [esc(s["src"] + " → " + s["dst"]), "<b>Destination Unreachable</b>", "—", "—"]
            cls = "r-bad"
        return [esc(name)] + cells + [esc(note)], cls

    differ = src != dst
    original = simulate(DEFAULT_LINKS, src, dst, repeats=1) if differ else None
    current = simulate(links, src, dst, repeats=1) if differ else None
    ec, ef = ss.exp["cost"], ss.exp["fail"]
    cost_note = ("Link " + pretty(ec["key"]) + " cost " + str(ec["old"]) + " → " + str(ec["new"])) if ec \
        else "Run experiment 1 in section E"
    fail_note = ("Link " + pretty(ef["key"]) + " disabled") if ef else "Run experiment 2 in section E"
    items = [("Original network", original, "Default links and costs" if differ else "Pick two different routers"),
             ("After link-cost change", ec["after"] if ec else None, cost_note),
             ("After link failure", ef["after"] if ef else None, fail_note),
             ("Current network (live)", current, "Whatever is on the graph right now")]
    rows, classes = [], []
    for name, s, note in items:
        r, cls = row(name, s, note)
        rows.append(r)
        classes.append(cls)
    return rows, classes


def render_comparison(links, src, dst):
    section("G", "Comparison panel", "Real Dijkstra results for each scenario, not typed-in values.")
    rows, classes = comparison_rows(links, src, dst)
    st.markdown(html_table(["Scenario", "Source → destination", "Route", "Total cost", "Hops", "What changed"],
                           rows, classes), unsafe_allow_html=True)
    st.markdown('<div class="nt-desc">The original row uses the currently selected routers on the default network. '
                'Experiment rows use the routers selected when the experiment ran, and experiments stack on the '
                'current network until you press Reset. Congestion and packet loss are not simulated.</div>',
                unsafe_allow_html=True)


def render_education():
    section("H", "Quick explanations", "Plain-English answers to the main concepts.")
    with st.expander("Open the explanation panel", expanded=False):
        cards = "".join('<div class="nt-edu"><div class="nt-edu-q">' + esc(q) + '</div><div class="nt-edu-a">' +
                        esc(a) + "</div></div>" for q, a in EDUCATION)
        st.markdown('<div class="nt-grid">' + cards + "</div>", unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="Efficient Routing in Computer Networks", page_icon="🛰️", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    ensure_widget_defaults()

    links, src, dst, sim = ss.links, ss.src, ss.dst, ss.sim
    # A stored result is only trusted if the network and selection are unchanged.
    sim_valid = sim is not None and sim["signature"] == signature(links, src, dst)
    sim_stale = sim is not None and not sim_valid
    path = sim["path"] if sim_valid and sim["reachable"] else []

    render_hero()
    message = ss.pop("flash", None)  # one-time message from the last button click
    if message:
        st.markdown(callout(message[0], message[1]), unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        render_topology(links, path, src, dst)
    with right:
        render_controls(links, sim_valid, sim_stale)

    render_result(sim, sim_valid, sim_stale)
    render_algorithm(sim, sim_valid)
    render_experiments(links)
    render_metrics(links, sim, sim_valid)
    render_comparison(links, src, dst)
    render_education()


if __name__ == "__main__":
    main()
