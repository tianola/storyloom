"""Fetch what tools/blender/human3d_mpfb.py needs, outside git: the MPFB2 extension and the MakeHuman assets.

    python tools/human3d_assets.py --dest assets/makehuman [--install-mpfb --blender <path to blender(.exe)>]

--dest gets the MakeHuman system assets (CC0) and, from the community asset packs, only the garments, hair
and beards the wardrobe of human3d_mpfb.ROLES names (CC0 and CC-BY; the CC-BY ones are credited in
docs/human3d-credits.md, which the film's credits must carry). Packs are downloaded once into
<dest>/_downloads and kept, so a second run only extracts.

--install-mpfb downloads MPFB2 from extensions.blender.org and installs it into that Blender's user
extensions ("blender --command extension install-file"), where human3d_mpfb.py expects it
(bl_ext.user_default.mpfb).

Plain Python 3, standard library only; works on Windows and Linux.
"""
import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

MPFB_URL = ("https://extensions.blender.org/download/"
            "sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip"
            "?repository=%2Fapi%2Fv1%2Fextensions%2F&blender_version_min=4.2.0")
PACKS = "https://files.makehumancommunity.org/asset_packs"
MIRROR = "https://files2.makehumancommunity.org/asset_packs"
SYSTEM = "makehuman_system_assets/makehuman_system_assets_cc0.zip"

# asset folder -> (pack zip, author, licence)
WARDROBE = {
    "elvs_ladies_apron": ("dress02/dress02_cc-by.zip", "Elvaerwyn", "CC-BY 4.0"),
    "punkduck_medieval_dress": ("dress03/dress03_cc-by.zip", "punkduck", "CC-BY 4.0"),
    "punkduck_winter_coat": ("dress03/dress03_cc-by.zip", "punkduck", "CC-BY 4.0"),
    "elvs_dirty_lil_maid_bonnet": ("hats03/hats03_cc-by.zip", "Elvaerwyn", "CC-BY 4.0"),
    "rehmanpolanski_hair_bun_brown": ("hair01/hair01_cc0.zip", "RehmanPolanski", "CC0"),
    "elvs_reverse_french_braid_bun": ("hair01/hair01_cc0.zip", "Elvaerwyn", "CC0"),
    "toigo_long_full_skirt": ("skirts01/skirts01_cc0.zip", "MargaretToigo", "CC0"),
    "elvs_male_shirt_tie_tucked1": ("shirts02/shirts02_ccby.zip", "Elvaerwyn", "CC-BY 4.0"),
    "elvs_ruffle_sleeve_peasant_blouse_1": ("shirts03/shirts03_ccby.zip", "Elvaerwyn", "CC-BY 4.0"),
    "toigo_suit_with_jacket_and_bowtie": ("suits01/suits01_cc0.zip", "MargaretToigo", "CC0"),
    "toigo_male_suit_tie_and_jacket": ("suits01/suits01_cc0.zip", "MargaretToigo", "CC0"),
    "toigo_ankle_boots_female": ("shoes01/shoes01_cc0.zip", "MargaretToigo", "CC0"),
    "toigo_ankle_boots_male": ("shoes01/shoes01_cc0.zip", "MargaretToigo", "CC0"),
    "wdg_scruffy_beard": ("bodyparts05/bodyparts05_cc0.zip", "WDG", "CC0"),
    "grinsegold_beard_sigmund_wip": ("bodyparts05/bodyparts05_cc0.zip", "grinsegold", "CC0"),
    "grinsegold_full_beard": ("bodyparts06/bodyparts06_cc-by.zip", "grinsegold", "CC-BY 4.0"),
    "toigo_wool_pants": ("pants01/pants01_cc0.zip", "MargaretToigo", "CC0"),
}


def download(url, path, mirror=None):
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    for u in [url] + ([mirror] if mirror else []):
        try:
            print(f"download {u}", flush=True)
            req = urllib.request.Request(u, headers={"User-Agent": "storyloom-assets"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(path)
            return path
        except OSError as exc:
            print(f"  failed: {exc}", flush=True)
    raise SystemExit(f"could not download {url}")


def extract(zip_path, dest, only=None):
    """Extract the zip into dest (MakeHuman layout); with `only`, just the folders of those asset names."""
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            parts = Path(info.filename).parts
            if only is not None and not any(p in only for p in parts):
                continue
            target = dest.joinpath(*parts)
            if dest.resolve() not in target.resolve().parents and target.resolve() != dest.resolve():
                continue  # no paths outside dest
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--install-mpfb", action="store_true")
    ap.add_argument("--blender", type=Path)
    args = ap.parse_args()
    dest = args.dest.resolve()
    cache = dest / "_downloads"

    sysz = download(f"{PACKS}/{SYSTEM}", cache / Path(SYSTEM).name, f"{MIRROR}/{SYSTEM}")
    if not (dest / "skins").exists():
        extract(sysz, dest)
    by_pack = {}
    for name, (pack, _, _) in WARDROBE.items():
        by_pack.setdefault(pack, set()).add(name)
    for pack, names in sorted(by_pack.items()):
        if all(any((dest / k / n).exists() for k in ("clothes", "hair")) for n in names):
            continue
        z = download(f"{PACKS}/{pack}", cache / Path(pack).name, f"{MIRROR}/{pack}")
        extract(z, dest, only=names)
    missing = [n for n in WARDROBE if not any((dest / k / n).exists() for k in ("clothes", "hair"))]
    if missing:
        raise SystemExit(f"not found in the packs: {', '.join(missing)}")
    print(f"assets ready in {dest}")

    if args.install_mpfb:
        if not args.blender:
            raise SystemExit("--install-mpfb needs --blender <path to blender>")
        z = download(MPFB_URL, cache / "add-on-mpfb-v2.0.18.zip")
        cmd = [str(args.blender), "--command", "extension", "install-file", "-r", "user_default", "-e", str(z)]
        print(" ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)
        print("MPFB2 installed")


if __name__ == "__main__":
    sys.exit(main())
