#!/usr/bin/env python3
"""Download 150x150 thumbnails for every item in research/catalog2.json."""
import json, os, time, urllib.request, urllib.parse
D = os.path.dirname(__file__); os.makedirs(os.path.join(D, 'thumbs'), exist_ok=True)
ids = sorted({i['id'] for v in json.load(open(os.path.join(D, 'catalog2.json'))).values() for i in v['items']})
UA = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
for n in range(0, len(ids), 50):
    chunk = ids[n:n + 50]
    for attempt in range(4):
        try:
            url = 'https://thumbnails.roblox.com/v1/assets?' + urllib.parse.urlencode({'assetIds': ','.join(map(str, chunk)), 'size': '150x150', 'format': 'Png'})
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: data = json.load(r)['data']; break
        except Exception as e:
            print('retry', e); time.sleep(10); data = []
    for d in data:
        if d.get('state') == 'Completed' and d.get('imageUrl'):
            try:
                with urllib.request.urlopen(urllib.request.Request(d['imageUrl'], headers=UA), timeout=20) as r:
                    open(os.path.join(D, 'thumbs', f"{d['targetId']}.png"), 'wb').write(r.read())
            except Exception as e: print('img', e)
    print(n, len(data)); time.sleep(1)
