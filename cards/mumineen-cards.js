// Mumineen dashboard cards: today, coming up, this week, Maghrib banner.
// Reads the Mumineen integration's entities (sensor.mumineen_*).
const VERSION = "1.0.0";
const P = "sensor.mumineen_";
const TIMES = [
  ["sihori", "Sihori"], ["fajr", "Fajr"], ["sunrise", "Sunrise"], ["zawaal", "Zawaal"],
  ["zohr_end", "Zohr ends"], ["asr_end", "Asr ends"], ["maghrib", "Maghrib"],
  ["maghrib_end", "Maghrib ends"], ["nisful_layl", "Nisful layl"], ["nisful_layl_end", "Nisful layl ends"],
];
const MONTHS = ["Muharram al-Haraam", "Safar al-Muzaffar", "Rabi al-Awwal", "Rabi al-Aakhar", "Jumada al-Ula",
  "Jumada al-Ukhra", "Rajab al-Asab", "Shaban al-Karim", "Ramadan al-Moazzam", "Shawwal al-Mukarram",
  "Zilqad al-Haraam", "Zilhaj al-Haraam"];
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

// ---------- Today: Hijri date, next namaaz, sun arc, all times ----------
class MumineenTodayCard extends MumineenBase {
  _watch() { return [...TIMES.map(([k]) => P + k), P + "next_namaaz", P + "next_namaaz_time", P + "hijri_date"]; }
  _css() {
    return `
      .head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
      .greg { text-align: right; font-size: 13px; }
      .next { margin: 16px 0 4px; display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
      .next .name { font-size: 15px; color: var(--mm-muted); }
      .next .t { font-size: 40px; font-weight: 300; letter-spacing: -.5px; line-height: 1; }
      .next .in { font-size: 14px; color: var(--mm-gold); font-weight: 500; }
      svg { width: 100%; height: auto; display: block; margin: 6px 0 2px; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 18px; margin-top: 10px; }
      .t-row { display: flex; justify-content: space-between; padding: 7px 10px; border-radius: 10px; font-size: 14px; }
      .t-row.past { color: var(--mm-muted); opacity: .6; }
      .t-row.next { background: var(--mm-gold-soft); color: var(--mm-text); font-weight: 600; }
      .t-row.next .lbl::before { content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%;
        background: var(--mm-gold); margin-right: 8px; vertical-align: middle; }
      .foot { margin-top: 12px; font-size: 11px; color: var(--mm-muted); }
      @media (max-width: 420px) { .grid { grid-template-columns: 1fr; } }
    `;
  }
  _arc(t, now) {
    const W = 320, cx = 160, cy = 132, r = 118;
    const rise = t.sunrise, set = t.maghrib;
    if (!rise || !set) return "";
    const frac = (d) => Math.min(1, Math.max(0, (d - rise) / (set - rise)));
    const pt = (f) => [cx - r * Math.cos(Math.PI * f), cy - r * Math.sin(Math.PI * f)];
    const day = now >= rise && now <= set;
    const f = frac(now);
    const [sx, sy] = pt(f);
    const arcTo = (f2) => { const [x, y] = pt(f2); return `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}`; };
    const ticks = [["zawaal", "Zawaal"], ["zohr_end", "Zohr"], ["asr_end", "Asr"]].filter(([k]) => t[k]).map(([k, lbl]) => {
      const tf = frac(t[k]); const [x1, y1] = pt(tf);
      const ox = (x1 - cx) / r, oy = (y1 - cy) / r;
      const [lx, ly] = [cx + (r + 16) * ox, cy + (r + 16) * oy];
      return `<circle cx="${x1}" cy="${y1}" r="3" fill="var(--card-background-color, #fff)" stroke="var(--mm-muted)" stroke-width="1.5"/>
        <text x="${lx}" y="${ly + 3}" text-anchor="middle" font-size="10" fill="var(--mm-muted)">${lbl} ${this.hm(t[k])}</text>`;
    }).join("");
    const body = day
      ? `<circle cx="${sx}" cy="${sy}" r="14" fill="rgba(196,154,58,.22)"/><circle cx="${sx}" cy="${sy}" r="8" fill="var(--mm-gold)"/>`
      : `<g transform="translate(${cx} ${cy - 56})"><path d="M 6 -14 A 14 14 0 1 0 6 14 A 11 11 0 1 1 6 -14 Z" fill="var(--mm-muted)" opacity=".75"/></g>
         <text x="${cx}" y="${cy - 18}" text-anchor="middle" font-size="11" fill="var(--mm-muted)">${now > set ? "Night" : "Before sunrise"}</text>`;
    return `<svg viewBox="0 0 ${W} 160" role="img" aria-label="Sun position between sunrise and Maghrib">
      <defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#e8b04a"/><stop offset="1" stop-color="#d9773f"/></linearGradient></defs>
      <path d="M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}" fill="none" stroke="var(--mm-line)" stroke-width="2" stroke-dasharray="3 5"/>
      ${f > 0 ? `<path d="${arcTo(day ? f : 1)}" fill="none" stroke="url(#g)" stroke-width="3" stroke-linecap="round" opacity="${day ? 1 : 0.35}"/>` : ""}
      <line x1="${cx - r - 22}" y1="${cy}" x2="${cx + r + 22}" y2="${cy}" stroke="var(--mm-line)" stroke-width="1"/>
      ${ticks}${body}
      <text x="${cx - r}" y="${cy + 18}" text-anchor="middle" font-size="11" fill="var(--mm-muted)">Sunrise ${this.hm(rise)}</text>
      <text x="${cx + r}" y="${cy + 18}" text-anchor="middle" font-size="11" fill="var(--mm-gold)" font-weight="600">Maghrib ${this.hm(set)}</text>
    </svg>`;
  }
  _html() {
    const now = new Date();
    const t = Object.fromEntries(TIMES.map(([k]) => [k, this.time(P + k)]));
    const hs = this.st(P + "hijri_date");
    if (!hs) return `<ha-card><div class="muted">Mumineen isn't set up.</div></ha-card>`;
    const a = hs.attributes;
    const raat = a.after_maghrib;
    const tonight = hijriOf(this.localYmd(new Date(now.getTime() + 864e5)));
    const shown = raat ? tonight : { y: a.year, m: a.month, d: a.day };
    const next = this.st(P + "next_namaaz")?.state;
    const nextT = this.time(P + "next_namaaz_time");
    let marked = false;
    const rows = TIMES.map(([k, lbl]) => {
      const d = t[k]; if (!d) return "";
      let cls = d < now ? "past" : "";
      if (!marked && d >= now) { cls = "next"; marked = true; }
      return `<div class="t-row ${cls}"><span class="lbl">${lbl}</span><span class="num">${this.hm(d)}</span></div>`;
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
      ${nextT ? `<div class="next"><span class="name">Next · ${esc(next)}</span><span class="t num">${this.hm(nextT)}</span><span class="in">${this.until(nextT)}</span></div>` : ""}
      ${this._arc(t, now)}
      <div class="grid">${rows}</div>
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

// ---------- This week: 7-day strip and list ----------
class MumineenWeekCard extends MumineenBase {
  _watch() { return [P + "miqaats_this_week"]; }
  _css() {
    return `
      .top { display: flex; justify-content: space-between; align-items: flex-start; }
      .add { border: 1px solid var(--mm-line); background: none; color: var(--mm-text); border-radius: 999px;
        padding: 6px 12px; font: inherit; font-size: 13px; cursor: pointer; }
      .add:hover { border-color: var(--mm-gold); color: var(--mm-gold); }
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
      .ev { display: grid; grid-template-columns: 70px 1fr; gap: 12px; padding: 9px 2px; border-top: 1px solid var(--mm-line); }
      .ev:first-of-type { border-top: none; }
      .when { font-size: 12.5px; color: var(--mm-muted); line-height: 1.35; }
      .when b { display: block; color: var(--mm-text); font-weight: 600; font-size: 13px; }
      .what { font-size: 14.5px; line-height: 1.35; }
      .tag { display: inline-block; font-size: 10.5px; padding: 1px 7px; border-radius: 999px; margin-left: 6px;
        background: rgba(127,127,127,.12); color: var(--mm-muted); vertical-align: 1px; }
      .tag.raat { background: rgba(70,80,160,.14); }
      .tag.personal { background: rgba(47,125,98,.15); color: var(--mm-green); }
      details { margin-top: 8px; font-size: 13px; color: var(--mm-muted); }
      summary { cursor: pointer; padding: 6px 2px; }
      details ul { margin: 4px 0 0; padding-left: 18px; line-height: 1.6; }
      .none { padding: 10px 2px; color: var(--mm-muted); }
    `;
  }
  _html() {
    const s = this.st(P + "miqaats_this_week");
    const ev = s?.attributes.events || [], ur = s?.attributes.urus || [];
    const today = new Date();
    const days = [...Array(7)].map((_, i) => {
      const d = new Date(today.getTime() + i * 864e5);
      const ymd = this.localYmd(d);
      return { d, ymd, h: hijriOf(ymd) };
    });
    const strip = days.map(({ d, ymd, h }, i) => {
      const dots = [...ev.filter((e) => e.date === ymd).map((e) => e.kind), ...ur.filter((e) => e.date === ymd).map(() => "urus")]
        .slice(0, 4).map((k) => `<span class="dot ${k}"></span>`).join("");
      return `<div class="day ${i === 0 ? "today" : ""}"><div class="wd">${i === 0 ? "Today" : this.fmt(d, { weekday: "short" })}</div>
        <div class="gd num">${this.fmt(d, { day: "numeric" })}</div><div class="hd">${h.d} ${MONTHS[h.m - 1].split(" ")[0].slice(0, 5)}</div>
        <div class="dots">${dots}</div></div>`;
    }).join("");
    const list = ev.map((e) => {
      const d = new Date(e.date + "T12:00:00");
      const label = e.days === 0 ? "Today" : e.days === 1 ? "Tomorrow" : this.fmt(d, { weekday: "short", day: "numeric", month: "short" });
      const tag = e.raat ? `<span class="tag raat">from Maghrib</span>` : e.kind === "personal" ? `<span class="tag personal">yours</span>` : "";
      return `<div class="ev"><div class="when"><b>${label}</b>${esc(e.hijri)}</div><div class="what">${esc(e.title)}${tag}</div></div>`;
    }).join("");
    const urus = ur.length ? `<details><summary>${ur.length} urus this week</summary><ul>${ur.map((e) =>
      `<li>${this.fmt(new Date(e.date + "T12:00:00"), { weekday: "short" })} · ${esc(e.title)}</li>`).join("")}</ul></details>` : "";
    return `<ha-card>
      <div class="top"><div><div class="eyebrow">Next 7 days</div><h2>This week</h2></div>
        <button class="add" title="Add one of your own Hijri dates">＋ My event</button></div>
      <div class="strip">${strip}</div>
      ${list || `<div class="none">No miqaats in the next 7 days.</div>`}
      ${urus}
    </ha-card>`;
  }
  _draw() {
    const open = this.shadowRoot.querySelector("details")?.open;
    super._draw();
    const det = this.shadowRoot.querySelector("details");
    if (det && open) det.open = true;
    this.shadowRoot.querySelector(".add")?.addEventListener("click", () => this.moreInfo(this._config.add_entity || "script.mumineen_add_event"));
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
    const count = left > 0 ? `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}` : "Now";
    return `<ha-card><div class="wrap">
      <div><div class="eyebrow">Maghrib</div><div class="big num">${this.hm(m)}</div>
        <div class="sub">Raat of ${tonight.d} ${MONTHS[tonight.m - 1]}</div></div>
      <div class="count">${left > 0 ? "<small>in</small>" : "<small>It is time</small>"}${count}</div>
    </div></ha-card>`;
  }
  getCardSize() { return 2; }
}

const CARDS = [
  ["mumineen-today-card", MumineenTodayCard, "Mumineen · Today", "Hijri date, next namaaz, sun arc and today's times."],
  ["mumineen-upcoming-card", MumineenUpcomingCard, "Mumineen · Key miqaats", "Countdown to the next key miqaats."],
  ["mumineen-week-card", MumineenWeekCard, "Mumineen · This week", "Seven-day strip and the week's miqaats."],
  ["mumineen-maghrib-card", MumineenMaghribCard, "Mumineen · Maghrib banner", "Live countdown to Maghrib."],
];
window.customCards = window.customCards || [];
for (const [tag, cls, name, description] of CARDS) {
  if (!customElements.get(tag)) customElements.define(tag, cls);
  window.customCards.push({ type: tag, name, description });
}
console.info(`%c MUMINEEN-CARDS %c ${VERSION} `, "background:#c49a3a;color:#fff", "background:#333;color:#fff");
