import json, subprocess, sys, re
ROOT='.'
qs=["EUV lithography","ASML","ASML EUV","Extreme ultraviolet lithography","Veldhoven","photolithography cleanroom","silicon wafer","wafer fab","semiconductor fab TSMC","TSMC","Zeiss lens","Zeiss mirror","Trumpf laser","CO2 laser","laser cutting","tin plasma","molten tin","vacuum chamber","multilayer mirror","photomask","chip manufacturing","microchip","integrated circuit die","Intel fab","Samsung semiconductor","Hsinchu Science Park","Kyoto Japan 1985","Intel 4004","cleanroom","stepper lithography","Jena Zeiss","Oberkochen","Taiwan Semiconductor","computer chip close-up","processor die photo","telescope mirror polishing","Hubble mirror","James Webb mirror"]
seen={}
for q in qs:
    r=subprocess.run([sys.executable,"tools/sourcing/providers.py","wikimedia",q,"--limit","25"],capture_output=True,text=True,encoding='utf-8')
    try: rows=json.loads(r.stdout)
    except Exception: print("fail",q,r.stderr[:200]); continue
    for x in rows:
        a=x['asset_id']
        if a in seen: continue
        if not re.search(r'\.(jpe?g|webm|ogv|png|tiff?)$',a,re.I): continue
        lic=x['license_review']['name'].lower()
        if not re.match(r'^(pd|cc0|cc-by|cc-zero|public)',lic): continue
        seen[a]={"asset_id":a,"url":x['url'],"license":lic,"attribution":re.sub('<[^>]+>','',x['license_review'].get('attribution') or '')[:80],"q":q}
json.dump(list(seen.values()),open('work/the-light-machine/sourcing/candidates.json','w',encoding='utf-8'),indent=1,ensure_ascii=False)
print(len(seen))
