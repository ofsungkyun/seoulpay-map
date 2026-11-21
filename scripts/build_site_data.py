"""data/merchants_all.csv + data/geocoded/*.json -> site/data/{구}.json, site/data/index.json

{구}.json 형식 (용량 절약용 배열):
  p: [[lat, lon, precision], ...]           위치(건물) 목록
  m: [[가맹점명, 업종번호, 위치번호, 주소], ...]
"""
import csv, json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from normalize import norm_key
from geocode import merchant_gu

SRC_DATE = "2026-08-10"
CATS = ["음식점/식음료업", "식자재/유통", "보건/복지", "생활/리빙", "의류/잡화",
        "기술/기능 교육", "입시/교습학원", "예술 교육", "외국어/언어", "기타교육기관",
        "문화/체육", "여행/숙박", "가전/통신", "건축/철물", "가구/인테리어", "디자인/인쇄",
        "자동차/주유", "기타", "부동산/임대", "기업/기관"]
CAT_IDX = {c: i for i, c in enumerate(CATS)}
SLUG = {"종로구": "jongno", "중구": "jung", "용산구": "yongsan", "성동구": "seongdong", "광진구": "gwangjin",
        "동대문구": "dongdaemun", "중랑구": "jungnang", "성북구": "seongbuk", "강북구": "gangbuk",
        "도봉구": "dobong", "노원구": "nowon", "은평구": "eunpyeong", "서대문구": "seodaemun", "마포구": "mapo",
        "양천구": "yangcheon", "강서구": "gangseo", "구로구": "guro", "금천구": "geumcheon",
        "영등포구": "yeongdeungpo", "동작구": "dongjak", "관악구": "gwanak", "서초구": "seocho",
        "강남구": "gangnam", "송파구": "songpa", "강동구": "gangdong"}


def short_addr(a):
    a = re.sub(r'\s+', ' ', a).strip()
    return re.sub(r'^(서울특별시|서울)\s*', '', a)


def main():
    rows = list(csv.DictReader(open("data/merchants_all.csv", encoding="utf-8")))
    geo = {}
    for f in os.listdir("data/geocoded"):
        geo.update(json.load(open(f"data/geocoded/{f}", encoding="utf-8")))

    per_gu = defaultdict(lambda: {"pos": {}, "p": [], "m": []})
    stats = defaultdict(lambda: [0, 0])
    seen = set()
    for r in rows:
        gu = merchant_gu(r)
        if not gu:
            continue
        name = r["가맹점명"].strip()
        dedup = (name, r["기본주소"].strip())
        if dedup in seen:          # 완전히 같은 행 중복 제거
            continue
        seen.add(dedup)
        stats[gu][1] += 1
        k = norm_key(gu, r["기본주소"])
        g = geo.get(k) if k else None
        if not g:
            continue
        stats[gu][0] += 1
        d = per_gu[gu]
        pk = (g[0], g[1])
        if pk not in d["pos"]:
            d["pos"][pk] = len(d["p"])
            d["p"].append([round(g[0], 5), round(g[1], 5), g[2]])
        cat = CAT_IDX.get(r["서울페이업종명"].strip(), CAT_IDX["기타"])
        d["m"].append([name, cat, d["pos"][pk], short_addr(r["기본주소"])])

    os.makedirs("site/data", exist_ok=True)
    index = {"date": SRC_DATE, "cats": CATS, "gus": []}
    for f in os.listdir("site/data"):
        if f.endswith(".json"):
            os.remove(f"site/data/{f}")
    for gu, d in sorted(per_gu.items()):
        if gu not in SLUG:
            print("알 수 없는 구 건너뜀:", gu)
            continue
        fn = f"{SLUG[gu]}.json"
        lats = [p[0] for p in d["p"]]
        lons = [p[1] for p in d["p"]]
        # 이상치 영향 줄이려고 1~99% 범위로 bbox
        ls, os_ = sorted(lats), sorted(lons)
        q = lambda a, f: a[min(len(a) - 1, int(len(a) * f))]
        bbox = [q(ls, .005), q(os_, .005), q(ls, .995), q(os_, .995)]
        with open(f"site/data/{fn}", "w", encoding="utf-8") as f:
            json.dump({"gu": gu, "p": d["p"], "m": d["m"]}, f, ensure_ascii=False, separators=(",", ":"))
        index["gus"].append({"name": gu, "file": fn, "bbox": [round(v, 4) for v in bbox],
                             "count": stats[gu][0], "total": stats[gu][1]})
        print(f"{gu}: 지도표시 {stats[gu][0]}/{stats[gu][1]}  위치 {len(d['p'])}  "
              f"{os.path.getsize(f'site/data/{fn}')//1024}KB")
    json.dump(index, open("site/data/index.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    tot = sum(v[0] for v in stats.values()), sum(v[1] for v in stats.values())
    print(f"전체: {tot[0]}/{tot[1]} ({100*tot[0]/tot[1]:.1f}%)")


if __name__ == "__main__":
    main()
