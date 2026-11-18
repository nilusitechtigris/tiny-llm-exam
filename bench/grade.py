"""Grade saved results. Applies manual_grades.json overrides (human review) on top of auto graders.

usage: python3 grade.py [label ...]   -> prints table, writes results/summary.json
"""
import json, os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tasks import TASKS

def load_manual():
    p = os.path.join(HERE, "manual_grades.json")
    return json.load(open(p)) if os.path.exists(p) else {}

def grade_file(path, manual):
    data = json.load(open(path))
    label = data["info"]["label"]
    byid = {r["id"]: r for r in data["results"]}
    rows = []
    for t in TASKS:
        r = byid[t["id"]]
        try:
            ok, note = t["grade"](r["content"])
        except Exception as e:
            ok, note = False, f"grader error: {e}"
        src = "auto"
        m = manual.get(label, {}).get(t["id"])
        if m is not None:
            ok, note, src = m["pass"], m["note"], "manual"
        tps = r["eval_count"] / r["eval_duration_s"] if r["eval_duration_s"] else 0
        rows.append({"id": t["id"], "tier": t["tier"], "category": t["category"], "title": t["title"],
                     "pass": bool(ok), "note": note, "graded": src, "tokens": r["eval_count"],
                     "thinking_chars": len(r.get("thinking") or ""), "wall_s": round(r["wall_s"], 2),
                     "tok_s": round(tps, 1), "answer": r["content"]})
    return data["info"], rows

def main():
    manual = load_manual()
    labels = sys.argv[1:]
    paths = [os.path.join(HERE, "results", f"{l}.json") for l in labels] or \
        sorted(p for p in glob.glob(os.path.join(HERE, "results", "*.json")) if not p.endswith("summary.json"))
    summary = {}
    for p in paths:
        info, rows = grade_file(p, manual)
        score = sum(r["pass"] for r in rows)
        tiers = {}
        for r in rows:
            tiers.setdefault(r["tier"], [0, 0])
            tiers[r["tier"]][0] += r["pass"]; tiers[r["tier"]][1] += 1
        tok = sum(r["tokens"] for r in rows)
        gen = sum(r["tokens"] / r["tok_s"] for r in rows if r["tok_s"])
        summary[info["label"]] = {"info": info, "score": score, "tiers": tiers, "rows": rows,
                                  "total_tokens": tok, "avg_tok_s": round(tok / gen, 1) if gen else 0,
                                  "total_wall_s": round(sum(r["wall_s"] for r in rows), 1)}
        print(f"\n### {info['label']}  ({info['model']}, think={info['think']})  SCORE {score}/30  "
              f"| {tok} tokens, {summary[info['label']]['avg_tok_s']} tok/s, {summary[info['label']]['total_wall_s']}s")
        print("    " + "  ".join(f"{k}: {v[0]}/{v[1]}" for k, v in tiers.items()))
        for r in rows:
            print(f"  {r['id']:3s} {'PASS' if r['pass'] else 'FAIL'} [{r['graded']:6s}] {r['title'][:32]:32s} "
                  f"{r['tokens']:5d}tok {r['wall_s']:5.1f}s | {r['note'][:90]}")
    json.dump(summary, open(os.path.join(HERE, "results", "summary.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
