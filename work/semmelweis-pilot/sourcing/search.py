import sys, json
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import providers
for q in sys.argv[1:]:
    print('##', q)
    try:
        for c in providers.search('wikimedia', q, limit=8):
            print({k: (str(v)[:110]) for k, v in c.items() if k in ('title','url','page','width','height','license','year')} or c)
    except Exception as e:
        print('ERR', e)
