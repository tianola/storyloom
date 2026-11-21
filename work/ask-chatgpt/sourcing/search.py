"""Search Wikimedia Commons (File namespace) and print title, mime, size, duration, licence. Run from repo root."""
import json, sys, time, urllib.request, urllib.parse
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import transport
contract = json.loads((ROOT / 'workflow/style.json').read_text(encoding='utf-8'))
def api(**p):
    p.update(format='json', formatversion='2')
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p), headers=transport.headers(contract))
    return json.loads(urllib.request.urlopen(req, timeout=60).read())
for q in sys.argv[1:]:
    d = api(action='query', generator='search', gsrsearch=q, gsrnamespace=6, gsrlimit=25, prop='imageinfo',
            iiprop='size|mime|extmetadata', iiextmetadatafilter='LicenseShortName')
    print('==', q)
    for pg in sorted(d.get('query', {}).get('pages', []), key=lambda x: x.get('index', 0)):
        ii = pg['imageinfo'][0]
        lic = ii.get('extmetadata', {}).get('LicenseShortName', {}).get('value', '?')
        print(f"  {pg['title'][:95]:95} {ii['mime'][:10]:10} {ii.get('width')}x{ii.get('height')} {ii.get('duration') and round(ii['duration'],1)}s {lic}")
    time.sleep(1)
