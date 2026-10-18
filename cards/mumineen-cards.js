// Mumineen dashboard cards: today, coming up, this week, Maghrib banner.
// Reads the Mumineen integration's entities (sensor.mumineen_*).
const VERSION = "1.1.0";
const P = "sensor.mumineen_";
const TIMES = [
  ["sihori", "Sihori"], ["fajr", "Fajr"], ["sunrise", "Sunrise"], ["zawaal", "Zawaal"],
  ["zohr_end", "Zohr ends"], ["asr_end", "Asr ends"], ["maghrib", "Maghrib"],
  ["maghrib_end", "Maghrib ends"], ["nisful_layl", "Nisful layl"], ["nisful_layl_end", "Nisful layl ends"],
];
const MONTHS = ["Muharram al-Haraam", "Safar al-Muzaffar", "Rabi al-Awwal", "Rabi al-Aakhar", "Jumada al-Ula",
  "Jumada al-Ukhra", "Rajab al-Asab", "Shaban al-Karim", "Ramadan al-Moazzam", "Shawwal al-Mukarram",
  "Zilqad al-Haraam", "Zilhaj al-Haraam"];
const MONTHS_SHORT = ["Muh", "Safar", "Rabi I", "Rabi II", "Jum I", "Jum II", "Rajab", "Shaban", "Ram", "Shaw", "Zilqad", "Zilhaj"];
const MONTHS_AR = ["محرم الحرام", "صفر المظفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الأخرى",
  "رجب الأصب", "شعبان الكريم", "رمضان المعظم", "شوال المكرم", "ذو القعدة الحرام", "ذو الحجة الحرام"];

// Misri tabular calendar, same as the integration (checked against mumineen.org).
const LEAP = new Set([2, 5, 8, 10, 13, 16, 19, 21, 24, 27, 29]);
const yearLen = (y) => (LEAP.has(y % 30) ? 355 : 354);
const monthLen = (y, m) => (m % 2 === 1 || (m === 12 && LEAP.has(y % 30)) ? 30 : 29);
const EPOCH_UTC = Date.UTC(622, 6, 18);
function hijriOf(ymd) {
  // ymd: "YYYY-MM-DD" (a calendar day, no time zone)
  const [Y, M, D] = ymd.split("-").map(Number);
  let rem = Math.round((Date.UTC(Y, M - 1, D) - EPOCH_UTC) / 864e5);
  let y = Math.floor(rem / 10631) * 30 + 1;
  rem = ((rem % 10631) + 10631) % 10631;
  while (rem >= yearLen(y)) { rem -= yearLen(y); y++; }
  let m = 1;
  while (rem >= monthLen(y, m)) { rem -= monthLen(y, m); m++; }
  return { y, m, d: rem + 1 };
}
const arabicDigits = (n) => String(n).replace(/\d/g, (c) => "٠١٢٣٤٥٦٧٨٩"[c]);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const STYLE = `
  :host { --mm-gold: #c49a3a; --mm-gold-soft: rgba(196,154,58,.14); --mm-green: #2f7d62;
    --mm-text: var(--primary-text-color); --mm-muted: var(--secondary-text-color); --mm-line: var(--divider-color, rgba(127,127,127,.2)); }
  ha-card { padding: 18px 20px; overflow: hidden; }
  .eyebrow { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--mm-gold); }
  .muted { color: var(--mm-muted); }
  .num { font-variant-numeric: tabular-nums; }
  h2 { margin: 2px 0 0; font-size: 22px; font-weight: 500; line-height: 1.25; color: var(--mm-text); }
  .row { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
  .ar { font-size: 15px; direction: rtl; color: var(--mm-muted); margin-top: 2px; }
`;

class MumineenBase extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); }
  setConfig(config) { this._config = config || {}; }
  set hass(hass) {
    this._hass = hass;
    const sig = this._watch().map((id) => hass.states[id]?.last_updated || "").join("|");
    if (sig !== this._sig) { this._sig = sig; this._draw(); }
  }
  connectedCallback() { this._timer = setInterval(() => this._draw(), this._tickMs()); this._draw(); }
  disconnectedCallback() { clearInterval(this._timer); }
  _tickMs() { return 30000; }
  _watch() { return []; }
  _draw() { if (this._hass) this.shadowRoot.innerHTML = `<style>${STYLE}${this._css()}</style>${this._html()}`; }
  st(id) { return this._hass.states[id]; }
  time(id) { const s = this.st(id); const d = s && new Date(s.state); return d && !isNaN(d) ? d : null; }
  fmt(d, opts) { return new Intl.DateTimeFormat("en-GB", { timeZone: this._hass.config.time_zone, ...opts }).format(d); }
  hm(d) { return d ? this.fmt(d, { hour: "2-digit", minute: "2-digit" }) : "–"; }
  localYmd(d) { return this.fmt(d, { year: "numeric", month: "2-digit", day: "2-digit" }).split("/").reverse().join("-"); }
  until(d) {
    const mins = Math.max(0, Math.round((d - Date.now()) / 60000));
    if (mins < 1) return "now";
    if (mins < 60) return `in ${mins} min`;
    return `in ${Math.floor(mins / 60)} h ${String(mins % 60).padStart(2, "0")} min`;
  }
  moreInfo(entityId) {
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }
  getCardSize() { return 6; }
  getGridOptions() { return { columns: 12, rows: "auto" }; }
}

// ---------- Today: Hijri date, what's next, and the coming namaaz times ----------
class MumineenTodayCard extends MumineenBase {
  _watch() { return [...TIMES.map(([k]) => P + k), P + "hijri_date"]; }
  _css() {
    return `
      .head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
      .greg { text-align: right; font-size: 13px; }
      .next { margin: 18px 0 6px; padding: 14px 16px; border-radius: 16px; background: var(--mm-gold-soft); }
      .next .lbl { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--mm-gold); font-weight: 600; }
      .next .main { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-top: 4px; flex-wrap: wrap; }
      .next .name { font-size: 22px; font-weight: 500; }
      .next .t { font-size: 34px; font-weight: 300; line-height: 1; }
      .next .sub { font-size: 13px; color: var(--mm-muted); margin-top: 4px; }
      .day { margin: 14px 2px 4px; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--mm-muted); font-weight: 600; }
      .t-row { display: flex; justify-content: space-between; padding: 7px 10px; border-radius: 10px; font-size: 14.5px; }
      .t-row + .t-row { border-top: 1px solid var(--mm-line); border-radius: 0; }
      .t-row.first { font-weight: 600; }
      .t-row.first .l::before { content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%;
        background: var(--mm-gold); margin-right: 8px; vertical-align: middle; }
      .foot { margin-top: 12px; font-size: 11px; color: var(--mm-muted); }
    `;
  }
  // Which night or day a time belongs to, as people say it.
  _dayLabel(d, now) {
    const hour = +this.fmt(d, { hour: "2-digit", hourCycle: "h23" });
    if (hour < 4 && d - now < 10 * 3600e3) return "Tonight";
    const ymd = this.localYmd(d);
    const long = this.fmt(d, { weekday: "long", day: "numeric", month: "short" });
    if (ymd === this.localYmd(now)) return `Today · ${long}`;
    if (ymd === this.localYmd(new Date(now.getTime() + 864e5))) return `Tomorrow · ${long}`;
    return long;
  }
  _html() {
    const now = new Date();
    const hs = this.st(P + "hijri_date");
    if (!hs) return `<ha-card><div class="muted">Mumineen isn't set up.</div></ha-card>`;
    const a = hs.attributes;
    const raat = a.after_maghrib;
    const tonight = hijriOf(this.localYmd(new Date(now.getTime() + 864e5)));
    const shown = raat ? tonight : { y: a.year, m: a.month, d: a.day };
    // The sensors each hold their coming time, so sorting them gives the next 24 hours in order.
    const rows = TIMES.map(([k, lbl]) => ({ k, lbl, d: this.time(P + k) }))
      .filter((r) => r.d && r.d > now - 60e3)
      .sort((x, y) => x.d - y.d);
    const next = rows[0];
    let last = "";
    const list = rows.map((r, i) => {
      const day = this._dayLabel(r.d, now);
      const head = day !== last ? `<div class="day">${day}</div>` : "";
      last = day;
      return `${head}<div class="t-row ${i === 0 ? "first" : ""}"><span class="l">${r.lbl}</span><span class="num">${this.hm(r.d)}</span></div>`;
    }).join("");
    return `<ha-card>
      <div class="head">
        <div>
          <div class="eyebrow">${raat ? "Tonight · Raat of" : "Today"}</div>
          <h2>${shown.d} ${MONTHS[shown.m - 1]} <span class="muted num" style="font-size:15px">${shown.y} H</span></h2>
          <div class="ar">${arabicDigits(shown.d)} ${MONTHS_AR[shown.m - 1]} ${arabicDigits(shown.y)}</div>
        </div>
        <div class="greg muted">${this.fmt(now, { weekday: "long" })}<br>${this.fmt(now, { day: "numeric", month: "long" })}</div>
      </div>
      ${next ? `<div class="next"><div class="lbl">Next</div>
        <div class="main"><span class="name">${next.lbl}</span><span class="t num">${this.hm(next.d)}</span></div>
        <div class="sub">${this._dayLabel(next.d, now).split(" · ")[0]} · ${this.until(next.d)}</div></div>` : ""}
      ${list}
      <div class="foot">${esc(this._config.location || "Al-Husayni Masjid London")} · mumineen.org</div>
    </ha-card>`;
  }
}

// ---------- Coming up: the next few key miqaats ----------
class MumineenUpcomingCard extends MumineenBase {
  _keys() {
    return Object.values(this._hass.states)
      .filter((s) => s.entity_id.startsWith(P + "days_until_") && s.state !== "" && !isNaN(+s.state))
      .sort((a, b) => +a.state - +b.state)
      .slice(0, this._config.count || 5);
  }
  _watch() { return this._hass ? this._keys().map((s) => s.entity_id) : []; }
  _css() {
    return `
      .list { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
      .item { display: grid; grid-template-columns: 64px 1fr; align-items: center; gap: 14px; padding: 10px 12px;
        border-radius: 14px; cursor: pointer; }
      .item:hover { background: rgba(127,127,127,.06); }
      .item.first { background: var(--mm-gold-soft); }
      .days { text-align: center; line-height: 1; }
      .days b { display: block; font-size: 28px; font-weight: 500; }
      .days small { font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--mm-muted); }
      .item.first .days b { color: var(--mm-gold); }
      .title { font-size: 15px; font-weight: 500; }
      .sub { font-size: 12.5px; color: var(--mm-muted); margin-top: 2px; }
    `;
  }
  _html() {
    const items = this._keys().map((s, i) => {
      const n = +s.state, a = s.attributes;
      const date = a.date ? new Date(a.date + "T12:00:00") : null;
      const big = n === 0 ? "Today" : n === 1 ? "1" : n;
      const unit = n === 0 ? "" : n === 1 ? "day" : "days";
      return `<div class="item ${i === 0 ? "first" : ""}" data-id="${s.entity_id}">
        <div class="days"><b class="num" style="${n === 0 ? "font-size:18px" : ""}">${big}</b><small>${unit}</small></div>
        <div><div class="title">${esc(a.title || s.attributes.friendly_name)}</div>
        <div class="sub">${date ? this.fmt(date, { weekday: "short", day: "numeric", month: "short" }) : ""} · ${esc((a.hijri || "").replace(/ \d+$/, ""))}</div></div>
      </div>`;
    }).join("");
    return `<ha-card><div class="eyebrow">Coming up</div><h2>Key miqaats</h2>
      <div class="list">${items || `<div class="muted">No key miqaats set.</div>`}</div></ha-card>`;
  }
  _draw() {
    super._draw();
    this.shadowRoot.querySelectorAll(".item").forEach((el) => el.addEventListener("click", () => this.moreInfo(el.dataset.id)));
  }
}

// ---------- Week: 7-day strip and list, scrollable week by week ----------
const CALS = [
  ["calendar.mumineen_miqaats", "miqaat"],
  ["calendar.mumineen_my_events", "personal"],
  ["calendar.mumineen_urus", "urus"],
];
class MumineenWeekCard extends MumineenBase {
  constructor() { super(); this._offset = 0; this._cache = {}; this._open = new Set(); this._urusOpen = false; }
  _tickMs() { return 60000; }
  _watch() { return [P + "miqaats_this_week", P + "hijri_date"]; }
  _days() {
    const base = new Date(`${this.localYmd(new Date())}T12:00:00`);
    return [...Array(7)].map((_, i) => {
      const d = new Date(base.getTime() + (this._offset * 7 + i) * 864e5);
      const ymd = this.localYmd(d);
      return { d, ymd, h: hijriOf(ymd) };
    });
  }
  async _load(days) {
    const key = days[0].ymd;
    const hit = this._cache[key];
    if (hit && (hit.loading || Date.now() - hit.at < 15 * 60e3)) return;
    this._cache[key] = { loading: true, events: hit?.events };
    const start = new Date(`${days[0].ymd}T00:00:00`).toISOString();
    const end = new Date(new Date(`${days[6].ymd}T00:00:00`).getTime() + 864e5).toISOString();
    const lists = await Promise.all(CALS.map(([id, kind]) =>
      this._hass.callApi("GET", `calendars/${id}?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`)
        .then((evs) => evs.map((e) => ({ ...e, kind }))).catch(() => [])));
    const events = lists.flat().map((e) => {
      const timed = !!e.start.dateTime;
      const lines = (e.description || "").split("\n").filter(Boolean);
      return {
        id: `${e.uid}|${e.recurrence_id || ""}|${e.kind}`,
        kind: e.kind, raat: timed, title: e.summary,
        ymd: timed ? this.localYmd(new Date(e.start.dateTime)) : e.start.date,
        from: timed ? new Date(e.start.dateTime) : null,
        hijri: (lines[0] || "").replace(/ \d+$/, ""),
        notes: lines.slice(1).filter((l) => !/^https?:/.test(l) && !/^Raat begins/.test(l)),
        link: lines.find((l) => /^https?:/.test(l)) || "",
      };
    }).sort((x, y) => x.ymd.localeCompare(y.ymd) || (x.kind === "miqaat" ? -1 : 1));
    this._cache[key] = { at: Date.now(), events };
    this._draw();
  }
  _css() {
    return `
      .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
      .nav { display: flex; gap: 6px; align-items: center; }
      button { border: 1px solid var(--mm-line); background: none; color: var(--mm-text); border-radius: 999px;
        padding: 5px 11px; font: inherit; font-size: 13px; cursor: pointer; line-height: 1.2; }
      button:hover { border-color: var(--mm-gold); color: var(--mm-gold); }
      button.arrow { width: 32px; padding: 5px 0; font-size: 16px; }
      .range { font-size: 13px; color: var(--mm-muted); margin-top: 3px; }
      .strip { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin: 14px 0 6px; }
      .day { text-align: center; padding: 8px 0 7px; border-radius: 12px; }
      .day.today { background: var(--mm-gold-soft); }
      .day .wd { font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--mm-muted); }
      .day .gd { font-size: 17px; font-weight: 500; margin: 2px 0 1px; }
      .day .hd { font-size: 10.5px; color: var(--mm-muted); }
      .dots { height: 6px; display: flex; justify-content: center; gap: 3px; margin-top: 4px; }
      .dot { width: 5px; height: 5px; border-radius: 50%; background: var(--mm-gold); }
      .dot.personal { background: var(--mm-green); }
      .dot.urus { background: var(--mm-muted); opacity: .45; }
      .ev { border-top: 1px solid var(--mm-line); }
      .ev:first-of-type { border-top: none; }
      .ev summary { list-style: none; display: grid; grid-template-columns: 74px 1fr 14px; gap: 12px; padding: 10px 2px; cursor: pointer; }
      .ev summary::-webkit-details-marker { display: none; }
      .ev summary::after { content: "›"; color: var(--mm-muted); transition: transform .15s; align-self: center; }
      .ev[open] summary::after { transform: rotate(90deg); }
      .when { font-size: 12.5px; color: var(--mm-muted); line-height: 1.35; }
      .when b { display: block; color: var(--mm-text); font-weight: 600; font-size: 13px; }
      .what { font-size: 14.5px; line-height: 1.35; }
      .more { padding: 0 2px 12px 88px; font-size: 13px; color: var(--mm-muted); line-height: 1.5; }
      .more a { color: var(--mm-gold); text-decoration: none; }
      .tag { display: inline-block; font-size: 10.5px; padding: 1px 7px; border-radius: 999px; margin-left: 6px;
        background: rgba(127,127,127,.12); color: var(--mm-muted); vertical-align: 1px; }
      .tag.raat { background: rgba(70,80,160,.14); }
      .tag.personal { background: rgba(47,125,98,.15); color: var(--mm-green); }
      details.urus { margin-top: 8px; font-size: 13px; color: var(--mm-muted); }
      details.urus summary { cursor: pointer; padding: 6px 2px; }
      details.urus ul { margin: 4px 0 0; padding-left: 18px; line-height: 1.6; }
      .none { padding: 10px 2px; color: var(--mm-muted); }
    `;
  }
  _html() {
    const days = this._days();
    const todayYmd = this.localYmd(new Date());
    const data = this._cache[days[0].ymd];
    if (!data || (!data.loading && Date.now() - data.at > 15 * 60e3)) this._load(days);
    const all = data?.events || [];
    const ev = all.filter((e) => e.kind !== "urus"), ur = all.filter((e) => e.kind === "urus");
    const strip = days.map(({ d, ymd, h }, i) => {
      const dots = all.filter((e) => e.ymd === ymd).map((e) => e.kind).sort((x, y) => (x === "urus") - (y === "urus"))
        .slice(0, 4).map((k) => `<span class="dot ${k}"></span>`).join("");
      return `<div class="day ${ymd === todayYmd ? "today" : ""}"><div class="wd">${ymd === todayYmd ? "Today" : this.fmt(d, { weekday: "short" })}</div>
        <div class="gd num">${this.fmt(d, { day: "numeric" })}</div><div class="hd">${h.d}${i === 0 || h.d === 1 ? " " + MONTHS_SHORT[h.m - 1] : ""}</div>
        <div class="dots">${dots}</div></div>`;
    }).join("");
    const list = ev.map((e) => {
      const d = new Date(e.ymd + "T12:00:00");
      const diff = Math.round((d - new Date(todayYmd + "T12:00:00")) / 864e5);
      const label = diff === 0 ? "Today" : diff === 1 ? "Tomorrow" : this.fmt(d, { weekday: "short", day: "numeric", month: "short" });
      const tag = e.raat ? `<span class="tag raat">from Maghrib ${this.hm(e.from)}</span>` : e.kind === "personal" ? `<span class="tag personal">yours</span>` : "";
      const more = [
        e.raat ? `The raat begins at Maghrib, ${this.hm(e.from)}, on ${this.fmt(d, { weekday: "long" })} evening.` : "",
        ...e.notes.map(esc),
        e.link ? `<a href="${esc(e.link)}" target="_blank" rel="noopener">Read on mumineen.org ↗</a>` : "",
      ].filter(Boolean).join("<br>") || "No further details.";
      return `<details class="ev" data-id="${esc(e.id)}" ${this._open.has(e.id) ? "open" : ""}>
        <summary><div class="when"><b>${label}</b>${esc(e.hijri)}</div><div class="what">${esc(e.title)}${tag}</div></summary>
        <div class="more">${more}</div></details>`;
    }).join("");
    const urus = ur.length ? `<details class="urus" ${this._urusOpen ? "open" : ""}><summary>${ur.length} urus this week</summary><ul>${ur.map((e) =>
      `<li>${this.fmt(new Date(e.ymd + "T12:00:00"), { weekday: "short" })} · ${esc(e.title)}</li>`).join("")}</ul></details>` : "";
    const first = days[0].d, lastDay = days[6].d;
    const range = `${this.fmt(first, { weekday: "short", day: "numeric", month: "short" })} – ${this.fmt(lastDay, { weekday: "short", day: "numeric", month: "short" })}`;
    const title = this._offset === 0 ? "Next 7 days" : this._offset === 1 ? "The week after" : `In ${this._offset} weeks`;
    return `<ha-card>
      <div class="top"><div><div class="eyebrow">Miqaats</div><h2>${title}</h2><div class="range">${range}</div></div>
        <div class="nav">
          ${this._offset !== 0 ? `<button class="today-btn">Today</button>` : ""}
          <button class="arrow prev" aria-label="Previous week" ${this._offset <= 0 ? "disabled style='opacity:.35;cursor:default'" : ""}>‹</button>
          <button class="arrow next" aria-label="Next week">›</button>
        </div></div>
      <div class="strip">${strip}</div>
      ${data && !data.events ? `<div class="none">Loading…</div>` : list || `<div class="none">No miqaats these 7 days.</div>`}
      ${urus}
      <div style="margin-top:12px"><button class="add" title="Add one of your own Hijri dates">＋ My event</button></div>
    </ha-card>`;
  }
  _draw() {
    super._draw();
    const root = this.shadowRoot;
    const go = (n) => { this._offset = Math.max(0, n); this._open.clear(); this._urusOpen = false; this._draw(); };
    root.querySelector(".prev")?.addEventListener("click", () => this._offset > 0 && go(this._offset - 1));
    root.querySelector(".next")?.addEventListener("click", () => go(this._offset + 1));
    root.querySelector(".today-btn")?.addEventListener("click", () => go(0));
    root.querySelector(".add")?.addEventListener("click", () => this.moreInfo(this._config.add_entity || "script.mumineen_add_event"));
    root.querySelectorAll("details.ev").forEach((el) => el.addEventListener("toggle", () => {
      if (el.open) this._open.add(el.dataset.id); else this._open.delete(el.dataset.id);
    }));
    root.querySelector("details.urus")?.addEventListener("toggle", (e) => { this._urusOpen = e.target.open; });
  }
}

// ---------- Maghrib banner (show it with a visibility condition on Maghrib soon) ----------
class MumineenMaghribCard extends MumineenBase {
  _tickMs() { return 1000; }
  _watch() { return [P + "maghrib", P + "hijri_date"]; }
  _css() {
    return `
      ha-card { padding: 0; color: #fff8ec; border: none;
        background: linear-gradient(115deg, #3a2a5c 0%, #8a3f5c 45%, #d9773f 80%, #e8b04a 100%); }
      .wrap { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 22px 26px; flex-wrap: wrap; }
      .eyebrow { color: rgba(255,248,236,.85); }
      .big { font-size: 46px; font-weight: 300; line-height: 1; margin-top: 4px; }
      .sub { margin-top: 6px; font-size: 15px; opacity: .9; }
      .count { font-size: 34px; font-weight: 500; font-variant-numeric: tabular-nums; text-align: right; }
      .count small { display: block; font-size: 12px; font-weight: 500; letter-spacing: .14em; text-transform: uppercase; opacity: .8; }
    `;
  }
  _html() {
    const m = this.time(P + "maghrib");
    const now = new Date();
    const left = m ? Math.round((m - now) / 1000) : 0;
    const tonight = hijriOf(this.localYmd(new Date(now.getTime() + 864e5)));
    const count = left <= 0 ? "Now" : left >= 3600 ? `${Math.floor(left / 3600)} h ${String(Math.floor(left / 60) % 60).padStart(2, "0")}`
      : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
    return `<ha-card><div class="wrap">
      <div><div class="eyebrow">Maghrib</div><div class="big num">${this.hm(m)}</div>
        <div class="sub">Raat of ${tonight.d} ${MONTHS[tonight.m - 1]}</div></div>
      <div class="count">${left > 0 ? "<small>in</small>" : "<small>It is time</small>"}${count}</div>
    </div></ha-card>`;
  }
  getCardSize() { return 2; }
}

const CARDS = [
  ["mumineen-today-card", MumineenTodayCard, "Mumineen · Today", "Hijri date, what's next, and the coming namaaz times."],
  ["mumineen-upcoming-card", MumineenUpcomingCard, "Mumineen · Key miqaats", "Countdown to the next key miqaats."],
  ["mumineen-week-card", MumineenWeekCard, "Mumineen · Week", "Seven-day strip and miqaats, scrollable week by week."],
  ["mumineen-maghrib-card", MumineenMaghribCard, "Mumineen · Maghrib banner", "Live countdown to Maghrib."],
];
window.customCards = window.customCards || [];
for (const [tag, cls, name, description] of CARDS) {
  if (!customElements.get(tag)) customElements.define(tag, cls);
  window.customCards.push({ type: tag, name, description });
}
console.info(`%c MUMINEEN-CARDS %c ${VERSION} `, "background:#c49a3a;color:#fff", "background:#333;color:#fff");
