"""30 benchmark tasks for tiny local LLMs, with automatic graders.

Each task: id, tier, category, title, prompt, grade(answer)->(bool, note).
Tasks marked manual=True get an automatic first-pass grade that a human reviews
(see manual_grades.json).
"""
import json, re, subprocess, sys, sqlite3, tempfile, os

FA = "End your reply with 'Final answer: {}'."

# ---------- helpers ----------
def unbox(s):
    """Replace \\boxed{...} with its contents, handling nested braces like \\boxed{\\frac{5}{36}}."""
    while "\\boxed{" in s:
        i = s.index("\\boxed{"); j = i + len("\\boxed{"); depth = 1; k = j
        while k < len(s) and depth:
            depth += {"{": 1, "}": -1}.get(s[k], 0); k += 1
        s = s[:i] + s[j:k - 1] + s[k:]
    return s

def final(a):
    """Text after the last 'Final answer', cleaned of markdown/LaTeX."""
    parts = re.split(r"final answer", a, flags=re.I)
    seg = parts[-1] if len(parts) > 1 else a.strip().splitlines()[-1] if a.strip() else ""
    seg = unbox(seg)
    seg = re.sub(r"\\d?frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", seg)
    seg = seg.replace("**", "").replace("$", " ").replace("\\", " ")
    return seg.strip(" :*\n\t")

def nums(s):
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", s)]

def num_is(val, tol=0.011):
    def g(a):
        seg = final(a)
        ns = nums(seg)
        ok = bool(ns) and abs(ns[0] - val) < tol
        return ok, f"final: {seg[:60]!r}"
    return g

def code_of(a):
    m = re.findall(r"```(?:python|py|sql|sqlite)?\s*\n(.*?)```", a, flags=re.S | re.I)
    return (max(m, key=len) if m else a).strip()

def run_py(code, tests, timeout=10):
    src = code + "\n\n" + "\n".join(f"assert {t}, {t!r}" for t in tests) + "\nprint('ALL_OK')\n"
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.py")
        open(p, "w").write(src)
        try:
            r = subprocess.run([sys.executable, "-I", p], capture_output=True, text=True, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return False, "timeout"
    if "ALL_OK" in r.stdout:
        return True, f"{len(tests)}/{len(tests)} tests passed"
    err = (r.stderr.strip().splitlines() or ["?"])[-1]
    return False, f"failed: {err[:120]}"

def py_tests(tests, forbid=()):
    def g(a):
        c = code_of(a)
        for f in forbid:
            if f in c:
                return False, f"uses forbidden {f}"
        return run_py(c, tests)
    return g

# ---------- task-specific graders ----------
RED = {"strawberry", "strawberries", "cherry", "cherries", "raspberry", "raspberries", "apple", "apples",
       "red apple", "red apples", "watermelon", "watermelons", "pomegranate", "pomegranates", "cranberry",
       "cranberries", "red currant", "redcurrant", "red currants", "tomato", "tomatoes", "red grapes",
       "red grape", "lingonberry", "lingonberries", "goji berry", "goji berries", "red plum", "plum",
       "blood orange", "lychee", "dragon fruit", "dragonfruit"}

def g_fruits(a):
    s = a.strip()
    if not re.fullmatch(r"[a-z ]+(, ?[a-z ]+){2}", s):
        return False, f"format wrong: {s[:60]!r}"
    items = [x.strip() for x in s.split(",")]
    bad = [x for x in items if x not in RED]
    return (not bad), ("ok" if not bad else f"not red fruit: {bad}")

def g_summary(a):
    s = a.strip()
    words = len(s.split())
    sentences = len(re.findall(r"[.!?](\s|$)", s))
    low = s.lower()
    facts = ("chat" in low) and any(k in low for k in ("response", "faster", "minute", "satisfaction")) \
        and any(k in low for k in ("stress", "staff", "hire", "agents"))
    ok = words <= 30 and sentences <= 1 and facts
    return ok, f"{words} words, {sentences} sentence(s), key facts={'yes' if facts else 'no'}"

def g_sql(a):
    q = code_of(a).strip().rstrip(";")
    db = sqlite3.connect(":memory:")
    db.execute("create table orders(customer_id integer, amount real)")
    rows = [(1, 50), (2, 200), (3, 75), (1, 60), (4, 10), (2, 5), (3, 90), (5, 300), (4, 15)]
    db.executemany("insert into orders values (?,?)", rows)
    try:
        cur = db.execute(q)
        got = [tuple(r) for r in cur.fetchall()]
        cols = [d[0].lower() for d in cur.description]
    except Exception as e:
        return False, f"SQL error: {e}"
    want = [(5, 300.0), (2, 205.0), (3, 165.0)]
    ok = [(int(r[0]), float(r[1])) for r in got] == want if got and len(got[0]) >= 2 else False
    return ok and cols[:2] == ["customer_id", "total"], f"rows={got} cols={cols}"

def g_json(a):
    s = code_of(a)
    try:
        d = json.loads(s[s.find("{"): s.rfind("}") + 1])
    except Exception as e:
        return False, f"invalid JSON: {e}"
    ok = (set(d) == {"name", "age", "job", "current_city"} and d["name"] == "Maria Lopez"
          and d["age"] == 34 and isinstance(d["age"], int) and "architect" in str(d["job"]).lower()
          and d["current_city"] == "Berlin")
    return ok, json.dumps(d)

def g_regex_answer(pattern, label):
    def g(a):
        seg = final(a)
        return bool(re.search(pattern, seg, flags=re.I)), f"final: {seg[:60]!r}"
    return g

def g_ball(a):
    seg = final(a).lower()
    ok = bool(re.search(r"(^|[^\d.])0?\.05\b|\b5 ?(cents|¢)", seg)) and "0.10" not in seg
    return ok, f"final: {seg[:60]!r}"

def g_email(a):
    low = a.lower()
    ok = "monday" in low and "friday" in low and "10" in low
    return ok, "mentions Friday, Monday, 10am" if ok else "missing Friday/Monday/10am"

def g_time(a):
    seg = final(a).lower().replace(".", "")
    ok = bool(re.search(r"\b0?6:30\s*(am|a m)?\b", seg)) and "pm" not in seg and "18:30" not in seg
    return ok, f"final: {seg[:60]!r}"

def g_honest(a):
    low = a.lower()
    hedges = ("hasn't", "has not", "not yet", "future", "don't have", "do not have", "no information",
              "cannot", "can't", "unable", "knowledge cutoff", "will take place", "will be held",
              "scheduled", "hasn’t", "haven't", "not taken place", "not occurred", "upcoming", "yet to")
    ok = any(h in low for h in hedges)
    return ok, "declines / flags future event" if ok else "states a result as fact"

def g_lipogram(a):
    s = a.strip().strip('"').strip()
    words = [w for w in re.findall(r"[A-Za-z']+", s)]
    has_e = "e" in s.lower()
    ok = len(words) == 10 and not has_e
    return ok, f"{len(words)} words, contains 'e': {has_e} -> {s[:80]!r}"

def g_knights(a):
    seg = final(a).lower()
    ok = bool(re.search(r"a is a knight.*b is a knave", seg))
    return ok, f"final: {seg[:70]!r}"

# ---------- the 30 tasks ----------
TASKS = [
 # ---------------- EASY ----------------
 dict(id="E1", tier="Easy", category="Knowledge", title="Capital of Australia",
      prompt="What is the capital of Australia? Answer in one word.",
      grade=lambda a: ("canberra" in a.lower(), a.strip()[:40])),
 dict(id="E2", tier="Easy", category="Math", title="17 × 23",
      prompt="What is 17 × 23? " + FA.format("<number>"), grade=num_is(391)),
 dict(id="E3", tier="Easy", category="Translation", title="English → Spanish",
      prompt="Translate into Spanish: 'The library opens at nine in the morning.' Only output the translation.",
      grade=lambda a: (all(k in a.lower() for k in ("biblioteca", "abre", "nueve")) and ("mañana" in a.lower() or "manana" in a.lower()), a.strip()[:70])),
 dict(id="E4", tier="Easy", category="Classification", title="Review sentiment",
      prompt="Classify the sentiment of this review as positive, negative, or neutral. Reply with one word.\n\n"
             "Review: \"The battery died after two days and customer support never replied.\"",
      grade=lambda a: ("negative" in a.lower() and "positive" not in a.lower(), a.strip()[:30])),
 dict(id="E5", tier="Easy", category="Writing", title="Fix grammar",
      prompt="Correct the grammar and capitalization in this sentence. Only output the corrected sentence.\n\n"
             "she don't like going to school on mondays",
      grade=lambda a: (bool(re.search(r"She (doesn't|does not|doesn’t) like", a)) and bool(re.search(r"\bMondays?\b", a)), a.strip()[:70])),
 dict(id="E6", tier="Easy", category="Math", title="3.5 hours in minutes",
      prompt="How many minutes are in 3.5 hours? " + FA.format("<number>"), grade=num_is(210)),
 dict(id="E7", tier="Easy", category="Instruction following", title="Exactly 3 red fruits, strict format",
      prompt="Name exactly three fruits that are usually red. Output them in lowercase, separated by commas, "
             "with nothing else — no numbering, no extra words, no period.",
      grade=g_fruits),
 dict(id="E8", tier="Easy", category="Summarization", title="One-sentence summary", manual=True,
      prompt="Summarize the following text in exactly one sentence of at most 30 words.\n\n"
             "Our company switched its customer support from email to live chat in March. In the first three months, "
             "average response time dropped from 9 hours to 4 minutes, and customer satisfaction scores rose from 71% "
             "to 88%. However, support staff reported higher stress levels because chats arrive continuously, so "
             "management plans to hire two additional agents in the autumn.",
      grade=g_summary),
 # ---------------- MEDIUM ----------------
 dict(id="M1", tier="Medium", category="Math", title="Discount + sales tax",
      prompt="A jacket costs $80. It is discounted by 25%, and then 8% sales tax is added to the discounted price. "
             "What is the final price? " + FA.format("<number>"), grade=num_is(64.80)),
 dict(id="M2", tier="Medium", category="Coding", title="SQL: top 3 customers",
      prompt="Table `orders` has columns customer_id (INTEGER) and amount (REAL). Write a SQLite query that returns "
             "the top 3 customers by total order amount, with columns named customer_id and total, highest total first. "
             "Only output the SQL.",
      grade=g_sql),
 dict(id="M3", tier="Medium", category="Extraction", title="Text → JSON",
      prompt="Extract the information below into JSON with exactly these keys: \"name\" (string), \"age\" (integer), "
             "\"job\" (string), \"current_city\" (string). Output only the JSON.\n\n"
             "Text: \"Maria Lopez, a 34-year-old architect, moved from Madrid to Berlin last spring.\"",
      grade=g_json),
 dict(id="M4", tier="Medium", category="Coding", title="Python: palindrome check",
      prompt="Write a Python function `is_palindrome(s: str) -> bool` that returns True if s is a palindrome, "
             "ignoring case, spaces and punctuation. Only output the code.",
      grade=py_tests(["is_palindrome('A man, a plan, a canal: Panama') is True", "is_palindrome('race a car') is False",
                      "is_palindrome('') is True", "is_palindrome(\"No 'x' in Nixon\") is True",
                      "is_palindrome('abca') is False", "is_palindrome('12321') is True"])),
 dict(id="M5", tier="Medium", category="Reasoning", title="Weekday in 100 days",
      prompt="Today is Wednesday. What day of the week will it be 100 days from today? " + FA.format("<day>"),
      grade=g_regex_answer(r"friday", "Friday")),
 dict(id="M6", tier="Medium", category="Trick question", title="Bat and ball",
      prompt="A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost? "
             + FA.format("<amount in dollars>"),
      grade=g_ball),
 dict(id="M7", tier="Medium", category="Trick question", title="R's in 'strawberry'",
      prompt="How many times does the letter 'r' appear in the word 'strawberry'? " + FA.format("<number>"),
      grade=num_is(3)),
 dict(id="M8", tier="Medium", category="Trick question", title="Machines & widgets",
      prompt="If 5 machines take 5 minutes to make 5 widgets, how many minutes would 100 machines take to make "
             "100 widgets? " + FA.format("<number>"), grade=num_is(5)),
 dict(id="M9", tier="Medium", category="Writing", title="Polite decline email", manual=True,
      prompt="Write a polite email of exactly 3 sentences declining a meeting invitation for Friday and proposing "
             "Monday at 10am instead. Do not include a subject line.",
      grade=g_email),
 # ---------------- HARD ----------------
 dict(id="H1", tier="Hard", category="Math", title="Sum of primes < 50",
      prompt="What is the sum of all prime numbers less than 50? " + FA.format("<number>"), grade=num_is(328)),
 dict(id="H2", tier="Hard", category="Logic puzzle", title="Mislabeled boxes",
      prompt="Three boxes are labeled 'Apples', 'Oranges' and 'Mixed'. Every label is wrong. You take one fruit "
             "from the box labeled 'Mixed' and it is an apple. What does the box labeled 'Oranges' contain? "
             + FA.format("<Apples, Oranges or Mixed>"),
      grade=g_regex_answer(r"^\W*mixed", "Mixed")),
 dict(id="H3", tier="Hard", category="Trick question", title="Sally's sisters",
      prompt="Sally has 3 brothers. Each of her brothers has 2 sisters. How many sisters does Sally have? "
             + FA.format("<number>"), grade=num_is(1)),
 dict(id="H4", tier="Hard", category="Coding", title="Longest unique substring",
      prompt="Write a Python function `longest_unique_substring(s: str) -> int` that returns the length of the "
             "longest substring without repeating characters. Only output the code.",
      grade=py_tests(["longest_unique_substring('abcabcbb') == 3", "longest_unique_substring('bbbbb') == 1",
                      "longest_unique_substring('pwwkew') == 3", "longest_unique_substring('') == 0",
                      "longest_unique_substring('dvdf') == 3", "longest_unique_substring('abba') == 2",
                      "longest_unique_substring('tmmzuxt') == 5"])),
 dict(id="H5", tier="Hard", category="Coding", title="Find & fix the bug",
      prompt="This Python function should return the average of a list of numbers, but it returns wrong results. "
             "Find the bug and output only the corrected function.\n\n"
             "def average(nums):\n    total = 0\n    for i in range(1, len(nums)):\n        total += nums[i]\n"
             "    return total / len(nums)",
      grade=py_tests(["average([2, 4, 6]) == 4", "average([5]) == 5", "average([1, 2, 3, 4]) == 2.5"])),
 dict(id="H6", tier="Hard", category="Math", title="Dice probability",
      prompt="Two fair six-sided dice are rolled. What is the probability that their sum is exactly 8? Give the "
             "answer as a simplified fraction. " + FA.format("<fraction>"),
      grade=g_regex_answer(r"\b5\s*/\s*36\b|frac\{5\}\{36\}|frac 5 36", "5/36")),
 dict(id="H7", tier="Hard", category="Reasoning", title="Time zones",
      prompt="A flight departs New York at 6:00 PM local time (UTC−5) and the flight lasts 7 hours 30 minutes. "
             "What is the local time in London (UTC+0) when it lands? " + FA.format("<time>"),
      grade=g_time),
 dict(id="H8", tier="Hard", category="Honesty", title="Don't hallucinate (future event)", manual=True,
      prompt="Who won the 2030 FIFA World Cup final, and what was the score?",
      grade=g_honest),
 # ---------------- EXPERT ----------------
 dict(id="X1", tier="Expert", category="Math", title="Inclusion–exclusion counting",
      prompt="How many positive integers less than or equal to 1000 are divisible by 3 or 5, but not by 7? "
             + FA.format("<number>"), grade=num_is(401)),
 dict(id="X2", tier="Expert", category="Constrained writing", title="10 words, no letter 'e'",
      prompt="Write one sentence about the ocean that has exactly 10 words and does not contain the letter 'e' "
             "anywhere. Output only the sentence.",
      grade=g_lipogram),
 dict(id="X3", tier="Expert", category="Coding", title="Expression parser (no eval)",
      prompt="Write a Python function `evaluate(expr: str) -> float` that evaluates an arithmetic expression "
             "containing non-negative numbers, +, -, *, / and parentheses, respecting operator precedence. "
             "Do not use eval() or exec(). Only output the code.",
      grade=py_tests(["abs(evaluate('2+3*4') - 14) < 1e-9", "abs(evaluate('(2+3)*4') - 20) < 1e-9",
                      "abs(evaluate('10/4') - 2.5) < 1e-9", "abs(evaluate('2*(3+(4-1))/3') - 4) < 1e-9",
                      "abs(evaluate('  7 - 2 - 1 ') - 4) < 1e-9", "abs(evaluate('3.5*2') - 7) < 1e-9"],
                     forbid=("eval(", "exec("))),
 dict(id="X4", tier="Expert", category="Logic puzzle", title="Knights & knaves",
      prompt="On an island, knights always tell the truth and knaves always lie. A says: 'B is a knave.' "
             "B says: 'A and I are both knights.' What are A and B? "
             + FA.format("A is a <knight/knave>, B is a <knight/knave>"),
      grade=g_knights),
 dict(id="X5", tier="Expert", category="Reading data", title="Net spend with refund",
      prompt="Here is a list of purchases:\n"
             "1. Priya — headphones — $59.99\n2. Tom — coffee beans — $18.50\n3. Priya — notebook — $4.25\n"
             "4. Lena — running shoes — $120.00\n5. Tom — mug — $12.00\n6. Priya — refund for headphones — -$59.99\n"
             "7. Lena — socks — $9.50\n8. Priya — backpack — $45.00\n\n"
             "What is Priya's net total spending after the refund? " + FA.format("<amount>"),
      grade=num_is(49.25)),
]

assert len(TASKS) == 30 and len({t["id"] for t in TASKS}) == 30
