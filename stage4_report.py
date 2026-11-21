"""Read the frozen test archive, cross-check exit records and render comparisons."""
import csv
from math import isclose
from statistics import mean

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D

from evaluate import METRICS, score
from stage3_search import load_json, summarize
from stage4_freeze import OUT, TEST, digest_json, write_json

TEAL, GOLD, INK = "#007c79", "#a66824", "#233342"
W, C = "follower_variation_per_km", "low_speed_vehicle_s"


def check_exits(raw, timestamps, arrivals):
    finished = {k: t for k, t in timestamps.items() if t is not None}
    assert raw["vehicles_admitted"] == len(timestamps)
    assert raw["vehicles_exited"] == len(finished)
    assert raw["exited_by_400s"] == sum(t <= 400 for t in finished.values())
    if raw["all_completed"]:
        assert set(finished) == {str(i+1) for i in range(len(arrivals))}
        total = sum(t - arrivals[int(k)-1] for k, t in finished.items())
        assert isclose(total, raw["total_travel_s"], rel_tol=0, abs_tol=1e-8)
        assert max(finished.values()) == raw["last_exit_s"]


def audit_and_export(freeze, records):
    binding = digest_json(freeze)
    rules = [x["rule"] for x in freeze["selected"].values()]
    ids = [r["id"] for r in rules]
    flat = []
    for seed, record in zip(TEST, records, strict=True):
        base = record["baseline"]
        assert record["seed"] == seed and record["binding"] == binding
        assert record["noop_trajectory_identical"] and [r["id"] for r in record["runs"]] == ids
        arms = [("IDM", base, record["baseline_score"], record["baseline_exit_times_s"])]
        for r in record["runs"]:
            assert r["score"] == score(base, r["raw"])
            assert all(v == base[k] - r["raw"][k] for k, v in r["savings"].items() if v is not None)
            arms.append((r["id"], r["raw"], r["score"], r["exit_times_s"]))
        for arm, raw, assessment, times in arms:
            check_exits(raw, times, record["scheduled_arrivals_s"])
            delta = {f"saving_{k}": base[k] - raw[k] if base.get(k) is not None and raw.get(k) is not None
                     else None for k in METRICS}
            changed = sum(times.get(i) != record["baseline_exit_times_s"].get(i)
                          for i in set(times) | set(record["baseline_exit_times_s"]))
            flat.append({"seed": seed, "arm": arm, "eligible_status": assessment["status"],
                         "reason": ", ".join(assessment["reasons"]), "reward": assessment["reward"],
                         "exit_timestamps_different": changed, **raw, **delta,
                         **{f"improvement_pct_{k}": assessment.get("improvements_percent", {}).get(k)
                            for k in METRICS}})
    with (OUT / "held-out-comparison.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for row in flat for k in row)))
        writer.writeheader()
        writer.writerows(flat)
    archived = load_json(OUT / "test/summary.json")
    assert archived["binding"] == binding and archived["seeds"] == list(TEST)
    assert summarize(records, rules) == archived["summary"]
    details = {}
    for rule in ids:
        rows = [r for r in flat if r["arm"] == rule]
        per_metric = {}
        for metric in METRICS:
            deltas = [r["saving_" + metric] for r in rows if r["saving_" + metric] is not None]
            per_metric[metric] = {"mean_saving": mean(deltas) if len(deltas) == len(rows) else None,
                                  "improved": sum(v > 0 for v in deltas), "tied": deltas.count(0),
                                  "worsened": sum(v < 0 for v in deltas), "missing": len(rows)-len(deltas)}
        details[rule] = {"paired_savings_and_counts": per_metric,
                         "changed_exit_timestamps": sum(r["exit_timestamps_different"] for r in rows)}
    write_json(OUT / "paired-counts.json", details)
    return flat


def outcome_plot(flat, ids):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True, layout="constrained")
    for ax, key, title in zip(axes, (W, C), ("Follower speed variation", "Time below 5 m/s")):
        xkey = f"improvement_pct_{key}"
        for i, seed in enumerate(TEST):
            x = [next(r[xkey] for r in flat if r["seed"] == seed and r["arm"] == arm) for arm in ids]
            ax.plot(x, [i, i], color="#b8c2cc", lw=1.7, zorder=1)
            ax.scatter(x, [i, i], c=[TEAL, GOLD], s=43, zorder=2)
        ax.set(title=title, xlabel="Reduction from all-IDM (%)",
               yticks=range(len(TEST)), yticklabels=[str(s) for s in TEST])
        ax.axvline(0, color="#98a6ad", lw=1)
        ax.set_xlim(left=min(-.2, ax.get_xlim()[0]))
        ax.grid(axis="x", alpha=.18)
        ax.spines[["right", "top"]].set_visible(False)
    axes[0].set_ylabel("Held-out seed")
    axes[0].invert_yaxis()
    fig.suptitle("Paired effects on six previously unseen traffic sequences", fontsize=15,
                 fontweight="bold", color=INK)
    handles = [Line2D([], [], color=c, marker="o", lw=0, label=label)
               for c, label in zip((TEAL, GOLD), (f"{ids[0]} · LLM rule", f"{ids[1]} · fixed rule"))]
    fig.legend(handles=handles, loc="outside lower center", ncols=2, frameon=False)
    fig.savefig(OUT / "paired-effects.png", dpi=170)
    plt.close(fig)


def trajectory_plot(first, ids):
    arms = ["IDM", ids[1], ids[0]]
    color = ["#aa453c", "#d6a56c", "#4f8882", "#9bb2c8"]
    cmap = ListedColormap(color)
    norm = BoundaryNorm([0, 5, 10, 20, 35], cmap.N, clip=True)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), sharex=True, sharey=True, layout="constrained")
    runs = {r["id"]: r for r in first["runs"]}
    with np.load(OUT / "test/trajectories-101.npz", allow_pickle=False) as arr:
        for ax, arm, title in zip(axes, arms, ("All-IDM baseline", f"{ids[1]} · fixed rule", f"{ids[0]} · LLM rule")):
            pts = arr[arm]
            ax.axhspan(4.5, 4.7, color="#91a1ab", alpha=.12)
            for vid in np.unique(pts[:, 0]):
                subset = pts[pts[:, 0] == vid]
                coords = np.column_stack((subset[:, 1], subset[:, 2]/1000))
                lines = LineCollection(np.stack((coords[:-1], coords[1:]), axis=1),
                                       cmap=cmap, norm=norm, linewidths=.75)
                lines.set_array(subset[:-1, 3])
                ax.add_collection(lines)
                if vid == 30:
                    ax.plot(*coords.T, color=INK, lw=1.4, ls=(0, (2, 3)), zorder=4)
            if arm in runs:
                for event in (runs[arm]["first_active"], runs[arm]["diagnostic"]["release"]):
                    if event:
                        ax.scatter(event["t"], event["position"]/1000, s=23, color=INK, zorder=5)
            ax.set(title=title, xlabel="Simulation time (s)", xlim=(140, 395), ylim=(2.75, 4.82))
            ax.spines[["right", "top"]].set_visible(False)
    axes[0].set_ylabel("Road position (km)")
    fig.suptitle("One controlled vehicle approaching the bottleneck  ·  test seed 101",
                 fontsize=15, color=INK, weight="bold")
    legend = [Line2D([], [], color=c, lw=3, label=s) for c, s in
              zip(color, ("Below 5 m/s", "5–10 m/s", "10–20 m/s", "20 m/s and above"))]
    legend += [Line2D([], [], color=INK, ls="--", label="Vehicle 30"),
               Line2D([], [], color=INK, lw=0, marker="o", markersize=4, label="Cap starts / ends")]
    fig.legend(handles=legend, loc="outside lower center", ncols=6, frameon=False)
    fig.savefig(OUT / "seed101-trajectories.png", dpi=160)
    plt.close(fig)


def main():
    freeze = load_json(OUT / "freeze.json")
    records = [load_json(OUT / f"test/seed-{seed}.json") for seed in TEST]
    ids = [freeze["selected"][m]["rule"]["id"] for m in ("llm", "fixed_grid")]
    flat = audit_and_export(freeze, records)
    outcome_plot(flat, ids)
    trajectory_plot(records[0], ids)


if __name__ == "__main__":
    main()
