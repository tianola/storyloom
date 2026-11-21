import json, re, sys, time
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import download, transport
contract = json.loads((ROOT / 'workflow/style.json').read_text(encoding='utf-8'))
def opener(url, timeout=120):
    return download._SAFE_OPENER.open(transport.build_request(url, contract, accept='*/*'), timeout=timeout)
EP = ROOT / 'work/euv-machine'
info = json.loads((EP / 'sourcing/info-video.json').read_text(encoding='utf-8'))
for k, v in info.items():
    url = re.sub(r'\?.*$', '', v['url'])
    ext = url.rsplit('.', 1)[1].lower()
    dest = EP / 'assets/video' / f"{k}.{ext}"
    if dest.exists():
        print('have', k); continue
    sha = download.download_binary(url, dest, opener=opener, max_bytes=200 * 1024 * 1024)
    print(k, sha[:12], dest.stat().st_size, flush=True); time.sleep(1.5)
