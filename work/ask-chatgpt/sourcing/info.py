"""Commons metadata + transcoded derivatives for sourcing/chosen.json -> sourcing/info.json. Run from repo root."""
import json, sys, time, urllib.request, urllib.parse
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import transport
contract = json.loads((ROOT / 'workflow/style.json').read_text(encoding='utf-8'))
EP = ROOT / 'work/ask-chatgpt'
src = sys.argv[1] if len(sys.argv) > 1 else 'chosen.json'
titles = json.loads((EP / 'sourcing' / src).read_text(encoding='utf-8'))
outp = EP / 'sourcing/info.json'
out = json.loads(outp.read_text(encoding='utf-8')) if outp.exists() else {}
for key, title in titles.items():
    q = urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": "2", "titles": title,
        "prop": "videoinfo", "viprop": "url|size|mime|extmetadata|derivatives",
        "viextmetadatafilter": "License|LicenseShortName|LicenseUrl|Artist|Credit|DateTimeOriginal|ObjectName|AttributionRequired|Copyrighted|Restrictions|ImageDescription"})
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers=transport.headers(contract))
    d = json.loads(urllib.request.urlopen(req, timeout=60).read())
    pg = d['query']['pages'][0]
    if 'missing' in pg:
        print('MISSING', key, title); continue
    ii = pg['videoinfo'][0]
    ders = [x for x in ii.get('derivatives', []) if x.get('type', '').startswith('video/webm')]
    out[key] = {"title": title, "url": ii['url'], "page": ii['descriptionurl'], "size": ii['size'], "w": ii.get('width'),
                "h": ii.get('height'), "mime": ii['mime'], "duration": ii.get('duration'),
                "derivatives": [{"src": x['src'], "w": x.get('width'), "h": x.get('height'), "transcodekey": x.get('transcodekey')} for x in ders],
                "meta": {k: v['value'] for k, v in ii.get('extmetadata', {}).items()}}
    m = out[key]['meta']
    print(key, ii['mime'], ii.get('width'), ii.get('height'), round(ii['size'] / 1e6, 1), 'MB', ii.get('duration'),
          m.get('LicenseShortName'), '|', str(m.get('Artist', ''))[:60].replace('\n', ' '), '|', [x.get('transcodekey') for x in ders])
    time.sleep(1.1)
outp.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
