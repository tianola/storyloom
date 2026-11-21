"""Download the CC0 assets listed in workflow/assets.json from Poly Haven into assets/polyhaven/.

    python tools/fetch_assets.py            # fetch what is missing
    python tools/fetch_assets.py --dry-run  # list what would be fetched, with sizes

Files land in assets/polyhaven/<textures|hdris|models>/<id>/ (git-ignored: this script and the
list are the record, so a fresh checkout fetches them again). Every file is written to
assets/polyhaven/manifest.json with its source URL, size and licence. Only the public API
(api.polyhaven.com) and its download host (dl.polyhaven.org) are used.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "workflow" / "assets.json"
OUT = ROOT / "assets" / "polyhaven"
API = "https://api.polyhaven.com/files/{}"
HOSTS = {"dl.polyhaven.org"}
AGENT = {"User-Agent": "asset-fetch-client"}
LICENCE = "CC0-1.0 (https://polyhaven.com/license)"
TEXTURE_MAPS = ("Diffuse", "nor_gl", "Rough")


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=120) as r:
        return r.read()


def plan(kind: str, asset: str, resolution: str, files: dict) -> list[tuple[str, int, str]]:
    """[(url, size, relative path)] for one asset at `resolution`."""
    out = []
    if kind == "textures":
        for m in TEXTURE_MAPS:
            if m in files:
                f = files[m][resolution]["jpg"]
                out.append((f["url"], f["size"], Path(urlparse(f["url"]).path).name))
    elif kind == "hdris":
        f = files["hdri"][resolution]["hdr"]
        out.append((f["url"], f["size"], Path(urlparse(f["url"]).path).name))
    else:
        g = files["gltf"][resolution]["gltf"]
        out.append((g["url"], g["size"], Path(urlparse(g["url"]).path).name))
        for rel, f in g.get("include", {}).items():
            out.append((f["url"], f["size"], rel))
    for url, _, rel in out:
        if urlparse(url).hostname not in HOSTS or ".." in Path(rel).parts or Path(rel).is_absolute():
            raise ValueError(f"{asset}: refusing {url} -> {rel}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    spec = json.loads(LIST.read_text(encoding="utf-8"))
    res = spec.get("resolution", "1k")
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    total = 0
    for kind in ("textures", "hdris", "models"):
        for asset, use in spec.get(kind, {}).items():
            files = json.loads(_get(API.format(asset)))
            items = plan(kind, asset, res, files)
            size = sum(s for _, s, _ in items)
            total += size
            folder = OUT / kind / asset
            todo = [(u, s, r) for u, s, r in items
                    if not ((folder / r).is_file() and (folder / r).stat().st_size == s)]
            print(f"{kind:8} {asset:28} {size / 1e6:5.1f} MB  {'ok' if not todo else f'{len(todo)} to fetch'}")
            if args.dry_run:
                continue
            for url, s, rel in todo:
                dest = folder / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                data = _get(url)
                if len(data) != s:
                    raise RuntimeError(f"{asset}: {url} gave {len(data)} bytes, expected {s}")
                dest.write_bytes(data)
                time.sleep(0.2)
            manifest[asset] = {"kind": kind, "use": use, "licence": LICENCE, "resolution": res,
                               "page": f"https://polyhaven.com/a/{asset}",
                               "files": [{"path": f"{kind}/{asset}/{r}", "url": u, "bytes": s} for u, s, r in items]}
    if not args.dry_run:
        OUT.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"total {total / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
