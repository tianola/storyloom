"""Export the episode purchase list and enforce the preview upload gate."""

import argparse
from collections import defaultdict
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.sourcing.manifest import purchase_list


def _cell(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_purchase_list(assets):
    lines = ["# License Purchase List", ""]
    if not assets:
        lines.extend(["No preview assets require purchase.", ""])
        return "\n".join(lines)

    grouped = defaultdict(list)
    for asset in assets:
        grouped[asset["provider"]].append(asset)
    for provider in sorted(grouped, key=str.casefold):
        lines.extend([
            f"## {_cell(provider)}", "",
            "| Internal ID | Asset ID | Purchase/source URL | Local path | Shot IDs | Notes |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for asset in sorted(grouped[provider], key=lambda item: item["id"].casefold()):
            lines.append(
                f"| {_cell(asset['id'])} | {_cell(asset['asset_id'])} | {_cell(asset['url'])} "
                f"| {_cell(asset['file'])} | {_cell(', '.join(asset['shots']))} | {_cell(asset['notes'])} |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the licence purchase list and apply the upload gate.")
    parser.add_argument("--episode", type=Path, required=True)
    args = parser.parse_args(argv)
    previews = purchase_list(args.episode / "assets/license-manifest.json")
    output = args.episode / "dist/license-purchase-list.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_purchase_list(previews), encoding="utf-8")
    if previews:
        print(f"UPLOAD BLOCKED: {len(previews)} preview assets")
        return 1
    print("LICENSE GATE CLEAR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
