import json, sys, time, urllib.request, urllib.parse
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import transport
contract = json.loads((ROOT / 'workflow/style.json').read_text(encoding='utf-8'))
for t in sys.argv[1:]:
    q = urllib.parse.urlencode({"action":"query","format":"json","formatversion":"2","titles":t,"prop":"imageinfo","iiprop":"url|size|mime|extmetadata",
      "iiextmetadatafilter":"LicenseShortName|Artist|Credit|DateTimeOriginal|DateTime|ObjectName|Copyrighted|ImageDescription|Restrictions"})
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?"+q, headers=transport.headers(contract))
    pg = json.loads(urllib.request.urlopen(req, timeout=60).read())['query']['pages'][0]
    if 'missing' in pg: print('MISSING', t); continue
    ii = pg['imageinfo'][0]; m = {k:v['value'] for k,v in ii['extmetadata'].items()}
    print('==', t, ii['width'], ii['height'], ii['size'], ii['mime'], ii['descriptionurl'])
    for k in ('LicenseShortName','Artist','DateTimeOriginal','Credit','Restrictions'):
        print('  ', k, str(m.get(k))[:200].replace('\n',' '))
    print('   desc', str(m.get('ImageDescription'))[:250].replace('\n',' '))
    time.sleep(1.1)
