"""Real footage and stock b-roll for Cosmos in Numbers, registered in assets.yaml with licence and credit.

  python stock.py search nasa-video "<query>" [--n 8]            NASA Image and Video Library (no key)
  python stock.py get nasa-video <nasa_id> <video_dir> [--key name]
  python stock.py search pixabay-video "<query>" [--n 8]         needs secrets/pixabay_key.txt
  python stock.py get pixabay-video <id> <video_dir> [--key name]

  python stock.py search pexels-video "<query>" [--n 8]          list candidates (id, size, duration, author)
  python stock.py search pexels-photo "<query>" [--n 8]
  python stock.py search unsplash-photo "<query>" [--n 8]
  python stock.py get pexels-video <id> <video_dir> [--key name]  download + register as assets.yaml[name]
  python stock.py get pexels-photo <id> <video_dir> [--key name]
  python stock.py get unsplash-photo <id> <video_dir> [--key name]

Keys (owner's own, never printed): secrets/pexels_key.txt, secrets/pixabay_key.txt, secrets/unsplash_key.txt.
Licences: Pexels License (free use, no attribution required; we credit anyway, no sale of unaltered copies,
no implied endorsement by people shown). Unsplash License (free use; attribution "Photo by X on Unsplash";
the download endpoint must be called when a photo is used, per the API guidelines).
NASA: media of the NASA library are generally not copyrighted; credit "NASA" (or the centre), no logos, no implied
endorsement; read each item's description for third-party rights. Pixabay Content License: free use, no attribution
required (we credit), no sale of unaltered copies. Clips are b-roll: never presented as a specific event they do not show.
Never download videos from YouTube channels or other creators: only these libraries.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, load_yaml, save_yaml  # noqa: E402

UA = "CosmosInNumbers/1.0 (stock fetch)"


def key(name: str) -> str:
    """Owner's API key from secrets/ (never printed). Accepts <name>_key.txt or <name>-api.json.txt,
    plain text or JSON ({"key": "..."} / {"api_key": "..."})."""
    alias = {"pixabay": ["pixabay", "pexabay"]}.get(name, [name])
    for n in alias:
        for fn in (f"{n}_key.txt", f"{n}-api.json.txt", f"{n}-api.txt", f"{n}.json"):
            p = ROOT / "secrets" / fn
            if p.exists():
                raw = p.read_text("utf-8-sig").strip()
                if raw.startswith("{"):
                    d = json.loads(raw)
                    vals = [v for k, v in d.items() if isinstance(v, str) and "key" in k.lower()] or                            [v for v in d.values() if isinstance(v, str)]
                    raw = vals[0] if vals else ""
                return raw.strip().strip('"')
    sys.exit(f"missing {name}_key.txt in secrets/: the owner creates it")


def get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **headers})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url: str, dest: Path, headers: dict | None = None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = urllib.parse.quote(url, safe=":/?&=%~+#,;@")  # NASA ids can contain spaces
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)


def pexels(path: str) -> dict:
    return get_json("https://api.pexels.com" + path, {"Authorization": key("pexels")})


def nasa(path: str) -> dict:
    return get_json("https://images-api.nasa.gov" + path, {})


def pixabay(params: str) -> dict:
    return get_json(f"https://pixabay.com/api/videos/?key={key('pixabay')}&{params}", {})


def unsplash(path: str) -> dict:
    return get_json("https://api.unsplash.com" + path, {"Authorization": "Client-ID " + key("unsplash"), "Accept-Version": "v1"})


def search(kind: str, query: str, n: int):
    q = urllib.parse.quote(query)
    if kind == "nasa-video":
        for it in nasa(f"/search?q={q}&media_type=video")["collection"]["items"][:n]:
            d = it["data"][0]
            print(f"{d['nasa_id']}	{d.get('date_created', '')[:10]}	{d.get('center', '')}	{d['title'][:70]}")
    elif kind == "pixabay-video":
        for v in pixabay(f"q={q}&per_page={max(3, n)}&safesearch=true")["hits"][:n]:
            m = v["videos"]["large"] if v["videos"]["large"]["url"] else v["videos"]["medium"]
            print(f"{v['id']}	{m['width']}x{m['height']}	{v['duration']}s	{v['user']}	{v['tags']}")
    elif kind == "pexels-video":
        for v in pexels(f"/videos/search?query={q}&per_page={n}&orientation=landscape")["videos"]:
            print(f"{v['id']}\t{v['width']}x{v['height']}\t{v['duration']}s\t{v['user']['name']}\t{v['url']}")
    elif kind == "pexels-photo":
        for p in pexels(f"/v1/search?query={q}&per_page={n}&orientation=landscape")["photos"]:
            print(f"{p['id']}\t{p['width']}x{p['height']}\t{p['photographer']}\t{p.get('alt', '')}\t{p['url']}")
    elif kind == "unsplash-photo":
        for p in unsplash(f"/search/photos?query={q}&per_page={n}&orientation=landscape")["results"]:
            print(f"{p['id']}\t{p['width']}x{p['height']}\t{p['user']['name']}\t{p.get('alt_description') or ''}\t{p['links']['html']}")
    else:
        sys.exit(f"unknown kind {kind}")


def get(kind: str, sid: str, video: Path, name: str | None):
    reg_path = video / "assets.yaml"
    reg = load_yaml(reg_path) or {}
    if kind == "nasa-video":
        d = nasa(f"/search?nasa_id={urllib.parse.quote(sid)}")["collection"]["items"][0]["data"][0]
        files = get_json(f"https://images-assets.nasa.gov/video/{urllib.parse.quote(sid)}/collection.json", {})
        mp4 = [f for f in files if f.endswith(".mp4")]
        # ~mobile can be 320 px on recent items: prefer the 720p-ish renditions
        pick = next((f for t in ("~medium", "~large", "~mobile", "~small") for f in mp4 if t in f), mp4[0])
        rel = f"assets/stock/nasa-{sid}.mp4"
        download(pick.replace("http://", "https://"), video / rel)
        entry = {"file": rel, "type": "video", "kind": "footage", "title": d["title"],
                 "source": f"https://images.nasa.gov/details/{sid}", "credit": "NASA" + (f"/{d['center']}" if d.get("center") else "") + (f" ({d['secondary_creator']})" if d.get("secondary_creator") else ""),
                 "license": "NASA media usage guidelines (generally not copyrighted; no endorsement, no logos)",
                 "check": "ok"}
        if "concept" in (d.get("description", "") + d["title"]).lower() or "animation" in d["title"].lower():
            entry["kind"] = "illustration"
    elif kind == "pixabay-video":
        v = pixabay(f"id={urllib.parse.quote(sid)}")["hits"][0]
        m = v["videos"]["large"] if v["videos"]["large"]["url"] else v["videos"]["medium"]
        rel = f"assets/stock/pixabay-{sid}.mp4"
        download(m["url"], video / rel)
        entry = {"file": rel, "type": "video", "kind": "stock", "title": f"Pixabay video {sid} ({v['tags']})",
                 "source": v["pageURL"], "credit": f"{v['user']} / Pixabay", "duration": v["duration"],
                 "license": "Pixabay Content License (https://pixabay.com/service/license-summary/)", "check": "ok"}
    elif kind == "pexels-video":
        v = pexels(f"/videos/videos/{sid}")
        files = [f for f in v["video_files"] if f.get("file_type") == "video/mp4" and f.get("width")]
        best = min(files, key=lambda f: (abs(f["width"] - 1920), -f["width"]))   # closest to 1080p
        rel = f"assets/stock/pexels-{sid}.mp4"
        download(best["link"], video / rel)
        entry = {"file": rel, "type": "video", "kind": "stock", "title": f"Pexels video {sid}",
                 "source": v["url"], "credit": f"{v['user']['name']} / Pexels", "duration": v["duration"],
                 "license": "Pexels License (https://www.pexels.com/license/)", "check": "ok"}
    elif kind == "pexels-photo":
        p = pexels(f"/v1/photos/{sid}")
        rel = f"assets/stock/pexels-{sid}.jpg"
        download(p["src"]["original"] + "?auto=compress&w=2400", video / rel)
        entry = {"file": rel, "type": "image", "kind": "stock", "title": p.get("alt") or f"Pexels photo {sid}",
                 "source": p["url"], "credit": f"{p['photographer']} / Pexels",
                 "license": "Pexels License (https://www.pexels.com/license/)", "check": "ok"}
    elif kind == "unsplash-photo":
        p = unsplash(f"/photos/{sid}")
        get_json(p["links"]["download_location"], {"Authorization": "Client-ID " + key("unsplash")})  # required ping
        rel = f"assets/stock/unsplash-{sid}.jpg"
        download(p["urls"]["raw"] + "&w=2400&fm=jpg&q=85", video / rel)
        entry = {"file": rel, "type": "image", "kind": "stock", "title": p.get("alt_description") or f"Unsplash photo {sid}",
                 "source": p["links"]["html"], "credit": f"Photo by {p['user']['name']} on Unsplash",
                 "license": "Unsplash License (https://unsplash.com/license)", "check": "ok"}
    else:
        sys.exit(f"unknown kind {kind}")
    k = name or Path(entry["file"]).stem
    reg[k] = entry
    save_yaml(reg_path, reg)
    print(f"{k}: {entry['file']} ({entry['credit']})")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 8
    name = a[a.index("--key") + 1] if "--key" in a else None
    if a[0] == "search":
        search(a[1], a[2], n)
    elif a[0] == "get":
        get(a[1], a[2], Path(a[3]).resolve(), name)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
