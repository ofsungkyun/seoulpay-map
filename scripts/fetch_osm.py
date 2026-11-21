"""서울 25개 자치구별 OSM 주소/도로 데이터를 Overpass에서 받아 data/osm/{구}.json 에 저장.
공용 서버 부담을 줄이기 위해 순차 실행 + 대기 + 이미 받은 파일은 건너뜀."""
import json, os, sys, time, urllib.parse, urllib.request

GUS = ["종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구",
       "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구",
       "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"]
ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
Q = """[out:json][timeout:300];
area["name"="서울특별시"]["admin_level"="4"]->.s;
rel(area.s)["boundary"="administrative"]["admin_level"="6"]["name"="{gu}"];
map_to_area->.a;
(nwr(area.a)["addr:housenumber"]["addr:street"];);
out tags center;
way(area.a)["highway"]["name"];
out tags geom;
"""

os.makedirs("data/osm", exist_ok=True)
targets = sys.argv[1:] or GUS
for gu in targets:
    path = f"data/osm/{gu}.json"
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        print("skip", gu); continue
    body = urllib.parse.urlencode({"data": Q.format(gu=gu)}).encode()
    for attempt in range(6):
        ep = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            req = urllib.request.Request(ep, data=body, headers={"User-Agent": "seoulpay-map/1.0 (personal, non-commercial)"})
            with urllib.request.urlopen(req, timeout=400) as r:
                raw = r.read()
            d = json.loads(raw)
            if not d.get("elements"):
                raise ValueError("empty result")
            with open(path, "wb") as f:
                f.write(raw)
            print(gu, len(d["elements"]), "elements", len(raw) // 1024, "KB", flush=True)
            break
        except Exception as e:
            wait = 15 * (attempt + 1)
            print(gu, "fail", ep, e, "retry in", wait, flush=True)
            time.sleep(wait)
    time.sleep(5)
