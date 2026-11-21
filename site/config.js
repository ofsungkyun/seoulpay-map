// ===== 설정 (필요하면 여기만 고치면 됩니다) =====
window.APP_CONFIG = {
  // 처음 지도 가운데 = 집 (신반포2차 아파트 단지 가운데. 정확한 동 위치는 공개하지 않음)
  home: { lat: 37.51059, lng: 127.00266, label: "우리 집" },
  startZoom: 17,
  // 집 주변에 그려 줄 거리 원 (미터)
  rings: [500, 1000],
  // 걷는 속도 (분당 미터) — 어르신 기준으로 넉넉하게
  walkMetersPerMin: 60,

  // 업종(서울페이업종명) -> 색깔 묶음
  groups: [
    { id: "food",    label: "음식점·카페",  emoji: "🍚", color: "#c92a2a", cats: ["음식점/식음료업"] },
    { id: "grocery", label: "마트·식료품",  emoji: "🛒", color: "#2f7d32", cats: ["식자재/유통"] },
    { id: "health",  label: "병원·약국",    emoji: "💊", color: "#1971c2", cats: ["보건/복지"] },
    { id: "living",  label: "미용·생활",    emoji: "✂️", color: "#9c36b5", cats: ["생활/리빙"] },
    { id: "clothes", label: "옷·잡화",      emoji: "👕", color: "#d6336c", cats: ["의류/잡화"] },
    { id: "culture", label: "운동·문화·여행", emoji: "🏃", color: "#0b7285", cats: ["문화/체육", "여행/숙박"] },
    { id: "home",    label: "가전·가구·수리", emoji: "🔧", color: "#f08c00", cats: ["가전/통신", "건축/철물", "가구/인테리어", "디자인/인쇄"] },
    { id: "edu",     label: "학원·교육",    emoji: "📚", color: "#8d5524", cats: ["기술/기능 교육", "입시/교습학원", "예술 교육", "외국어/언어", "기타교육기관"] },
    { id: "car",     label: "자동차·주유",  emoji: "🚗", color: "#343a40", cats: ["자동차/주유"] },
    { id: "etc",     label: "기타",         emoji: "📦", color: "#868e96", cats: ["기타", "부동산/임대", "기업/기관"] },
  ],
};
