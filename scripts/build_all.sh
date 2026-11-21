#!/usr/bin/env bash
# 새 가맹점 엑셀 파일로 지도 데이터 전체를 다시 만드는 스크립트
#   사용법: 프로젝트 폴더에 새 xlsx 하나만 두고  bash scripts/build_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
mkdir -p data
python scripts/extract.py          # xlsx -> data/merchants_all.csv
python scripts/fetch_osm.py        # OSM 주소/도로 (data/osm, 이미 있으면 건너뜀)
python scripts/geocode.py          # 주소 -> 좌표 (data/geocoded)
python scripts/build_site_data.py  # site/data/*.json
echo "완료. site/data/index.json 의 date 값을 새 기준일로 바꿨는지 확인하세요 (build_site_data.py 의 SRC_DATE)."
