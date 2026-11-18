"""Run the 30 tasks against a local Ollama model and save raw outputs.

usage: python3 run.py <ollama-model> <label> [--think on|off]
"""
import json, os, sys, time, urllib.request, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasks import TASKS

OLLAMA = "http://localhost:11434"

def post(path, body, timeout=900):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def main():
    model, label = sys.argv[1], sys.argv[2]
    think = None
    if "--think" in sys.argv:
        think = sys.argv[sys.argv.index("--think") + 1] == "on"
    show = post("/api/show", {"model": model})
    info = {"model": model, "label": label, "think": think,
            "params": show.get("model_info", {}).get("general.parameter_count"),
            "quant": show.get("details", {}).get("quantization_level"),
            "family": show.get("details", {}).get("family")}
    # warm-up so load time doesn't skew task 1
    post("/api/chat", {"model": model, "messages": [{"role": "user", "content": "hi"}], "stream": False,
                       "options": {"num_predict": 1, "num_ctx": 16384}, **({"think": False} if think is not None else {})})
    ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
    info["ollama_ps"] = ps
    results = []
    t0 = time.time()
    for t in TASKS:
        body = {"model": model, "messages": [{"role": "user", "content": t["prompt"]}], "stream": False,
                "options": {"seed": 42, "num_ctx": 16384, "num_predict": 8192}}
        if think is not None:
            body["think"] = think
        s = time.time()
        r = post("/api/chat", body)
        wall = time.time() - s
        msg = r.get("message", {})
        rec = {"id": t["id"], "content": msg.get("content", ""), "thinking": msg.get("thinking", ""),
               "eval_count": r.get("eval_count", 0), "prompt_eval_count": r.get("prompt_eval_count", 0),
               "eval_duration_s": r.get("eval_duration", 0) / 1e9, "wall_s": wall,
               "done_reason": r.get("done_reason")}
        results.append(rec)
        print(f"{label:24s} {t['id']:3s} {rec['eval_count']:5d} tok {wall:6.1f}s  {rec['done_reason']}", flush=True)
    info["total_wall_s"] = time.time() - t0
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", f"{label}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"info": info, "results": results}, open(out, "w"), indent=1, ensure_ascii=False)
    print("saved", out)

if __name__ == "__main__":
    main()
