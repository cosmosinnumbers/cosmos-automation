"""Quality control of every post before it is queued and before it is published (owner request, 1/11/2026).

  python tools/post_qc.py                       check every queued item that is still to come (exit 1 on errors)
  python tools/post_qc.py --all                 also items already past
  python tools/post_qc.py --text "..." [--platform threads|ig|fb|tiktok|x] [--kind news|quiz|video|reel]

Two layers, no LLM (owner decision 30/10/2026: posts carry only verifiable data):
1. Blocking errors: site menu text, sentences cut in half, leftover HTML or placeholders, length and format limits of
   each platform, LAUNCH9 (only COSMOS9 exists on Gumroad), Gumroad link without COSMOS9 before 30/11, missing source,
   numbers not found in the source text, recent duplicates, TikTok rules (caption with "Full video on YouTube" and no
   product, link or discount code: owner rule of 26/10/2026), hashtags in Threads posts.
2. Copy score 0-100: hook of the first line (number, question, superlative, short), clarity (whole sentences,
   short ones, one message), numbers ("Cosmos in Numbers"), match with the niche trends of the week
   (research/cosmos/<week>.json: titles of the fastest-growing videos, top Reddit and Instagram posts), source,
   call to action (Gumroad LOOK UP reply on Threads, YouTube on Reels and TikTok).

clean() fixes what can be fixed without rewriting the facts (HTML entities, spaces, LAUNCH9, hashtags on Threads,
a trailing cut sentence); check() is run again after it. threads_build.py uses the score to choose the best news of
the day and drops what does not pass; run_slot.py runs check() at publish time and, for Threads, swaps a blocked
post for a reserve post built from the NASA Planetary Fact Sheet. Every decision goes to logs/qc-log.jsonl.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cosmos"
COSMOS9_UNTIL = date(2026, 11, 30)
MIN_SCORE = 55  # below this a news candidate is not used (another candidate or the reserve post goes out)

LIMITS = {"threads": 500, "x": 280, "ig": 2200, "fb": 5000, "tiktok": 2200}
REPLY_LIMIT = {"threads": 500, "x": 280}

# site menus scraped as text (1/11/2026: the APOD post carried the whole science.nasa.gov/apod navigation bar)
MENU_PHRASE = re.compile(r"astronomy picture of the day discover|discover the cosmos|today[’']s apod|apod archive|"
                         r"each day a different image|tomorrow[’']s picture|skip to (main )?content|cookie (policy|settings)|"
                         r"subscribe to (our )?newsletter|share on (facebook|twitter|x)\b|enable javascript|"
                         r"you might also like|related (articles|stories)|back to top|all rights reserved", re.I)
MENU_WORD = re.compile(r"\b(Archive|Submissions|Index|Search|Calendar|RSS|Discuss|Menu|Login|Subscribe|Newsletter|"
                       r"Contact|Careers|Sitemap)\b")
PLACEHOLDER = re.compile(r"\{[a-z_]+\}|\bTODO\b|\bTBD\b|lorem ipsum|\bundefined\b|\bNone\b|\bnan\b|\[object|\$\{|"
                         r"<[a-z/][^>]*>|&(amp|nbsp|quot|lt|gt|#\d+);", re.I)
# image credit or section heading glued to a sentence ("NASA/JPL-Caltech Twin Travelers In 1977, NASA launched...")
CREDIT_GLUE = re.compile(r"(^|[.!?]\s+)(NASA|ESA|ESO|JPL|STScI|CSA|JAXA)(/[\w.&-]+)+\s+[A-Z]")
CUT_END = re.compile(r"(…|\.\.\.|\b(and|or|the|a|an|of|to|in|with|by|for|from|that|which|is|are|was|at|on|as))$", re.I)
SENT_END = re.compile(r"[.!?…][\"'”’)\]]?$|[\U0001F300-\U0001FAFF☀-➿]$")
SUPERLATIVE = re.compile(r"\b(biggest|largest|smallest|fastest|slowest|hottest|coldest|oldest|youngest|farthest|"
                         r"closest|deepest|brightest|darkest|heaviest|lightest|longest|shortest|first|only|never|"
                         r"impossible|record|times (bigger|larger|faster|heavier|hotter|longer)|than earth|than the sun|"
                         r"why|how|what|you|your|imagine|secret|strange|weird)\b", re.I)
BOILERPLATE = re.compile(r"^(apod:|photo release|press release|organisation release|science release|news release|"
                         r"\d{4} \w+ \d{1,2}\b)", re.I)
STOP = set("""a an the of and or to in on for from with by at as is are was were be been it its this that these those
than then into over under about after before more most very can could will would should may might not no yes
you your we our they their he she his her them us i me my what which who whom why how when where there here
shorts short video videos space science facts fact new just like one two all out up off so do does did has have
had get got make made really much many part please bhai""".split())
WORD = re.compile(r"[a-z][a-z'\-]{2,}")


def _now() -> date:
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import creds
        return creds.now_local().date()
    except Exception:  # noqa: BLE001  (tests and tools without tzdata)
        return date.today()


# ---------- helpers ----------

def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def is_meta_line(p: str) -> bool:
    """Lines that do not need to end with a full stop: source, link, disclosure, credit, CTA."""
    return bool(re.match(r"(source|sources|data|image|credit|read more|full video|narration|code|answer)\b", p, re.I)
                or re.search(r"https?://|gumroad\.com|\.(com|org|io)/|@\w|#\w|COSMOS9", p))


def _is_title(p: str) -> bool:
    return len(p) < 110 and "\n" not in p and not re.search(r"[.!?]\s", p)


def core(text: str) -> str:
    """The prose of a post, without source, link, disclosure and CTA lines."""
    return " ".join(p for p in paragraphs(text) if not is_meta_line(" ".join(p.split()))) or text


def numbers(text: str) -> list[str]:
    return [n.rstrip(".,") for n in re.findall(r"\d[\d,.]*", text) if n.rstrip(".,")]


def missing_numbers(text: str, source: str) -> list[str]:
    """Numbers of the post that are not in the source text (with or without thousands separators). Dates, years
    and the numbers of URLs are ignored."""
    body = re.sub(r"https?://\S+", " ", text)
    body = re.sub(r"\b\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b", " ", body)
    flat = source.replace(",", "").replace(" ", "").replace("\xa0", "")
    out = []
    for n in dict.fromkeys(numbers(body)):
        if re.fullmatch(r"(19|20)\d\d", n) or n in source or n.replace(",", "") in flat:
            continue
        out.append(n)
    return out


def words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOP}


def similarity(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    return len(wa & wb) / max(1, min(len(wa), len(wb))) if wa and wb else 0.0


# ---------- niche trends ----------

_TRENDS: dict[str, float] | None = None


def trends(path: Path | None = None) -> dict[str, float]:
    """Keywords of the week, weighted: titles of the fastest-growing niche videos (by views per day), top Reddit and
    Instagram posts, Google Trends terms that are rising. From the latest research/cosmos/<week>.json."""
    global _TRENDS
    if _TRENDS is not None and path is None:
        return _TRENDS
    files = sorted(RESEARCH.glob("20*-W*.json")) if path is None else [path]
    out: dict[str, float] = {}
    if files:
        try:
            d = json.loads(files[-1].read_text("utf-8"))
        except (OSError, ValueError):
            d = {}
        vids = sorted(d.get("youtube", {}).get("videos", []), key=lambda v: -v.get("views_per_day", 0))[:25]
        for rank, v in enumerate(vids):
            for w in words(re.sub(r"#\S+", " ", v.get("title", ""))):
                out[w] = out.get(w, 0) + 1.0 / (1 + rank / 5)
        for p in d.get("reddit", {}).get("posts", [])[:25]:
            for w in words(p.get("title", "")):
                out[w] = out.get(w, 0) + 0.4
        for posts in d.get("instagram", {}).values():
            for p in posts[:5]:
                for w in words(p.get("caption", "")[:200]):
                    out[w] = out.get(w, 0) + 0.3
        for term, t in d.get("trends", {}).items():
            if t.get("last_4w", 0) or t.get("change", 0) > 0:
                for w in words(term):
                    out[w] = out.get(w, 0) + 1.0 + max(0, t.get("change", 0)) / 50
    top = dict(sorted(out.items(), key=lambda kv: -kv[1])[:60])
    if path is None:
        _TRENDS = top
    return top


# ---------- checks ----------

def errors_of(platform: str, kind: str, text: str, replies: list[str] | None = None, poll: list[str] | None = None,
              source_text: str | None = None, recent: list[str] | None = None, today: date | None = None) -> list[str]:
    """Blocking problems. Empty list = publishable."""
    replies, today = replies or [], today or _now()
    errs = []
    t = " ".join(text.split())
    allt = " ".join([text, *replies])
    if not t:
        return ["empty text"]
    m = MENU_PHRASE.search(allt)
    if m:
        errs.append(f"site menu or boilerplate text ({m.group()!r})")
    mw = sorted(set(MENU_WORD.findall(allt)))
    if len(mw) >= 2:
        errs.append(f"menu words {mw}")
    m = PLACEHOLDER.search(allt)
    if m:
        errs.append(f"leftover placeholder or HTML ({m.group()!r})")
    m = next((m for p in [text, *replies] for q in paragraphs(p) if (m := CREDIT_GLUE.search(q))), None)
    if m:
        errs.append(f"image credit or heading glued to the text ({m.group().strip()!r})")
    if re.search(r"\bLAUNCH9\b", allt, re.I):
        errs.append("LAUNCH9 does not exist on Gumroad: the code is COSMOS9")
    gum = [p for p in [text, *replies] if "gumroad.com" in p]
    if today <= COSMOS9_UNTIL and platform in ("threads", "x", "fb") and gum and not any("COSMOS9" in p for p in gum):
        errs.append("Gumroad link without the COSMOS9 code (valid until 30/11/2026)")
    if re.search(r"gumroad\.com(?!/l/(?:look-up|solar-system-20))", allt):
        errs.append("Gumroad link that is not the LOOK UP page")
    if re.search(r"https?://\S*…|https?://\S*\.\.\.", allt):
        errs.append("truncated link")
    lim = LIMITS.get(platform)
    if lim and len(text) > lim:
        errs.append(f"text too long for {platform} ({len(text)} > {lim})")
    for r in replies:
        if platform in REPLY_LIMIT and len(r) > REPLY_LIMIT[platform]:
            errs.append(f"reply too long ({len(r)} > {REPLY_LIMIT[platform]})")
    if poll is not None:
        if not 2 <= len(poll) <= 4 or any(len(o) > 25 or not o.strip() for o in poll) or len(set(poll)) != len(poll):
            errs.append(f"poll options not valid {poll}")
    # whole sentences: every prose paragraph of the post and of the replies ends like a sentence
    paras = paragraphs(text)
    for n, p in enumerate(paras + [q for r in replies for q in paragraphs(r)]):
        flat = " ".join(p.split())
        if is_meta_line(flat) or n == 0 and len(paras) > 1 and _is_title(flat):  # the title line of a post
            continue
        if not SENT_END.search(flat) or CUT_END.search(flat.rstrip(".!?\"'”’) ")) and flat.endswith(("…", "...")):
            errs.append(f"paragraph cut mid-sentence ({flat[-40:]!r})")
        if flat.count("(") != flat.count(")") or flat.count("“") != flat.count("”"):
            errs.append(f"unbalanced brackets or quotes ({flat[:40]!r})")
    body = [p for n, p in enumerate(paras) if not is_meta_line(" ".join(p.split()))
            and not (n == 0 and len(paras) > 1 and _is_title(p))]
    if kind in ("news", "video", "data") and sum(len(p) for p in body) < 80:
        errs.append(f"too little text ({sum(len(p) for p in body)} characters of prose)")
    if kind in ("news", "quiz", "video", "data") and platform in ("threads", "x") \
            and not re.search(r"\b(source|sources|data)\b\s*:|\((NASA|ESA|JPL|ESO)\b", allt, re.I):
        errs.append("no source cited (Source: / Data:)")
    if platform == "threads" and re.search(r"(^|\s)#[A-Za-z]\w+", text):
        errs.append("hashtags in a Threads post (Threads uses one topic tag, set by the API)")
    if platform == "threads" and "gumroad.com" in text and kind in ("news", "quiz", "video", "data"):
        errs.append("Gumroad link in the Threads post itself: it goes in the first reply")
    if platform == "tiktok":
        if not re.search(r"full video on youtube", text, re.I):
            errs.append("TikTok caption without 'Full video on YouTube'")
        if re.search(r"gumroad|look ?up\b|cosmos9|launch9|discount|coupon|\bcode\b|https?://|link in bio", text, re.I):
            errs.append("TikTok caption with product, link or code (owner rule 26/10/2026: never commercial content)")
    if platform == "ig":
        tags = re.findall(r"#\w+", text)
        if len(tags) > 30:
            errs.append(f"{len(tags)} hashtags (Instagram allows 30)")
        if kind in ("reel",) and not re.search(r"full video on youtube", text, re.I):
            errs.append("Reel caption without 'Full video on YouTube'")
    if source_text is not None:
        miss = missing_numbers(" ".join([text, *[r for r in replies if "gumroad" not in r]]), source_text)
        if miss:
            errs.append(f"numbers not found in the source {miss}")
    for old in recent or []:
        if kind == "quiz":  # quizzes share a template: only the same question counts as a duplicate
            q_new, q_old = re.findall(r"Today's quiz.*", text), re.findall(r"Today's quiz.*", old)
            if q_new and q_new == q_old:
                errs.append(f"same quiz question as a recent post ({q_new[0][:50]!r})")
                break
            continue
        if platform in ("ig", "fb", "tiktok"):  # captions share the CTA block: compare the opening line only
            a, b = paragraphs(text)[:1], paragraphs(old)[:1]
            if a and a == b:
                errs.append(f"same caption opening as a recent post ({a[0][:50]!r})")
                break
            continue
        if len(words(core(text))) >= 8 and similarity(core(text), core(old)) >= 0.75:
            errs.append(f"near duplicate of a recent post ({old[:50]!r})")
            break
    return errs


def score(platform: str, kind: str, text: str, replies: list[str] | None = None,
          trend_words: dict[str, float] | None = None) -> tuple[int, dict[str, int]]:
    """Copy score 0-100 with its parts. Not blocking by itself: threads_build drops news below MIN_SCORE."""
    replies = replies or []
    tw = trends() if trend_words is None else trend_words
    paras = paragraphs(text)
    first = re.sub(r"^yesterday's answer:.*", "", paras[0], flags=re.I).strip() if paras else ""
    if not first and len(paras) > 1:
        first = paras[1]
    first = first.split("\n")[0]
    parts = {}
    # hook (30): short, concrete, a number / question / superlative, no press-release label
    h = 0
    h += 8 if len(first) <= 70 else 4 if len(first) <= 100 else 0
    h += 8 if numbers(first) else 0
    h += 7 if "?" in first or SUPERLATIVE.search(first) else 0
    h += 7 if not BOILERPLATE.search(first) else -5
    parts["hook"] = max(0, min(30, h))
    # clarity (20): whole short sentences, one message (max 4 sentences in the post body)
    prose = " ".join(p for p in paras if not is_meta_line(" ".join(p.split())))
    ss = [s for s in re.split(r"(?<=[.!?])\s+", prose) if s.strip()]
    avg = sum(len(s.split()) for s in ss) / len(ss) if ss else 0
    c = 20
    c -= 6 if avg > 28 else 3 if avg > 22 else 0
    c -= 5 if len(ss) > 4 else 0
    c -= 6 if re.search(r"\b(et al|i\.e\.|e\.g\.|cf\.)", prose) else 0
    c -= 4 if len(re.findall(r"\([^)]{25,}\)", prose)) > 1 else 0
    parts["clarity"] = max(0, c)
    # numbers (15): the channel promise
    n = len([x for x in numbers(prose) if not re.fullmatch(r"(19|20)\d\d", x)])
    parts["numbers"] = 15 if n >= 2 else 10 if n == 1 else 5 if kind == "quiz" else 0
    # trends (15): keywords of the week's fastest-growing niche content
    hit = words(text) & set(tw)
    weight = sum(tw[w] for w in hit)
    top = sorted(tw.values(), reverse=True)[:3]
    parts["trend"] = 0 if not tw else min(15, round(15 * weight / max(1.0, sum(top))))
    # source (10) and call to action (10)
    allt = " ".join([text, *replies])
    parts["source"] = 10 if re.search(r"\b(source|sources|data)\b\s*:|\((NASA|ESA|JPL|ESO)\b", allt, re.I) else 0
    if platform in ("threads", "x"):
        cta = "gumroad.com/l/look-up" in allt or kind in ("news", "quiz", "video", "data")  # cta.py adds it at publish
    else:
        cta = bool(re.search(r"full video on youtube|look up", allt, re.I))
    parts["cta"] = 10 if cta else 0
    return sum(parts.values()), parts


def clean(text: str, platform: str = "threads") -> str:
    """Safe fixes only: entities and tags, spaces, LAUNCH9, hashtags on Threads, a trailing cut sentence."""
    t = html.unescape(text)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\bLAUNCH9\b", "COSMOS9", t, flags=re.I)
    if platform == "threads":
        t = re.sub(r"(^|\s)#[A-Za-z]\w+", r"\1", t)
    out = []
    for p in re.split(r"\n\s*\n", t):
        lines = [" ".join(line.split()) for line in p.split("\n")]
        p = "\n".join(line for line in lines if line)
        flat = " ".join(p.split())
        if p and not is_meta_line(flat) and not SENT_END.search(flat):
            whole = re.match(r"(.*[.!?][\"'”’)]?)\s", flat + " ")
            p = whole.group(1) if whole and len(whole.group(1)) >= 60 else p
        if p:
            out.append(p)
    return "\n\n".join(out).strip()


def review(item: dict, platform: str, kind: str | None = None, recent: list[str] | None = None,
           source_text: str | None = None, today: date | None = None) -> dict:
    """Errors, score and a cleaned copy of a queue item. 'ok' is True when the item (possibly cleaned) can go out."""
    kind = kind or kind_of(item, platform)
    text = item.get("text") or item.get("caption") or ""
    replies = item.get("replies", [])
    errs = errors_of(platform, kind, text, replies, item.get("poll"), source_text, recent, today)
    fixed = None
    if errs:
        ct, cr = clean(text, platform), [clean(r, platform) for r in replies]
        if (ct, cr) != (text, replies):
            e2 = errors_of(platform, kind, ct, cr, item.get("poll"), source_text, recent, today)
            if len(e2) < len(errs):
                fixed = {"text": ct, "replies": cr}
                errs = e2
    s, parts = score(platform, kind, (fixed or {}).get("text", text), replies)
    return {"ok": not errs, "errors": errs, "score": s, "parts": parts, "fixed": fixed, "kind": kind}


def kind_of(item: dict, platform: str) -> str:
    ref = item.get("ref", "")
    if item.get("poll") or "-quiz-" in ref:
        return "quiz"
    if "-news-" in ref:
        return "news"
    if "-data-" in ref:
        return "data"
    if item.get("short") or re.match(r"th-a\d{4}", ref):
        return "video"
    if item.get("action", "").endswith("reel") or platform == "tiktok":
        return "reel"
    if item.get("action", "").endswith("story"):
        return "story"
    return "post"


def recent_texts(queue: list[dict], at: str, days: int = 14, exclude: str = "") -> list[str]:
    """Texts of the other items of the last `days` days before `at` (same queue), for the duplicate check."""
    try:
        t0 = datetime.strptime(at[:10], "%Y-%m-%d")
    except ValueError:
        return []
    # the same video on another Meta surface (sr-/fr-/si-/sf-<tag>) is cross-posting, not a duplicate (03/11/2026:
    # the Reel FB of c1103-p4-clip-d was blocked because the Reel IG one minute earlier had the same caption)
    same = exclude.split("-", 1)[1] if re.match(r"^(sr|fr|si|sf)-", exclude) else None
    out = []
    for i in queue:
        if i.get("ref") == exclude or not i.get("at") or i["at"] >= at:
            continue
        if same and re.match(r"^(sr|fr|si|sf)-", i.get("ref", "")) and i["ref"].split("-", 1)[1] == same:
            continue
        if (t0 - datetime.strptime(i["at"][:10], "%Y-%m-%d")).days <= days:
            body = i.get("text") or i.get("caption") or ""
            out.append(re.sub(r"^Yesterday's answer:.*?\n\n", "", body, flags=re.S))
    return out


def log(entry: dict):
    if "--dry-run" in sys.argv:
        return
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import creds
        creds.append("qc-log.jsonl", entry)
    except Exception as e:  # noqa: BLE001  (logging must never stop a publication)
        print(f"  qc log not written: {type(e).__name__}")


# ---------- CLI ----------

PLATFORM_OF = {"threads-queue.json": "threads", "x-queue.json": "x", "tiktok-queue.json": "tiktok"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    if "--text" in a:
        p = a[a.index("--platform") + 1] if "--platform" in a else "threads"
        k = a[a.index("--kind") + 1] if "--kind" in a else "news"
        r = review({"text": a[a.index("--text") + 1]}, p, k)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        sys.exit(0 if r["ok"] else 1)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    bad = 0
    for qf in sorted((ROOT / "queues").glob("*-queue.json")):
        queue = json.loads(qf.read_text("utf-8"))
        for it in queue:
            if not ("--all" in a or it.get("at", "") >= now):
                continue
            plat = PLATFORM_OF.get(qf.name) or ("fb" if it.get("action", "").startswith("fb") else "ig")
            if not (it.get("text") or it.get("caption")):
                continue
            r = review(it, plat, recent=recent_texts(queue, it.get("at", ""), exclude=it.get("ref", "")))
            mark = "OK " if r["ok"] else "BAD"
            bad += not r["ok"]
            print(f"{mark} {plat:7} {it.get('at', ''):16} {it['ref']:45} score {r['score']:3} {r['parts']}")
            for e in r["errors"]:
                print(f"      - {e}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
