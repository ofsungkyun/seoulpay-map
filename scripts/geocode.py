"""가맹점 주소 -> 좌표 변환 (OSM 기반, API 키 불필요)

정확도 단계 (precision)
  0 : OSM 에 같은 도로명주소(도로명+건물번호)가 있음 -> 그 좌표 사용 (정확)
  1 : 같은 도로의 앞뒤 번호 건물(앵커) 사이를 도로선을 따라 보간 (대체로 정확, 수십 m 오차)
  2 : 앵커 범위 밖 외삽 / 앵커 없음 -> 도로명주소 규칙(기초번호 1 = 약 10 m, 서->동, 남->북)으로 추정

결과: data/geocoded/{구}.json  (key -> [lat, lon, precision])
"""
import csv, json, math, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from normalize import norm_key

GU_RE = re.compile(r'서울(?:특별시)?\s*(\S+구)')
HN_RE = re.compile(r'^\s*(?:지하\s*)?(\d+)(?:-(\d+))?')
M_PER_NUM = 10.0           # 도로명주소 기초번호 간격 20 m, 좌/우 홀짝 -> 번호 1 당 약 10 m
SIDE_OFFSET = 9.0          # 홀수 = 왼쪽, 짝수 = 오른쪽 (진행방향 기준)


def merchant_gu(row):
    gu = row["자치구명"].strip()
    if gu.endswith("구"):
        return gu
    m = GU_RE.search(row["기본주소"])
    return m.group(1) if m else None


# ---------- 좌표계 (국소 평면, 미터) ----------
LAT0 = 37.55
KX = 111320.0 * math.cos(math.radians(LAT0))
KY = 110540.0


def to_xy(lat, lon):
    return (lon * KX, lat * KY)


def to_ll(x, y):
    return (y / KY, x / KX)


# ---------- 도로 polyline ----------
class Road:
    """같은 이름의 OSM way 들을 그래프로 묶고, 가장 긴 경로(지름)를 주경로로 사용."""

    def __init__(self, ways, parent_pts=None):
        adj = defaultdict(dict)
        self.all_pts = []
        for geom in ways:
            pts = [to_xy(p["lat"], p["lon"]) for p in geom]
            keys = [(round(x, 1), round(y, 1)) for x, y in pts]
            self.all_pts.extend(keys)
            for a, b in zip(keys, keys[1:]):
                if a == b:
                    continue
                d = math.dist(a, b)
                adj[a][b] = d
                adj[b][a] = d
        self.adj = adj
        self.path = self._main_path()
        # 방향: "OO로8길" 같은 가지 도로는 상위 도로와 만나는 쪽이 시작점
        if len(self.path) >= 2 and parent_pts:
            def near(p):
                return min(math.dist(p, q) for q in parent_pts)
            if near(self.path[-1]) < near(self.path[0]):
                self.path.reverse()
        # 그 외: 동서 도로는 서->동, 남북 도로는 남->북
        elif len(self.path) >= 2:
            (x0, y0), (x1, y1) = self.path[0], self.path[-1]
            if abs(x1 - x0) >= abs(y1 - y0):
                if x1 < x0:
                    self.path.reverse()
            elif y1 < y0:
                self.path.reverse()
        self.cum = [0.0]
        for a, b in zip(self.path, self.path[1:]):
            self.cum.append(self.cum[-1] + math.dist(a, b))
        self.length = self.cum[-1]

    def _dijkstra(self, src, nodes):
        import heapq
        dist = {src: 0.0}
        prev = {}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e18):
                continue
            for v, w in self.adj[u].items():
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    def _main_path(self):
        if not self.adj:
            return []
        # 가장 큰 연결요소 안에서 지름 경로
        seen, best = set(), None
        for s in self.adj:
            if s in seen:
                continue
            dist, _ = self._dijkstra(s, None)
            comp = set(dist)
            seen |= comp
            far = max(dist, key=dist.get)
            d2, prev = self._dijkstra(far, None)
            end = max(d2, key=d2.get)
            if best is None or d2[end] > best[0]:
                path = [end]
                while path[-1] != far:
                    path.append(prev[path[-1]])
                best = (d2[end], path)
        return best[1]

    def project(self, x, y):
        """점 -> (chainage, 거리)"""
        best = (1e18, 0.0)
        for i, (a, b) in enumerate(zip(self.path, self.path[1:])):
            ax, ay = a
            bx, by = b
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
            px, py = ax + t * dx, ay + t * dy
            d = math.hypot(x - px, y - py)
            if d < best[0]:
                best = (d, self.cum[i] + t * math.sqrt(L2))
        return best[1], best[0]

    def point_at(self, s, side=0.0):
        s = max(0.0, min(self.length, s))
        import bisect
        i = max(0, min(len(self.path) - 2, bisect.bisect_right(self.cum, s) - 1))
        a, b = self.path[i], self.path[i + 1]
        seg = self.cum[i + 1] - self.cum[i]
        t = 0.0 if seg == 0 else (s - self.cum[i]) / seg
        x = a[0] + t * (b[0] - a[0])
        y = a[1] + t * (b[1] - a[1])
        if side and seg > 0:
            # 진행방향 왼쪽 법선 (-dy, dx)
            nx, ny = -(b[1] - a[1]) / seg, (b[0] - a[0]) / seg
            x += nx * side
            y += ny * side
        return x, y


def theil_sen(xs, ys):
    sl = []
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            if xs[j] != xs[i]:
                sl.append((ys[j] - ys[i]) / (xs[j] - xs[i]))
    if not sl:
        return None, None
    sl.sort()
    b = sl[len(sl) // 2]
    ints = sorted(y - b * x for x, y in zip(xs, ys))
    return b, ints[len(ints) // 2]


class RoadModel:
    def __init__(self, road, anchors):
        """anchors: list of (mainnum, x, y)"""
        self.road = road
        pts = []
        for n, x, y in anchors:
            s, d = road.project(x, y)
            if d < 80:
                pts.append((n, s))
        # 같은 번호는 평균
        by = defaultdict(list)
        for n, s in pts:
            by[n].append(s)
        pts = sorted((n, sum(v) / len(v)) for n, v in by.items())
        self.slope, self.icpt = (None, None)
        if len(pts) >= 2:
            b, a = theil_sen([p[0] for p in pts], [p[1] for p in pts])
            if b is not None and 3 <= abs(b) <= 30:
                self.slope, self.icpt = b, a
                pts = [p for p in pts if abs(p[1] - (a + b * p[0])) < 120]   # 이상치 제거
        if self.slope is None and pts:
            # 앵커 1개(또는 경사 이상): 규칙 기반 기울기
            self.slope = M_PER_NUM
            self.icpt = pts[len(pts) // 2][1] - M_PER_NUM * pts[len(pts) // 2][0]
            pts = [pts[len(pts) // 2]]
        self.pts = pts

    def locate(self, n):
        side = SIDE_OFFSET if n % 2 == 1 else -SIDE_OFFSET
        sgn = 1 if (self.slope or 1) > 0 else -1
        side *= sgn
        pts = self.pts
        if len(pts) >= 2 and pts[0][0] <= n <= pts[-1][0]:
            for (n0, s0), (n1, s1) in zip(pts, pts[1:]):
                if n0 <= n <= n1:
                    s = s0 if n1 == n0 else s0 + (s1 - s0) * (n - n0) / (n1 - n0)
                    return self.road.point_at(s, side), 1
        if self.slope is not None:
            s = self.icpt + self.slope * n
            if -60 <= s <= self.road.length + 60:
                return self.road.point_at(s, side), 2
            return None, None
        # 앵커 없음: 시작점(서/남쪽 끝)에서 번호*10 m
        s = M_PER_NUM * (n - 1)
        if s <= self.road.length + 40:
            return self.road.point_at(s, side), 2
        return None, None


PARENT_RE = re.compile(r'^(.+?(?:대로|로|길))\d+(?:번)?(?:가|안)?길$')


def build_model(road, ways, anchors):
    if not ways.get(road):
        return None
    parent_pts = None
    m = PARENT_RE.match(road)
    if m and ways.get(m.group(1)):
        parent_pts = [(round(p["lat"] * KY, 1), round(p["lon"] * KX, 1))[::-1]
                      for geom in ways[m.group(1)] for p in geom]
    return RoadModel(Road(ways[road], parent_pts), anchors.get(road, []))


def clean_street(s):
    return re.sub(r'\s+', '', s or '')


def process_gu(gu, keys):
    path = f"data/osm/{gu}.json"
    if not os.path.exists(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    exact = defaultdict(list)          # (road, "9-16") -> [(x,y)]
    anchors = defaultdict(list)        # road -> [(mainnum, x, y)]
    ways = defaultdict(list)
    for e in d["elements"]:
        t = e.get("tags", {})
        if "highway" in t and "geometry" in e and "name" in t:
            ways[clean_street(t["name"])].append(e["geometry"])
            continue
        st, hn = t.get("addr:street"), t.get("addr:housenumber")
        if not st or not hn:
            continue
        m = HN_RE.match(hn)
        if not m:
            continue
        if "center" in e:
            lat, lon = e["center"]["lat"], e["center"]["lon"]
        elif "lat" in e:
            lat, lon = e["lat"], e["lon"]
        else:
            continue
        x, y = to_xy(lat, lon)
        road = clean_street(st)
        num = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
        exact[(road, num)].append((x, y))
        if not m.group(2):
            anchors[road].append((int(m.group(1)), x, y))

    # 구 범위(주소가 있는 OSM 건물 분포의 0.1~99.9%, 600 m 여유) — 추정 좌표가 구 밖으로 튀는 것 방지
    xs = sorted(p[0] for v in exact.values() for p in v)
    ys = sorted(p[1] for v in exact.values() for p in v)
    q = lambda a, f: a[min(len(a) - 1, int(len(a) * f))]
    box = (q(xs, .001) - 600, q(ys, .001) - 600, q(xs, .999) + 600, q(ys, .999) + 600)
    inside = lambda x, y: box[0] <= x <= box[2] and box[1] <= y <= box[3]

    models = {}
    out = {}
    stats = [0, 0, 0, 0]
    for key in keys:
        _, road, num = key.split("|")
        pts = exact.get((road, num))
        if pts:
            x = sum(p[0] for p in pts) / len(pts)
            y = sum(p[1] for p in pts) / len(pts)
            lat, lon = to_ll(x, y)
            out[key] = [round(lat, 6), round(lon, 6), 0]
            stats[0] += 1
            continue
        main = int(num.split("-")[0])
        # 가지번호(9-16)는 본번(9) 정확 좌표가 있으면 그 근처로
        if "-" in num and (road, str(main)) in exact:
            pts = exact[(road, str(main))]
            x = sum(p[0] for p in pts) / len(pts)
            y = sum(p[1] for p in pts) / len(pts)
            lat, lon = to_ll(x, y)
            out[key] = [round(lat, 6), round(lon, 6), 1]
            stats[1] += 1
            continue
        if road not in models:
            models[road] = build_model(road, ways, anchors)
        mdl = models[road]
        xy, prec = (None, None)
        if mdl is not None and mdl.road.path:
            xy, prec = mdl.locate(main)
        if xy is None and anchors.get(road):
            # 도로선 범위를 벗어난 경우: 번호가 가장 가까운 건물(±40 이내) 위치로 대체
            n0, x0, y0 = min(anchors[road], key=lambda a: abs(a[0] - main))
            if abs(n0 - main) <= 40:
                xy, prec = (x0, y0), 2
        if xy is None:
            stats[3] += 1
            continue
        if not inside(*xy):
            stats[3] += 1
            continue
        lat, lon = to_ll(*xy)
        out[key] = [round(lat, 6), round(lon, 6), prec]
        stats[prec] += 1
    return out, stats


def main():
    targets = set(sys.argv[1:])
    rows = list(csv.DictReader(open("data/merchants_all.csv", encoding="utf-8")))
    keys_by_gu = defaultdict(set)
    for r in rows:
        gu = merchant_gu(r)
        if not gu:
            continue
        k = norm_key(gu, r["기본주소"])
        if k:
            keys_by_gu[gu].add(k)
    os.makedirs("data/geocoded", exist_ok=True)
    for gu in sorted(keys_by_gu):
        if targets and gu not in targets:
            continue
        res = process_gu(gu, keys_by_gu[gu])
        if res is None:
            print(gu, "OSM 데이터 없음")
            continue
        out, st = res
        json.dump(out, open(f"data/geocoded/{gu}.json", "w", encoding="utf-8"), ensure_ascii=False)
        tot = len(keys_by_gu[gu])
        print(f"{gu}: 주소 {tot}  정확 {st[0]}  보간 {st[1]}  추정 {st[2]}  실패 {st[3]}  ({100*(tot-st[3])/tot:.1f}%)", flush=True)


if __name__ == "__main__":
    main()
