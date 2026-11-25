import json, sys, urllib.request, urllib.parse
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import transport
contract = json.loads((ROOT / 'workflow/style.json').read_text(encoding='utf-8'))
def api(**p):
    p.update(action='query', format='json', formatversion='2')
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode(p), headers=transport.headers(contract))
    return json.loads(urllib.request.urlopen(req, timeout=60).read())
mode, arg = sys.argv[1], sys.argv[2]
if mode == 'cat':
    d = api(list='categorymembers', cmtitle=arg, cmlimit='60')
    for m in d['query']['categorymembers']: print(m['title'])
else:
    d = api(list='search', srsearch=arg, srnamespace='6', srlimit='15')
    for m in d['query']['search']: print(m['title'])
