"""Leave-one-out 검증: OSM에 실제 좌표가 있는 주소를 하나씩 숨기고 추정 -> 오차(m) 분포"""
import json, sys, random, math, os
from collections import defaultdict
sys.path.insert(0, 'scripts')
import geocode as g
gu = sys.argv[1]
d = json.load(open(f'data/osm/{gu}.json', encoding='utf-8'))
anchors = defaultdict(list); ways = defaultdict(list)
for e in d['elements']:
    t = e.get('tags', {})
    if 'highway' in t and 'geometry' in e and 'name' in t:
        ways[g.clean_street(t['name'])].append(e['geometry']); continue
    st, hn = t.get('addr:street'), t.get('addr:housenumber')
    if not st or not hn: continue
    m = g.HN_RE.match(hn)
    if not m or m.group(2): continue
    c = e.get('center') or {'lat': e.get('lat'), 'lon': e.get('lon')}
    if c['lat'] is None: continue
    anchors[g.clean_street(st)].append((int(m.group(1)), *g.to_xy(c['lat'], c['lon'])))
random.seed(1)
errs = {1: [], 2: []}
roads = [r for r in anchors if r in ways]
random.shuffle(roads)
for r in roads[:400]:
    road = g.Road(ways[r])
    if not road.path: continue
    nums = sorted(set(a[0] for a in anchors[r]))
    for n in random.sample(nums, min(3, len(nums))):
        rest = [a for a in anchors[r] if a[0] != n]
        truth = [a for a in anchors[r] if a[0] == n]
        tx = sum(a[1] for a in truth)/len(truth); ty = sum(a[2] for a in truth)/len(truth)
        xy, p = g.build_model(r, ways, {r: rest}).locate(n)
        if xy: errs[p].append(math.dist(xy, (tx, ty)))
for p, e in errs.items():
    e.sort()
    if e: print(f'precision {p}: n={len(e)} median={e[len(e)//2]:.0f}m p80={e[int(len(e)*.8)]:.0f}m p95={e[int(len(e)*.95)]:.0f}m')
