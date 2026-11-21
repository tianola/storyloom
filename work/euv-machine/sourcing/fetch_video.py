import json, sys, re, time, urllib.request, urllib.parse
from pathlib import Path
ROOT=Path('.').resolve(); sys.path.insert(0,str(ROOT))
from tools.sourcing import transport, download
contract=json.loads((ROOT/'workflow/style.json').read_text(encoding='utf-8'))
EP=ROOT/'work/euv-machine'
titles=json.loads((EP/'sourcing/chosen-video.json').read_text(encoding='utf-8'))
out={}
for key,title in titles.items():
    q=urllib.parse.urlencode({"action":"query","format":"json","formatversion":"2","titles":title,"prop":"imageinfo",
        "iiprop":"url|size|mime|mediatype|extmetadata|timestamp|dimensions","iiextmetadatafilter":"License|LicenseShortName|LicenseUrl|Artist|Credit|DateTimeOriginal|ObjectName|AttributionRequired|Copyrighted|Restrictions"})
    req=urllib.request.Request("https://commons.wikimedia.org/w/api.php?"+q,headers=transport.headers(contract))
    d=json.loads(urllib.request.urlopen(req,timeout=60).read())
    ii=d['query']['pages'][0]['imageinfo'][0]
    out[key]={"title":title,"url":ii['url'],"page":ii['descriptionurl'],"size":ii['size'],"w":ii['width'],"h":ii['height'],"mime":ii['mime'],"duration":ii.get('duration'),"meta":{k:v['value'] for k,v in ii['extmetadata'].items()}}
    time.sleep(1.1)
    print(key,ii['mime'],ii['width'],ii['height'],round(ii['size']/1e6,1),'MB',ii.get('duration'),out[key]['meta'].get('License',{}) ,out[key]['meta'].get('Restrictions'),out[key]['meta'].get('Copyrighted'))
(EP/'sourcing/info-video.json').write_text(json.dumps(out,indent=1,ensure_ascii=False),encoding='utf-8')
