"""Download a low-resolution transcode of each candidate (for choosing in/out points). Run from repo root."""
import json, re, sys, time
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import download, transport
contract = json.loads((ROOT / 'workflow/style.json').read_text(encoding='utf-8'))
def opener(url, timeout=300):
    return download._SAFE_OPENER.open(transport.build_request(url, contract, accept='*/*'), timeout=timeout)
EP = ROOT / 'work/ask-chatgpt'
info = json.loads((EP / 'sourcing/info.json').read_text(encoding='utf-8'))
want = sys.argv[1:] or list(info)
for k in want:
    v = info[k]
    ders = {d['transcodekey']: d['src'] for d in v['derivatives']}
    url = ders.get('480p.vp9.webm') if v['size'] > 60e6 else re.sub(r'\?.*$', '', v['url'])
    if v['duration'] and v['duration'] > 400:
        url = ders.get('240p.vp9.webm', url)
    if not url:
        print('no preview for', k); continue
    dest = EP / 'sourcing/preview' / f"{k}.{url.rsplit('.', 1)[1]}"
    if dest.exists():
        print('have', k); continue
    download.download_binary(url, dest, opener=opener, max_bytes=400 * 1024 * 1024)
    print(k, round(dest.stat().st_size / 1e6, 1), 'MB', url.rsplit('/', 1)[1][-20:], flush=True)
    time.sleep(1.5)
