"""Commons imageinfo for the stills -> sourcing/info-stills.json and download them to assets/archive/. Run from repo root."""
import json, re, sys, time, urllib.request, urllib.parse
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import transport, download
contract = json.loads((ROOT / 'workflow/style.json').read_text(encoding='utf-8'))
EP = ROOT / 'work/semmelweis-pilot'
def opener(url, timeout=300):
    return download._SAFE_OPENER.open(transport.build_request(url, contract, accept='*/*'), timeout=timeout)
titles = json.loads(sys.argv[1])
out = {}
for key, title in titles.items():
    q = urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": "2", "titles": title, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "License|LicenseShortName|LicenseUrl|Artist|Credit|DateTimeOriginal|ObjectName"})
    d = json.loads(urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers=transport.headers(contract)), timeout=60).read())
    ii = d['query']['pages'][0]['imageinfo'][0]
    out[key] = {"title": title, "url": ii['url'], "page": ii['descriptionurl'], "size": ii['size'], "w": ii['width'], "h": ii['height'],
                "mime": ii['mime'], "meta": {k: v['value'] for k, v in ii['extmetadata'].items()}}
    m = out[key]['meta']
    print(key, ii['width'], ii['height'], m.get('LicenseShortName'), '|', re.sub('<[^>]+>', '', m.get('Artist', ''))[:60], '|', m.get('DateTimeOriginal', '')[:20])
    ii['url'] = re.sub(r'\?.*$', '', ii['url']); out[key]['url'] = ii['url']
    ext = ii['url'].rsplit('.', 1)[1].lower().replace('jpeg', 'jpg')
    dest = EP / 'assets/archive' / f"{key}.{ext}"
    if not dest.exists():
        download.download_binary(ii['url'], dest, opener=opener, max_bytes=60 * 1024 * 1024)
    time.sleep(1.2)
p = EP / 'sourcing/info-stills.json'
old = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
old.update(out)
p.write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding='utf-8')
