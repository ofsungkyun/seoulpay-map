"""주소 정규화: '서울특별시 서초구 신반포로 270 (반포동) 1층' -> '서초구|신반포로|270'"""
import re

ROAD_RE = re.compile(
    r'([가-힣A-Za-z0-9·.]+?(?:대로|로|길)(?:\s?\d+(?:번)?(?:가|안)?길)?)\s*(\d+(?:-\d+)?)(?=\D|$)'
)


def norm_key(gu, addr):
    a = re.sub(r'\s+', ' ', addr.replace('서울특별시', '서울')).strip()
    a2 = re.sub(r'^서울\s*\S+구\s*', '', a)       # "서울 XX구 " 접두어 제거
    a2 = re.sub(r'지하\s*(?=\d)', '', a2)          # "신반포로 지하 200" -> "신반포로 200"
    m = ROAD_RE.search(a2)
    if not m:
        return None
    road = m.group(1).replace(' ', '')
    num = m.group(2)
    return f"{gu}|{road}|{num}"
