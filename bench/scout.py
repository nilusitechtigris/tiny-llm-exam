"""Quick warm-up used to pick the model: 6 short probes (not part of the 30 tasks), thinking on and off.

usage: python3 scout.py <ollama-model> [<ollama-model> ...]
"""
import json, time, urllib.request, sys
PROBES = [
 ("24 x 26", "What is 24 × 26? End with 'Final answer: <number>'.", lambda a: "624" in a.split("Final answer")[-1]),
 ("Tom brothers", "Tom has 4 sisters. Each of his sisters has exactly 1 brother. How many brothers does Tom have? End with 'Final answer: <number>'.", lambda a: a.split("Final answer")[-1].strip(": *").startswith("0")),
 ("Feb+Mar leap", "How many days are in February and March combined in a leap year? End with 'Final answer: <number>'.", lambda a: "60" in a.split("Final answer")[-1]),
 ("Capital Canada", "What is the capital of Canada? One word.", lambda a: "ottawa" in a.lower()),
 ("JSON city", "Return only JSON with keys \"city\" and \"country\" for this sentence: 'I flew into Lyon, France on Tuesday.'", lambda a: '"lyon"' in a.lower() and '"france"' in a.lower()),
 ("Reverse word", "Spell the word 'planet' backwards. Only output the result.", lambda a: "tenalp" in a.lower()),
]
def chat(model, prompt, think):
    body = {"model": model, "messages":[{"role":"user","content":prompt}], "stream": False,
            "options":{"seed":7, "num_ctx":8192, "num_predict":4096}}
    if think is not None: body["think"] = think
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    t=time.time(); r=json.load(urllib.request.urlopen(req, timeout=600)); dt=time.time()-t
    return r["message"].get("content",""), r.get("eval_count",0), dt
def caps(model):
    req = urllib.request.Request("http://localhost:11434/api/show", data=json.dumps({"model":model}).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req)).get("capabilities", [])
for model in sys.argv[1:]:
    for think in ((True, False) if "thinking" in caps(model) else (None,)):
        ok=0; toks=0; tt=0
        for name, p, chk in PROBES:
            a, n, dt = chat(model, p, think); toks+=n; tt+=dt
            good = chk(a); ok+=good
            print(f"  {model:22s} think={think!s:5s} {name:15s} {'PASS' if good else 'FAIL'} {n:5d}tok {dt:5.1f}s | {a.strip()[-70:]!r}", flush=True)
        print(f"== {model} think={think}: {ok}/{len(PROBES)}  {toks} tok  {tt:.1f}s  ({toks/tt:.0f} tok/s)\n", flush=True)
