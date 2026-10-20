#!/usr/bin/env python3
"""Search the Roblox avatar catalog for free items (one search per product) and save details + thumbnails.
Output: research/catalog.json and research/thumbs/<id>.png. Read-only public endpoints, no API key."""
import json, time, urllib.request, urllib.parse, urllib.error, os, sys
QUERIES = json.load(open(os.path.join(os.path.dirname(__file__), 'queries.json'), encoding='utf-8'))
OUT = os.path.dirname(__file__)
os.makedirs(os.path.join(OUT, 'thumbs'), exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (catalog research for Boulevard Jood)', 'Accept': 'application/json'}
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
def log(*a):
    print(*a); print(*a, file=LOG); LOG.flush()
def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            log('HTTP', e.code, url[:120])
            if e.code == 429: time.sleep(8); continue
            return None
        except Exception as e:
            log('ERR', e, url[:120]); time.sleep(2)
    return None
csrf = ['']
def details(ids):
    body = json.dumps({'items': [{'itemType': 'Asset', 'id': i} for i in ids]}).encode()
    for attempt in range(4):
        req = urllib.request.Request('https://catalog.roblox.com/v1/catalog/items/details', data=body, method='POST',
                                     headers={**UA, 'Content-Type': 'application/json', 'x-csrf-token': csrf[0]})
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r).get('data', [])
        except urllib.error.HTTPError as e:
            if e.code == 403 and e.headers.get('x-csrf-token'): csrf[0] = e.headers['x-csrf-token']; continue
            log('details HTTP', e.code)
            if e.code == 429: time.sleep(8); continue
            return []
    return []
result = {}
for key, spec in QUERIES.items():
    q = urllib.parse.urlencode({'category': spec.get('category', 'Accessories'), 'keyword': spec['q'], 'maxPrice': 0,
                                'salesTypeFilter': 1, 'limit': 30, 'sortType': 0, 'includeNotForSale': 'false'})
    data = get('https://catalog.roblox.com/v1/search/items?' + q)
    ids = [d['id'] for d in (data or {}).get('data', []) if d.get('itemType') == 'Asset'][:30]
    det = details(ids) if ids else []
    keep = [d for d in det if (d.get('price') in (0, None)) and d.get('priceStatus') in (None, 'Free') or d.get('price') == 0]
    result[key] = {'query': spec['q'], 'items': [{k: d.get(k) for k in ('id', 'name', 'assetType', 'price', 'priceStatus', 'creatorName',
                   'creatorType', 'creatorHasVerifiedBadge', 'favoriteCount', 'itemRestrictions', 'offSaleDeadline',
                   'unitsAvailableForConsumption', 'totalQuantity', 'description')} for d in keep]}
    log(key, spec['q'], len(ids), '->', len(keep))
    json.dump(result, open(os.path.join(OUT, 'catalog.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    time.sleep(2.5)
all_ids = sorted({it['id'] for v in result.values() for it in v['items']})
for i in range(0, len(all_ids), 50):
    chunk = all_ids[i:i + 50]
    t = get('https://thumbnails.roblox.com/v1/assets?' + urllib.parse.urlencode({'assetIds': ','.join(map(str, chunk)), 'size': '150x150', 'format': 'Png'}))
    for d in (t or {}).get('data', []):
        if d.get('state') == 'Completed' and d.get('imageUrl'):
            try:
                with urllib.request.urlopen(urllib.request.Request(d['imageUrl'], headers=UA), timeout=30) as r:
                    open(os.path.join(OUT, 'thumbs', f"{d['targetId']}.png"), 'wb').write(r.read())
            except Exception as e: print('thumb', d['targetId'], e, file=sys.stderr)
    time.sleep(1)
json.dump(result, open(os.path.join(OUT, 'catalog.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('done', len(all_ids), 'items')
