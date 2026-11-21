/* 서울페이 가맹점 지도 */
(function () {
  "use strict";
  const CFG = window.APP_CONFIG;
  const HOME = CFG.home;
  const GROUPS = CFG.groups;
  const MIN_ZOOM_SHOW = 15;      // 이보다 멀리 보면 가게 숨김 (안내 문구)
  const PIN_ZOOM = 17;           // 이 배율부터 아이콘 핀, 그 아래는 점
  const MAX_PINS = 700;
  const LIST_LIMIT = 60;

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---------- 상태 ----------
  const state = {
    index: null,
    catGroup: [],             // 원래 업종번호 -> 그룹번호
    active: new Set(GROUPS.map((_, i) => i)),
    loaded: new Map(),        // 파일 -> Promise
    buildings: [],            // {lat,lng,prec,gu,items:[merchant]}
    merchants: [],            // {n,cat,g,a,b}
    ref: { lat: HOME.lat, lng: HOME.lng, label: "집" },  // 거리 기준점
    query: "",
    selected: null,
    sheetMode: null,          // "list" | "detail" | "search"
  };

  // ---------- 지도 ----------
  const map = L.map("map", {
    zoomControl: false,
    preferCanvas: true,
    minZoom: 11,
    maxZoom: 19,
  }).setView([HOME.lat, HOME.lng], CFG.startZoom);

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    maxNativeZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> 기여자 | 가맹점: 서울시',
  }).addTo(map);
  L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);

  const canvas = L.canvas({ padding: 0.3, tolerance: 8 });
  const shopLayer = L.layerGroup().addTo(map);

  // 집 표시 + 거리 원
  const homeIcon = L.divIcon({
    className: "",
    html: `<div class="home-pin"><div class="bubble">🏠 ${esc(HOME.label)}</div><div class="stem"></div></div>`,
    iconSize: [130, 56],
    iconAnchor: [65, 56],
  });
  L.marker([HOME.lat, HOME.lng], { icon: homeIcon, interactive: false, zIndexOffset: 2000, keyboard: false }).addTo(map);
  CFG.rings.forEach((r) => {
    L.circle([HOME.lat, HOME.lng], { radius: r, color: "#111", weight: 3, opacity: 0.7, dashArray: "10 8", fill: false, interactive: false }).addTo(map);
    const lat = HOME.lat + r / 111000;  // 원의 위쪽 끝에 이름표
    L.marker([lat, HOME.lng], {
      interactive: false, keyboard: false,
      icon: L.divIcon({ className: "", html: `<div class="ring-label">${walkLabel(r)}</div>`, iconSize: [150, 26], iconAnchor: [75, 13] }),
    }).addTo(map);
  });
  let meMarker = null;

  // ---------- 유틸 ----------
  function distM(a, b) {
    const R = 6371000, toR = Math.PI / 180;
    const dLat = (b.lat - a.lat) * toR, dLng = (b.lng - a.lng) * toR;
    const s = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * toR) * Math.cos(b.lat * toR) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  }
  function fmtDist(m) {
    return m < 1000 ? `${Math.round(m / 10) * 10}m` : `${(m / 1000).toFixed(1)}km`;
  }
  function walkLabel(m) {
    const min = Math.max(1, Math.round(m / CFG.walkMetersPerMin));
    return `${fmtDist(m)} · 걸어서 약 ${min}분`;
  }
  function distText(b) {
    const m = distM(state.ref, b);
    const who = state.ref.label === "집" ? "집에서" : "지금 위치에서";
    if (m > 3000) return `${who} ${fmtDist(m)}`;
    return `${who} ${walkLabel(m)}`;
  }
  // 배경색이 밝으면 검은 글씨, 어두우면 흰 글씨 (WCAG 대비)
  function textOn(hex) {
    const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    const L = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    return (1.05) / (L + 0.05) >= (L + 0.05) / 0.05 ? "#fff" : "#111";
  }
  function debounce(fn, ms) {
    let t;
    return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }
  function setTopHeight() {
    const h = $("topbar").offsetHeight;
    document.documentElement.style.setProperty("--top-h", h + "px");
    map.invalidateSize();
  }

  // ---------- 업종 단추 ----------
  function buildChips() {
    const box = $("chips");
    box.innerHTML = "";
    const all = document.createElement("button");
    all.className = "chip all";
    all.innerHTML = `<span class="dot"></span>전체`;
    all.onclick = () => { state.active = new Set(GROUPS.map((_, i) => i)); onFilterChange(); };
    box.appendChild(all);
    GROUPS.forEach((g, i) => {
      const b = document.createElement("button");
      b.className = "chip";
      b.style.setProperty("--c", g.color);
      b.style.setProperty("--t", textOn(g.color));
      b.dataset.idx = i;
      b.innerHTML = `<span>${g.emoji}</span>${esc(g.label)}`;
      b.setAttribute("aria-pressed", "true");
      b.onclick = () => toggleGroup(i);
      box.appendChild(b);
    });
    paintChips();
    // 옆으로 더 있다는 표시 (끝까지 밀면 사라짐)
    const more = $("chips-more");
    const upd = () => { more.hidden = box.scrollLeft + box.clientWidth >= box.scrollWidth - 8; };
    more.onclick = () => box.scrollBy({ left: box.clientWidth * 0.7, behavior: "smooth" });
    box.addEventListener("scroll", debounce(upd, 60));
    window.addEventListener("resize", debounce(upd, 150));
    setTimeout(upd, 50);
  }
  function toggleGroup(i) {
    const allOn = state.active.size === GROUPS.length;
    if (allOn) state.active = new Set([i]);                // 전체 상태에서 누르면 그것만
    else if (state.active.has(i)) {
      state.active.delete(i);
      if (state.active.size === 0) state.active = new Set(GROUPS.map((_, k) => k));
    } else state.active.add(i);
    onFilterChange();
  }
  function paintChips() {
    const allOn = state.active.size === GROUPS.length;
    document.querySelectorAll("#chips .chip").forEach((el) => {
      if (el.classList.contains("all")) { el.classList.toggle("on", allOn); el.setAttribute("aria-pressed", allOn); return; }
      const on = state.active.has(+el.dataset.idx);
      el.classList.toggle("on", on && !allOn);
      el.classList.toggle("off", !on);
      el.setAttribute("aria-pressed", on);
    });
  }
  function onFilterChange() {
    paintChips();
    render();
    if (state.sheetMode === "list") showList();
    else if (state.sheetMode === "search") showSearch();
    else if (state.sheetMode === "detail" && state.selected) showDetail(state.selected);
  }

  // ---------- 데이터 ----------
  async function loadIndex() {
    const r = await fetch("data/index.json");
    state.index = await r.json();
    const name2group = {};
    GROUPS.forEach((g, gi) => g.cats.forEach((c) => (name2group[c] = gi)));
    const etc = GROUPS.findIndex((g) => g.id === "etc");
    state.catGroup = state.index.cats.map((c) => (c in name2group ? name2group[c] : etc));
    $("help-date").textContent = state.index.date.replace(/^(\d+)-0?(\d+)-0?(\d+)$/, "$1년 $2월 $3일");
  }

  function gusInView(pad) {
    const b = map.getBounds().pad(pad);
    return state.index.gus.filter((g) => {
      const [s, w, n, e] = g.bbox;
      return !(n < b.getSouth() || s > b.getNorth() || e < b.getWest() || w > b.getEast());
    });
  }

  let pending = 0;
  function loadGu(g) {
    if (state.loaded.has(g.file)) return state.loaded.get(g.file);
    pending++;
    $("loading").hidden = false;
    const p = fetch("data/" + g.file)
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((d) => {
        const base = state.buildings.length;
        d.p.forEach(([lat, lng, prec]) => state.buildings.push({ lat, lng, prec, gu: d.gu, items: [] }));
        d.m.forEach(([n, cat, pi, a]) => {
          const b = state.buildings[base + pi];
          const m = { n, cat, g: state.catGroup[cat], a, b };
          b.items.push(m);
          state.merchants.push(m);
        });
      })
      .catch((e) => { console.error("load fail", g.file, e); state.loaded.delete(g.file); })
      .finally(() => {
        pending--;
        if (pending === 0) $("loading").hidden = true;
        render();
        // 목록을 보고 있는 중이면 스크롤 위치를 유지한 채 갱신
        if (state.sheetMode === "list") showList(true);
        if (state.sheetMode === "search") showSearch(true);
      });
    state.loaded.set(g.file, p);
    return p;
  }
  function ensureLoaded() {
    if (!state.index || map.getZoom() < MIN_ZOOM_SHOW - 1) return;
    gusInView(0.25).forEach(loadGu);
  }

  // ---------- 그리기 ----------
  function visibleItems(b) {
    return b.items.filter((m) => state.active.has(m.g));
  }
  function mainGroup(items) {
    const cnt = {};
    let best = items[0].g;
    items.forEach((m) => { cnt[m.g] = (cnt[m.g] || 0) + 1; if (cnt[m.g] > cnt[best]) best = m.g; });
    return best;
  }

  function render() {
    shopLayer.clearLayers();
    const z = map.getZoom();
    $("zoom-hint").hidden = z >= MIN_ZOOM_SHOW;
    if (z < MIN_ZOOM_SHOW) return;
    const bounds = map.getBounds().pad(0.15);
    const vis = [];
    for (const b of state.buildings) {
      if (!bounds.contains([b.lat, b.lng])) continue;
      const items = visibleItems(b);
      if (items.length) vis.push([b, items]);
    }
    const usePins = z >= PIN_ZOOM && vis.length <= MAX_PINS;
    const r = z >= 17 ? 10 : z >= 16 ? 8 : 6;
    for (const [b, items] of vis) {
      const g = GROUPS[mainGroup(items)];
      let mk;
      if (usePins) {
        const cnt = items.length > 1 ? `<span class="cnt">${items.length}</span>` : "";
        const sel = state.selected === b ? " sel" : "";
        mk = L.marker([b.lat, b.lng], {
          icon: L.divIcon({ className: "", html: `<div class="shop-pin${sel}" style="--c:${g.color}">${g.emoji}${cnt}</div>`, iconSize: [40, 40], iconAnchor: [20, 20] }),
          title: items.length > 1 ? `${items[0].n} 외 ${items.length - 1}곳` : items[0].n,
          riseOnHover: true,
        });
      } else {
        mk = L.circleMarker([b.lat, b.lng], {
          renderer: canvas, radius: items.length > 1 ? r + 2 : r,
          color: state.selected === b ? "#ffbf00" : "#fff", weight: state.selected === b ? 5 : 2,
          fillColor: g.color, fillOpacity: 0.95,
        });
      }
      mk.on("click", () => showDetail(b));
      shopLayer.addLayer(mk);
    }
  }

  // ---------- 아래 패널 ----------
  function openSheet(title, sub, bodyHtml, mode, tall) {
    state.sheetMode = mode;
    $("sheet-title").textContent = title;
    $("sheet-sub").innerHTML = sub || "";
    $("sheet-body").innerHTML = bodyHtml;
    $("sheet-body").scrollTop = 0;
    $("sheet").classList.toggle("tall", !!tall);
    $("sheet").hidden = false;
    $("btn-list").hidden = true;
  }
  function closeSheet() {
    $("sheet").hidden = true;
    $("btn-list").hidden = false;
    state.sheetMode = null;
    if (state.selected) { state.selected = null; render(); }
  }

  function mapLinks(m) {
    const q = encodeURIComponent(`${m.n} ${m.b.gu}`);
    return `<div class="links">
      <a class="link-btn naver" href="https://map.naver.com/p/search/${q}" target="_blank" rel="noopener">네이버 지도</a>
      <a class="link-btn kakao" href="https://map.kakao.com/?q=${q}" target="_blank" rel="noopener">카카오맵</a>
    </div>`;
  }
  function shopCard(m, withLinks) {
    const g = GROUPS[m.g];
    const cat = state.index.cats[m.cat];
    // 목록(withLinks=false)에서는 간단히, 가게 정보 창에서만 위치 안내 문구
    const approx = withLinks && m.b.prec === 2 ? `<div class="approx">※ 지도 위치는 주소로 짐작한 것이라 조금 다를 수 있어요</div>` : "";
    return `<div class="name">${esc(m.n)}</div>
      <div class="cat" style="--c:${g.color}">${g.emoji} ${esc(cat)}</div>
      <div class="addr">📮 ${esc(m.a)}</div>
      <div class="dist">🚶 ${distText(m.b)}</div>
      ${approx}${withLinks ? mapLinks(m) : ""}`;
  }

  function showDetail(b, focus) {
    state.selected = b;
    render();
    const items = visibleItems(b);
    let list = items.length ? items : b.items;
    if (focus) list = [focus, ...list.filter((m) => m !== focus)];   // 목록에서 누른 가게를 맨 위에
    const title = list.length > 1 ? `이 건물에 ${list.length}곳` : "가게 정보";
    const sub = list.length > 1 ? (focus ? "누르신 가게가 맨 위에 있어요 · 아래로 밀면 같은 건물 가게가 더 있어요" : "아래로 밀어서 모두 보세요") : "";
    const body = list.map((m) => `<div class="shop" style="--c:${GROUPS[m.g].color}">${shopCard(m, true)}</div>`).join("");
    openSheet(title, sub, body, "detail");
    panIntoView(b);
  }

  // 아래 패널에 가려지지 않게, 고른 건물을 지도에서 보이는 부분의 가운데로 옮김
  function panIntoView(b) {
    const mapRect = map.getContainer().getBoundingClientRect();
    const sheetTop = $("sheet").hidden ? mapRect.bottom : $("sheet").getBoundingClientRect().top;
    const visibleH = Math.max(80, sheetTop - mapRect.top);
    const pt = map.latLngToContainerPoint([b.lat, b.lng]);
    const targetY = visibleH / 2;
    const targetX = mapRect.width / 2;
    if (Math.abs(pt.y - targetY) > visibleH * 0.3 || pt.x < 40 || pt.x > mapRect.width - 100) {
      map.panBy([pt.x - targetX, pt.y - targetY], { animate: true });
    }
  }

  function nearbyMerchants(filterFn) {
    const arr = [];
    for (const m of state.merchants) {
      if (!state.active.has(m.g)) continue;
      if (filterFn && !filterFn(m)) continue;
      arr.push([distM(state.ref, m.b), m]);
    }
    arr.sort((a, b) => a[0] - b[0]);
    return arr;
  }

  let listLimit = LIST_LIMIT;
  function renderListBody(arr, emptyMsg) {
    if (!arr.length) return `<div class="empty">${emptyMsg}</div>`;
    const shown = arr.slice(0, listLimit);
    let html = shown.map(([, m], i) => `<button class="shop" style="--c:${GROUPS[m.g].color}" data-i="${i}">${shopCard(m, false)}</button>`).join("");
    if (arr.length > listLimit) html += `<button class="more-btn" id="list-more">더 보기 (${arr.length - listLimit}곳 더 있어요)</button>`;
    return html;
  }
  function bindListClicks(arr, rerender) {
    $("sheet-body").querySelectorAll("button.shop").forEach((el) => {
      el.onclick = () => {
        const m = arr[+el.dataset.i][1];
        map.setView([m.b.lat, m.b.lng], Math.max(map.getZoom(), 18), { animate: false });
        showDetail(m.b, m);
      };
    });
    const more = $("list-more");
    if (more) more.onclick = () => { listLimit += LIST_LIMIT; rerender(true); };
  }

  // 기준점(집/내 위치) 주변 약 2km 안에 걸치는 구는 미리 불러오기
  function loadNearRef() {
    if (!state.index) return;
    const d = 0.02;
    state.index.gus.forEach((g) => {
      const [s, w, n, e] = g.bbox;
      if (!(n < state.ref.lat - d || s > state.ref.lat + d || e < state.ref.lng - d || w > state.ref.lng + d)) loadGu(g);
    });
  }

  function showList(keepLimit) {
    if (!keepLimit) { listLimit = LIST_LIMIT; loadNearRef(); }
    const arr = nearbyMerchants();
    const who = state.ref.label === "집" ? "집" : "지금 위치";
    const allOn = state.active.size === GROUPS.length;
    const which = allOn ? "모든 가게" : [...state.active].map((i) => GROUPS[i].emoji + " " + GROUPS[i].label).join(", ");
    const sub = `${esc(which)} · ${who}에서 가까운 순서`;
    const st = $("sheet-body").scrollTop;
    openSheet("📋 가까운 가게", sub, renderListBody(arr, "아직 가게 정보를 불러오는 중이에요. 잠시만 기다려 주세요."), "list", true);
    if (keepLimit) $("sheet-body").scrollTop = st;
    bindListClicks(arr, showList);
  }

  function norm(s) { return s.replace(/\s+/g, "").toLowerCase(); }
  function showSearch(keepLimit) {
    if (!keepLimit) listLimit = LIST_LIMIT;
    const q = norm(state.query);
    if (!q) { closeSheet(); return; }
    const arr = nearbyMerchants((m) => norm(m.n).includes(q));
    const loadedNames = state.index.gus.filter((g) => state.loaded.has(g.file)).map((g) => g.name);
    const notAll = loadedNames.length < state.index.gus.length;
    let sub = `“${esc(state.query)}” 찾은 결과 ${arr.length}곳 · 가까운 순서`;
    if (notAll) sub += `<br>지금은 <b>${esc(loadedNames.join(", "))}</b>에서만 찾았어요.<br><button class="small-btn" id="search-all">서울 전체에서 찾기</button>`;
    const st = $("sheet-body").scrollTop;
    openSheet("🔍 찾은 가게", sub, renderListBody(arr, "찾는 가게가 없어요. 이름을 짧게 써 보세요. (예: 김밥)"), "search", true);
    if (keepLimit) $("sheet-body").scrollTop = st;
    bindListClicks(arr, showSearch);
    const all = $("search-all");
    if (all) all.onclick = () => { all.disabled = true; all.textContent = "불러오는 중…(조금 걸려요)"; state.index.gus.forEach(loadGu); };
  }

  // ---------- 버튼 ----------
  function goHome() {
    state.ref = { lat: HOME.lat, lng: HOME.lng, label: "집" };
    map.setView([HOME.lat, HOME.lng], CFG.startZoom);
    if (state.sheetMode === "list") showList();
  }
  function locate() {
    if (!navigator.geolocation) { alert("이 기기에서는 위치를 찾을 수 없어요."); return; }
    $("loading").hidden = false;
    $("loading").textContent = "내 위치를 찾는 중…";
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        $("loading").hidden = true;
        $("loading").textContent = "불러오는 중…";
        const ll = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        state.ref = { ...ll, label: "내 위치" };
        if (meMarker) meMarker.remove();
        meMarker = L.marker([ll.lat, ll.lng], { icon: L.divIcon({ className: "", html: '<div class="me-dot"></div>', iconSize: [26, 26], iconAnchor: [13, 13] }), interactive: false }).addTo(map);
        map.setView([ll.lat, ll.lng], 17);
        if (state.sheetMode === "list") showList();
      },
      () => {
        $("loading").hidden = true;
        $("loading").textContent = "불러오는 중…";
        alert("위치를 찾지 못했어요.\n휴대폰 설정에서 '위치' 사용을 허용해 주세요.");
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    );
  }

  function openHelp() {
    $("help").hidden = false;
    $("help").querySelector(".modal-box").scrollTop = 0;
    $("help-close").focus({ preventScroll: true });
  }
  function paintFontBtn() {
    const big = document.documentElement.classList.contains("big");
    $("btn-font").textContent = big ? "글자 작게" : "글자 크게";
  }

  function bindUI() {
    $("btn-home").onclick = goHome;
    $("btn-locate").onclick = locate;
    $("btn-zoom-in").onclick = () => map.zoomIn();
    $("btn-zoom-out").onclick = () => map.zoomOut();
    $("btn-list").onclick = () => showList();
    $("sheet-close").onclick = closeSheet;
    $("btn-help").onclick = () => { openHelp(); };
    $("help-close").onclick = () => { $("help").hidden = true; localStorage.setItem("helpSeen", "1"); };
    $("help").onclick = (e) => { if (e.target === $("help")) $("help-close").click(); };
    $("btn-font").onclick = () => {
      const big = document.documentElement.classList.toggle("big");
      localStorage.setItem("bigFont", big ? "1" : "0");
      paintFontBtn();
      setTopHeight();
    };
    const doSearch = debounce(() => {
      state.query = $("search").value.trim();
      $("btn-search-clear").hidden = !state.query;
      if (state.query) showSearch(); else if (state.sheetMode === "search") closeSheet();
    }, 350);
    $("search").addEventListener("input", doSearch);
    $("search").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.target.blur(); doSearch(); } });
    $("btn-search-clear").onclick = () => { $("search").value = ""; state.query = ""; $("btn-search-clear").hidden = true; closeSheet(); };
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { if (!$("help").hidden) $("help-close").click(); else if (!$("sheet").hidden) closeSheet(); }
    });
    map.on("moveend", debounce(() => { ensureLoaded(); render(); }, 120));
    window.addEventListener("resize", debounce(setTopHeight, 150));
  }

  // ---------- 시작 ----------
  async function start() {
    if (localStorage.getItem("bigFont") === "1") document.documentElement.classList.add("big");
    buildChips();
    bindUI();
    paintFontBtn();
    setTopHeight();
    if (!localStorage.getItem("helpSeen")) openHelp();
    try {
      await loadIndex();
      ensureLoaded();
    } catch (e) {
      console.error(e);
      $("loading").hidden = false;
      $("loading").textContent = "가게 정보를 불러오지 못했어요. 인터넷 연결을 확인하고 새로고침 해 주세요.";
    }
  }
  start();
})();
