"""Summarize development runs, lock the shortlist and draw paired evidence plots."""
import csv
import hashlib
import json

from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
import numpy as np

from stage3_search import GROUPS, OUT, SEEDS, load_json, save_json
from stage1_single_vehicle import CONTROLLED, metrics, run
from stage3_policy import TablePolicy

INK = "#253645"
TEAL = "#007c79"
GOLD = "#b07622"


def shortlist(rows):
    feasible = [r for r in rows if r["mean_reward"] is not None]
    return sorted(feasible, key=lambda r: (-r["mean_reward"], r["id"]))[:2]


def overview(data, rows):
    fig, (ax, right) = plt.subplots(1, 2, figsize=(11, 4.7),
                                     gridspec_kw={"width_ratios": [1, 1.2]})
    fig.subplots_adjust(left=.08, right=.98, bottom=.18, top=.78, wspace=.28)
    fig.text(.03, .95, "R3B reduced low-speed exposure with equal total travel time",
             fontsize=15, weight="bold", color=INK, va="top")
    fig.text(.03, .875, "Development seeds 1–3   /   60 vehicles per seed   /   one controlled vehicle",
             fontsize=10, color="#4e6070")
    ax.set_title("Three proposals per LLM round", loc="left", fontsize=12)
    best = []
    winner_x = []
    for i, g in enumerate(GROUPS[1:], start=1):
        a = data[g]["summary"]
        for j, r in enumerate(a):
            if r["mean_reward"] is not None:
                ax.scatter(i + .09*(j-1), r["mean_reward"], s=42, color="#76a6a4", zorder=3)
        b = shortlist(a)[0]
        best.append(b["mean_reward"])
        winner_x.append(i + .09*(a.index(b)-1))
        ax.annotate(b["id"], (winner_x[-1], b["mean_reward"]), xytext=(-12, 8),
                    textcoords="offset points", fontsize=9, color=INK)
    ax.plot(winner_x, best, color=TEAL, linewidth=1.5, zorder=2)
    ax.axhline(shortlist(data["grid"]["summary"])[0]["mean_reward"],
               color=GOLD, ls="--", lw=1.4, label="Best fixed-grid rule")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.set(xticks=[1, 2, 3], xticklabels=["Round 1", "Round 2", "Round 3"],
           xlim=(.65, 3.35), ylim=(-.05, 1.75), ylabel="Mean reward (weighted points)")
    selected = [shortlist(data["grid"]["summary"])[0], rows["R3B"], rows["R3C"]]
    pos = np.arange(len(selected))
    for offset, key, label, color in [
        (-.19, "follower_variation_per_km", "Follower speed variation", TEAL),
        (.19, "low_speed_vehicle_s", "Time below 5 m/s", "#9d685b"),
    ]:
        vals = [r["mean_improvement_percent"][key] for r in selected]
        bars = right.barh(pos + offset, vals, height=.3, color=color, label=label)
        right.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
    right.set_title("Follower variation and low-speed exposure", loc="left", fontsize=12)
    right.axvline(0, color=INK, lw=.8)
    right.set(yticks=pos, yticklabels=["Fixed grid", "R3B", "R3C"],
              xlabel="Mean reduction from all-IDM (%)", xlim=(-6.3, 23.5))
    right.invert_yaxis()
    right.legend(loc="upper center", bbox_to_anchor=(.5, -.20), ncol=2, frameon=False, fontsize=8)
    for a in (ax, right):
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y" if a is ax else "x", alpha=.17)
        a.set_axisbelow(True)
    fig.savefig(OUT / "development-comparison.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def trajectories(winner, expected):
    base, arrivals, flags, _, _ = run(1, "baseline")
    changed, paired, assignments, _, decisions = run(1, "candidate", TablePolicy(winner))
    if arrivals != paired or flags != assignments or metrics(changed, paired) != expected:
        raise ValueError("Figure replay differs from the scored seed-1 run")
    if [v.id for v in base] != [v.id for v in changed]:
        raise ValueError("Unmatched vehicle IDs")
    changed_exits = sum(v.history[-1]["t"] != w.history[-1]["t"] for v, w in zip(base, changed))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharex=True, sharey=True)
    fig.subplots_adjust(left=.075, right=.985, top=.78, bottom=.21, wspace=.05)
    fig.text(.055, .96, "How the same 60 vehicles approach the bottleneck",
             color=INK, fontsize=16, weight="bold", va="top")
    fig.text(.055, .875, "Development seed 1   /   approach detail   /   colour shows speed at 0.5 s intervals",
             fontsize=10, color="#4e6070")
    palette = ["#aa453c", "#d6a56c", "#4f8882", "#9bb2c8"]
    cmap = ListedColormap(palette)
    norm = BoundaryNorm([0, 5, 10, 20, 35], cmap.N, clip=True)
    for ax, group, title in zip(axes, (base, changed), ("All-IDM baseline", f"{winner['id']} on vehicle 30")):
        ax.axhspan(4.5, 4.7, color="#91a1ab", alpha=.11)
        for vehicle in group:
            samples = vehicle.history[::5]
            points = np.array([(p["t"], p["position"] / 1000) for p in samples])
            segments = np.stack([points[:-1], points[1:]], axis=1)
            collection = LineCollection(segments, cmap=cmap, norm=norm, linewidths=.73)
            collection.set_array(np.array([p["speed"] for p in samples[:-1]]))
            ax.add_collection(collection)
            if vehicle.id == CONTROLLED:
                ax.plot(*points.T, ls=(0, (2, 3)), color=INK, lw=1.5, zorder=4)
        ax.set(title=title, xlim=(140, 395), ylim=(2.75, 4.82), xlabel="Simulation time (s)")
        ax.spines[["right", "top"]].set_visible(False)
    axes[0].set_ylabel("Position on road (km)")
    for state, description, offset in [("active", "Cap starts", (8, -14)), ("done", "Cap ends", (8, 9))]:
        p = next(r for r in decisions if r["state"] == state)
        xy = p["t"], p["position"]/1000
        axes[1].scatter(*xy, color=INK, s=24, zorder=5)
        axes[1].annotate(description, xy, xytext=offset, textcoords="offset points", fontsize=9,
                         bbox=dict(facecolor="white", alpha=.85, edgecolor="none", pad=1.3))
    handles = [Line2D([], [], color=c, lw=3, label=s) for c, s in
               zip(palette, ["Below 5 m/s", "5–10 m/s", "10–20 m/s", "20 m/s and above"])]
    handles.append(Line2D([], [], color=INK, ls="--", label="Vehicle 30"))
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False)
    fig.savefig(OUT / "seed1-trajectories.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    return changed_exits


def main():
    scores = {g: load_json(OUT / f"{g}-results.json") for g in GROUPS}
    rules = {r["id"]: r for g in GROUPS for r in load_json(OUT / "proposals" / f"{g}.json")}
    all_rows = {r["id"]: r for result in scores.values() for r in result["summary"]}
    if len(rules) != 18 or set(all_rows) != set(rules):
        raise ValueError("Expected a complete 9 + 9 search")
    for g, record in scores.items():
        if [r["seed"] for r in record["by_seed"]] != list(SEEDS):
            raise ValueError(f"Unexpected seeds in {g}")
    selected = {"llm": shortlist([r for g in GROUPS[1:] for r in scores[g]["summary"]]),
                "fixed_grid": shortlist(scores["grid"]["summary"])}
    locked = {}
    for method, records in selected.items():
        locked[method] = []
        for r in records:
            rule = rules[r["id"]]
            canonical = json.dumps(rule, sort_keys=True, separators=(",", ":")).encode()
            locked[method].append({"rule": rule, "sha256_canonical_json": hashlib.sha256(canonical).hexdigest(),
                                   "development_mean_reward": r["mean_reward"]})
    with (OUT / "development-ranking.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ["group", "id", "eligible_seeds", "mean_reward", "min_gap_m",
                  "joint_mean_time_and_variation_improved",
                  "I_total_travel_pct", "I_follower_variation_pct", "I_low_speed_pct", "I_last_exit_pct"]
        writer = csv.writer(stream)
        writer.writerow(fields)
        for g, record in scores.items():
            for row in record["summary"]:
                gains = row["mean_improvement_percent"] or {}
                writer.writerow([g, *[row[k] for k in fields[1:6]],
                                 *[gains.get(k) for k in ("total_travel_s", "follower_variation_per_km",
                                                           "low_speed_vehicle_s", "last_exit_s")]])
    overview(scores, all_rows)
    best = locked["llm"][0]["rule"]
    expected = next(r["raw"] for g in GROUPS[1:] for r in scores[g]["by_seed"][0]["runs"]
                    if r["id"] == best["id"])
    changed = trajectories(best, expected)
    save_json(OUT / "shortlist.json", {"split": "development only", "seeds": SEEDS,
                                      "seed1_individual_exit_times_changed_for_best_llm": changed,
                                      "finalists_for_validation": locked})


if __name__ == "__main__":
    main()
