import json, sys, time, urllib.request
from pathlib import Path
ROOT=Path('.').resolve(); sys.path.insert(0,str(ROOT))
from tools.sourcing import download, transport
import json as _j
contract=_j.loads((ROOT/'workflow/style.json').read_text(encoding='utf-8'))
def opener(url,timeout=60):
    return download._SAFE_OPENER.open(transport.build_request(url,contract,accept='*/*'),timeout=timeout)
EP=ROOT/'work/euv-machine'
info=json.loads((EP/'sourcing/info.json').read_text(encoding='utf-8'))
for k,v in info.items():
    ext=v['url'].rsplit('.',1)[1].lower()
    dest=EP/'assets/archive'/f"{k}.{ext}"
    if dest.exists(): print('have',k); continue
    sha=download.download_binary(v['url'],dest,opener=opener,max_bytes=60*1024*1024)
    print(k,sha[:12],dest.stat().st_size); time.sleep(1.5)
