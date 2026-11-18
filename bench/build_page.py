"""Build docs/index.html (interactive results page) and the two 1080x1350 image cards from results/summary.json.

Run grade.py first. build.sh runs the whole chain and renders the PNGs into assets/."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
from tasks import TASKS

S = json.load(open(os.path.join(HERE, "results", "summary.json")))
NAMES = {
    "lfm3-1.7b-thinking": ("LFM3 1.7B · thinking", "Liquid AI · 1.1 GB"),
    "lfm3-1.7b-fast": ("LFM3 1.7B · no thinking", "same model, answers directly"),
    "gemma3-1b": ("Gemma3 1B", "Google · 0.8 GB"),
    "qwen3-0.6b-thinking": ("Qwen3 0.6B · thinking", "Alibaba · 0.5 GB"),
}
runs = {}
for k, (name, sub) in NAMES.items():
    v = S[k]
    runs[k] = {"name": name, "sub": sub, "score": v["score"], "tiers": v["tiers"],
               "rows": [{x: r[x] for x in ("id", "tier", "category", "title", "pass", "note", "graded", "tokens", "wall_s", "answer")}
                        for r in v["rows"]]}

# warm-up probe (6 questions, not part of the 30); best of thinking on/off where the model has both
scout = [
    dict(model="LFM3 1.7B", maker="Liquid AI", params="1.7B", disk="1.1 GB", score="6/6", pick=True),
    dict(model="Qwen3 1.7B", maker="Alibaba", params="2.0B", disk="1.4 GB", score="5/6"),
    dict(model="Qwen3.5 2B", maker="Alibaba", params="1.9B", disk="1.9 GB", score="4/6"),
    dict(model="Gemma3 1B", maker="Google", params="1.0B", disk="0.8 GB", score="4/6"),
    dict(model="Qwen3 0.6B", maker="Alibaba", params="0.6B", disk="0.5 GB", score="4/6"),
    dict(model="Granite4 350M", maker="IBM", params="0.35B", disk="0.7 GB", score="3/6"),
    dict(model="Qwen3.5 0.8B", maker="Alibaba", params="0.8B", disk="1.2 GB", score="2/6"),
    dict(model="Gemma3 270M", maker="Google", params="0.27B", disk="0.3 GB", score="2/6"),
]

copy = {
    "eyebrow": "Offline · 1.1 GB · Mac mini",
    "headline": "A 1.1 GB AI model took a 30-question exam on my Mac mini",
    "lede": "LFM3 1.7B from Liquid AI, running fully offline through Ollama on a Mac mini (M4 Pro). No cloud and no API key. "
            "The 30 tasks run from easy to expert: knowledge, math, code that has to actually run, logic puzzles and trick questions.",
    "scoreNote": "LFM3 1.7B · thinking on",
    "stats": [["1.1 GB", "download size"], ["1.3 GB", "memory while running"],
              ["119 tok/s", "generation speed"], ["5 s", "median time per task"]],
    "cmpLede": "Same 30 tasks, same settings. With thinking off, LFM3 answers most tasks in under 2 seconds but loses 3 points. "
               "The two smaller models pass the easy tier and then fall apart on multi-step reasoning. Both also invented a winner "
               "for the 2030 World Cup.",
    "good": [
        "All 8 easy and all 9 medium tasks, including the classic trick questions: bat and ball, the r's in 'strawberry', Sally's sisters.",
        "Code that was actually executed: the SQL query, palindrome check, longest-substring function and bug fix all passed their tests on the first try.",
        "Clean structured output: valid JSON with the right types, and a strict comma-separated list with no extra words.",
        "Multi-step math such as inclusion–exclusion (401) and a time-zone conversion across midnight.",
        "It would not invent a 2030 World Cup result. Both smaller models made one up.",
    ],
    "bad": [
        "The hardest coding task (an expression parser without eval) used the whole 8,192-token budget on thinking and never produced code.",
        "World knowledge is thin. It claimed the 2030 World Cup isn't an official tournament.",
        "Thinking is costly on hard tasks. The 10-word sentence without the letter 'e' took 3,563 tokens (32 s) of thinking.",
        "With thinking off it slips in plain sight. It opened with \"Sydney? No, that's not right…\" before answering Canberra, and it called a 38-word summary \"20 words\".",
    ],
    "method": [
        "<b>Setup.</b> Ollama 0.40.16 on a Mac mini with an Apple M4 Pro and 24 GB of memory. Model tag lfm3:1.7b-q4_K_M (4-bit). "
        "Each task was sent once as a fresh chat with seed 42, a 16K context, an 8,192-token output cap and the model's default sampling settings.",
        "<b>Grading.</b> 27 tasks are graded by code: final-answer checks for math and logic, Python answers run against unit tests, SQL runs "
        "against a real SQLite table and JSON is parsed and compared. The summary, the email and the World Cup question were graded by hand "
        "against criteria written before the run. Review caught two grader bugs (a LaTeX fraction parser, and a translation check that accepted "
        "'closes' for 'opens'). Both fixes apply to every model.",
        "<b>Limits.</b> One sample per task. Thirty tasks show the shape of what a model can do; they are not a leaderboard. "
        "The comparison models are smaller on purpose, because the question is how far down you can go.",
    ],
}
card = {
    "eyebrow": "Offline · 1.1 GB · Mac mini",
    "headline": "I gave a 1.1 GB AI model a 30-question exam.",
    "barsTitle": "Same 30 tasks, other tiny models",
    "footL": "LFM3 1.7B (Liquid AI) · Ollama · Apple M4 Pro",
    "footR": "no internet · no API",
    "notes": [
        ["✗", "The one miss: a math parser without eval(). It thought for 73 seconds and never wrote the code."],
        ["?", "“Who won the 2030 World Cup?” LFM3: no result, it hasn't been played. Gemma3 1B: “Croatia won the match with a score of 4-2.”"],
    ],
}

# The 9 tasks an average person does every week. Text answers are the model's exact words;
# number answers show the model's final result (the full reply is one click away on the page).
star_rows = {r["id"]: r for r in S["lfm3-1.7b-thinking"]["rows"]}
exact = lambda i: star_rows[i]["answer"].strip()
everyday = [
    dict(id="E3", label="Translate", group="text", ask="Translate into Spanish: “The library opens at nine in the morning.”", answer=exact("E3")),
    dict(id="E5", label="Fix grammar", group="text", ask="she don't like going to school on mondays", answer=exact("E5")),
    dict(id="E8", label="Summarize", group="text", ask="Sum up a paragraph about moving customer support to live chat in one sentence of at most 30 words.", answer=exact("E8")),
    dict(id="M9", label="Polite email", group="text", ask="Write a polite 3-sentence email declining Friday's meeting and proposing Monday at 10am.", answer=exact("M9")),
    dict(id="H7", label="Time zones", group="num", ask="A flight leaves New York at 6:00 PM (UTC−5) and lasts 7 h 30 min. What time is it in London when it lands?", answer="6:30 AM, next day"),
    dict(id="X5", label="Expense check", group="num", ask="Eight purchases, one of them a $59.99 refund. What did Priya spend in total?", answer="$49.25"),
    dict(id="M1", label="Shopping math", group="num", ask="An $80 jacket is 25% off, then 8% sales tax is added. Final price?", answer="$64.80"),
    dict(id="M5", label="Calendar", group="num", ask="Today is Wednesday. What day will it be in 100 days?", answer="Friday"),
    dict(id="E6", label="Unit conversion", group="num", ask="How many minutes are in 3.5 hours?", answer="210 minutes"),
]
for e in everyday:
    assert star_rows[e["id"]]["pass"], e["id"]
# shorter wording for the 1080x1350 image (answers stay the model's own words; '…' marks a cut)
card_short = {
    "E3": ("To Spanish: “The library opens at nine in the morning.”", None),
    "E8": ("A paragraph about moving support to live chat, in one sentence of max 30 words.", None),
    "M9": ("Decline Friday's meeting politely, propose Monday 10am, 3 sentences.",
           "…I am unable to attend the meeting scheduled for this Friday. Would it be possible to move our conversation to Monday at 10am, when your schedule allows? …"),
    "H7": ("Leave New York 6:00 PM (UTC−5), fly 7 h 30 min. London time on landing?", "6:30 AM"),
    "X5": ("8 purchases incl. a $59.99 refund. Priya's net spend?", None),
    "M1": ("$80 jacket, 25% off, plus 8% sales tax?", None),
    "M5": ("It's Wednesday. What day in 100 days?", None),
    "E6": ("Minutes in 3.5 hours?", "210 min"),
}
for e in everyday:
    a, b = card_short.get(e["id"], (None, None))
    if a:
        e["cardAsk"] = a
    if b:
        e["cardAnswer"] = b
copy["evTitle"] = "The everyday stuff: 9 out of 9"
copy["evLede"] = ("Nine of the 30 tasks are things most people do every week: translating a sentence, fixing a message, "
                  "writing a polite email, checking a bill. LFM3 got all nine right in a few seconds each, and nothing left the computer. "
                  "Text answers are shown word for word. For the number questions the card shows the final result; click any card for the full reply.")
card2 = {
    "eyebrow": "Same 1.1 GB model · offline",
    "headline": "The everyday stuff it handled.",
    "textTitle": "Words",
    "numTitle": "Quick math",
    "cmpTitle": "Other models, same 9",
    "footL": "LFM3 1.7B (Liquid AI) · Ollama · Apple M4 Pro",
    "footR": "your data never leaves the computer",
}
data = {"star": "lfm3-1.7b-thinking", "order": list(NAMES), "runs": runs, "scout": scout, "copy": copy, "card": card,
        "card2": card2, "everyday": everyday,
        "prompts": {t["id"]: t["prompt"] for t in TASKS}, "firstDetail": "X2"}
blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
PAGE_HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
             '<style>body{margin:0}</style>\n')
outputs = (
    ("templates/report.html", "../docs/index.html", True),          # interactive results page (GitHub Pages)
    ("templates/card-scorecard.html", "build/card-scorecard.html", False),  # sources for assets/*.png
    ("templates/card-everyday.html", "build/card-everyday.html", False),
)
os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
for tpl, out, wrap in outputs:
    html = open(os.path.join(HERE, tpl)).read().replace("__DATA__", blob)
    if wrap:
        html = PAGE_HEAD + html + "\n</html>\n"
    path = os.path.normpath(os.path.join(HERE, out))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(html)
    print("wrote", os.path.relpath(path, os.path.dirname(HERE)), f"({len(html) // 1024} KB)")
