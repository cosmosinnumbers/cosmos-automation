"""Put the tracked Gumroad links in the profile texts that the APIs allow (run by bio-links.yml).

  python tools/bio_links.py facebook|youtube [--dry-run]
  python tools/bio_links.py audit        # read-only: every profile text, every link in it opened -> reports/bio-links.md

- facebook : Page "website" + "about" (Graph API, token META_JSON; needs pages_manage_metadata).
- youtube  : channel description gets the free sky calendar, LOOK UP and free-PDF lines on top (channels.update, token YOUTUBE_TOKEN_JSON).
Instagram, TikTok, Threads and X bios have no write API: the same links are given to the owner to paste.
The current values are printed first (public text) so a change can be undone by hand. Idempotent.
"""
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "video"))
DRY = "--dry-run" in sys.argv
GR = {"Authorization": "Bearer " + json.loads((ROOT / "secrets" / "gumroad.json").read_text("utf-8"))["access_token"]}


def utm(campaign: str, source: str, medium: str) -> str:
    for u in requests.get("https://api.gumroad.com/v2/utm_links", headers=GR, timeout=60).json().get("utm_links", []):
        if (u["utm_campaign"], u["utm_source"], u["utm_medium"]) == (campaign, source, medium):
            return u["short_url"]
    sys.exit(f"UTM link {campaign}/{source}/{medium} missing: run gumroad-utm create first")


def facebook():
    import creds
    c = creds.load("meta")
    G, pid, tok = "https://graph.facebook.com/v21.0", c["page_id"], c["page_token"]
    cur = requests.get(f"{G}/{pid}", params={"access_token": tok, "fields": "website,about,description"}, timeout=60).json()
    print("current:", json.dumps(cur, ensure_ascii=False))
    free, look = utm("sky-30-nights", "facebook", "post"), utm("look-up", "facebook", "post")
    old = [u.strip() for u in (cur.get("website") or "").split(",") if u.strip()]
    old = [u for u in old if "gumroad.com" not in u and not u.startswith("https://gum.co/u/")]
    base = ["https://cosmosinnumbers.github.io/links.html?src=fb", "https://cosmosinnumbers.github.io/",
            "https://www.tiktok.com/@cosmosinnumbers", "https://www.instagram.com/cosmos.innumbers/"]
    sites = [free, look, *dict.fromkeys([*old, *base])]  # keep the links already there (site, TikTok, Instagram)
    website = ", ".join(sites)
    about = cur.get("about") or ""
    if free not in about:
        about = ("Real space. Real data. Space explainers from real NASA/ESA images and public data. "
                 f"Free sky calendar, The Next 30 Nights: {free} | Full videos: youtube.com/@CosmosinNumbers")
    print("new website:", website, "| about:", len(about), "chars")
    if DRY:
        return
    r = requests.post(f"{G}/{pid}", data={"access_token": tok, "website": website, "about": about}, timeout=60)
    print("facebook:", r.status_code, r.text[:300])


def youtube():
    from ytf import yt_api
    yt = yt_api.service()
    ch = yt.channels().list(part="brandingSettings", mine=True).execute()["items"][0]
    b = ch["brandingSettings"]
    cur = b.get("channel", {}).get("description", "")
    print("current description:\n" + cur + "\n---")
    sky, look = utm("sky-30-nights", "youtube", "description"), utm("look-up", "youtube", "description")
    free = utm("solar-system-20", "youtube", "description")
    head = (f"🔭 Free sky calendar, The Next 30 Nights (what to see this month): {sky}\n"
            f"📘 LOOK UP, our beginner's stargazing guide: {look}\n"
            f"🆓 Free PDF, The Solar System in 20 Numbers: {free}")
    if cur.startswith(head):
        print("already done")
        return
    rest = cur.split("\n")
    while rest and (not rest[0].strip() or "gum.co/" in rest[0] or "gumroad.com/l/" in rest[0]):  # our old link lines
        rest.pop(0)
    new = head + "\n\n" + "\n".join(rest)
    if len(new) > 1000:  # YouTube refuses a channel description over 1000 characters: the third line goes
        new = head.rsplit("\n", 1)[0] + "\n\n" + "\n".join(rest)
    if len(new) > 1000:
        sys.exit(f"description would be {len(new)} characters (max 1000): shorten it by hand in YouTube Studio")
    print("new description:\n" + new)
    if DRY:
        return
    b.setdefault("channel", {})["description"] = new
    yt.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": b}).execute()
    print("youtube: updated")


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
URL = __import__("re").compile(r"(?:https?://)?(?:[\w-]+\.)+(?:com|co|io|net|me|org)(?:/[^\s,|\"'<>)]*)?", __import__("re").I)


def open_link(u: str, tracked: dict) -> dict:
    """Follows a link the way a visitor would. tracked: short_url -> (product, source, medium)."""
    full = u if u.startswith("http") else "https://" + u
    out = {"url": u, "tracked": tracked.get(full.rstrip("/"))}
    try:
        r = requests.get(full, headers=UA, timeout=40, allow_redirects=True)
        out.update(status=r.status_code, final=r.url.split("&utm_")[0][:140], utm="utm_source=" in r.url or bool(out["tracked"]))
        if "gumroad.com/l/" in r.url:
            out["product"] = r.url.split("/l/")[1].split("?")[0].split("/")[0]
            out["buyable"] = 'property="og:title"' in r.text and "Page not found" not in r.text[:3000]
    except requests.RequestException as e:
        out.update(status=0, final=type(e).__name__)
    return out


def profiles() -> dict:
    """Public profile texts, read with the tokens we already have (read-only). A missing one is reported, not guessed."""
    import creds
    out = {}

    def grab(name, fn):
        try:
            out[name] = fn()
        except (Exception, SystemExit) as e:  # one profile that cannot be read must not hide the others
            out[name] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}

    def yt():
        from ytf import yt_api
        ch = yt_api.service().channels().list(part="brandingSettings,snippet", mine=True).execute()["items"][0]
        return {"text": ch["brandingSettings"].get("channel", {}).get("description", ""),
                "note": "i 'link del canale' sotto la descrizione non sono leggibili via API: vanno guardati in YouTube Studio"}

    def meta(kind):
        c = creds.load("meta")
        G, tok = "https://graph.facebook.com/v21.0", c["page_token"]
        if kind == "fb":
            d = requests.get(f"{G}/{c['page_id']}", params={"access_token": tok, "fields": "website,about,description"}, timeout=60).json()
            return {"text": " | ".join(str(d.get(k, "")) for k in ("website", "about", "description"))}
        d = requests.get(f"{G}/{c['ig_user_id']}", params={"access_token": tok, "fields": "biography,website,username"}, timeout=60).json()
        if "error" in d:
            raise RuntimeError(d["error"].get("message", ""))
        return {"text": f"{d.get('website', '')} | {d.get('biography', '')}"}

    def threads():
        import threads_api
        d = threads_api.call("GET", "/v1.0/me", fields="username,threads_biography", access_token=threads_api.cfg()["token"])
        return {"text": d.get("threads_biography", ""), "note": "il campo link del profilo Threads non è leggibile via API"}

    def page(u):
        r = requests.get(u, headers=UA, timeout=40)
        import re
        links = re.findall(r"https://(?:gum\.co/u/\w+|cosmosinnumbers\.gumroad\.com/l/[\w-]+[^\"'\s<]*)", r.text)
        return {"text": " ".join(dict.fromkeys(links)), "status": r.status_code}

    def tiktok():
        import re
        r = requests.get("https://www.tiktok.com/@cosmosinnumbers", headers=UA, timeout=40)
        m = re.search(r'"bioLink":\{"link":"([^"]+)"', r.text)
        sig = re.search(r'"signature":"([^"]*)"', r.text)
        if not (m or sig):
            raise RuntimeError(f"pagina non leggibile da qui (HTTP {r.status_code}): va guardata dal browser")
        return {"text": f"{m.group(1) if m else ''} | {sig.group(1) if sig else ''}".encode().decode("unicode_escape", "ignore")}

    grab("YouTube (descrizione canale)", yt)
    grab("Facebook (sito e informazioni)", lambda: meta("fb"))
    grab("Instagram (bio e link)", lambda: meta("ig"))
    grab("Threads (bio)", threads)
    grab("TikTok (bio e link)", tiktok)
    grab("Sito: links.html", lambda: page("https://cosmosinnumbers.github.io/links.html"))
    grab("Sito: home", lambda: page("https://cosmosinnumbers.github.io/"))
    return out


def audit():
    import datetime
    reg = json.loads((ROOT / "config" / "gumroad-utm.json").read_text("utf-8"))
    tracked = {v["short_url"]: tuple(k.split("|")) for k, v in reg.items()}
    lines = [f"# Link nelle bio, controllo del {datetime.date.today().isoformat()}", "",
             "Scritto da `tools/bio_links.py audit`: ogni testo di profilo letto con le API, ogni link aperto come farebbe un visitatore.", ""]
    for name, p in profiles().items():
        lines += [f"## {name}", ""]
        if "error" in p:
            lines += [f"- NON LETTO: {p['error']}", ""]
            continue
        lines += ["> " + (p["text"].strip().replace("\n", " / ")[:600] or "(vuoto)"), ""]
        found = list(dict.fromkeys(m.group(0).rstrip(".") for m in URL.finditer(p["text"])))
        if not any("gum" in u for u in found):
            lines.append("- **Nessun link Gumroad in questo testo.**")
        for u in found:
            if not any(k in u for k in ("gum.co", "gumroad", "github.io")):
                continue
            o = open_link(u, tracked)
            t = "tracciato (" + "/".join(o["tracked"]) + ")" if o["tracked"] else ("tracciato (utm)" if o.get("utm") else "NON tracciato")
            buy = "" if "buyable" not in o else (", pagina prodotto aperta" if o["buyable"] else ", ATTENZIONE: la pagina prodotto non si apre")
            lines.append(f"- `{u}` → HTTP {o['status']}, arriva a `{o.get('product') or o['final']}`, {t}{buy}")
        if p.get("note"):
            lines.append(f"- Nota: {p['note']}")
        lines.append("")
    lines += ["## Tutti i link corti registrati", ""]
    for short, key in tracked.items():
        o = open_link(short, tracked)
        ok = o["status"] == 200 and o.get("product") == key[0] and o.get("buyable")
        lines.append(f"- {'ok' if ok else 'PROBLEMA'} · {'/'.join(key)} · {short} → HTTP {o['status']} `{o.get('product') or o['final']}`")
    out = ROOT / "reports" / "bio-links.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    {"facebook": facebook, "youtube": youtube, "audit": audit}[sys.argv[1]]()
