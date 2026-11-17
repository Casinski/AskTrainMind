/* AskTrainMind Web — interfaccia (JS puro, nessuna dipendenza esterna) */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const COLL = new Intl.Collator("it", {numeric: true, sensitivity: "base"});
const LS = {
  get(k, d) { try { const v = localStorage.getItem("atm." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("atm." + k, JSON.stringify(v)); } catch {} },
};

async function api(url, opt = {}) {
  if (opt.json !== undefined) {
    opt.method = opt.method || "POST";
    opt.headers = {"Content-Type": "application/json"};
    opt.body = JSON.stringify(opt.json);
  }
  const r = await fetch(url, opt);
  let data = null;
  try { data = await r.json(); } catch { data = null; }
  if (!r.ok) throw new Error((data && data.error) || `Errore ${r.status}`);
  return data;
}

function toast(msg, kind = "", ms = 4000) {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), ms);
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove();
  }
  toast("Copiato negli appunti", "ok", 1500);
}

/* ── Markdown essenziale (senza _corsivo_: i FUNC ID contengono "_") ── */
function mdInline(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|#[\w-]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\[\[(.+?)\]\]/g, "<mark>$1</mark>");
}
function md(src) {
  const lines = String(src || "").replace(/\r/g, "").split("\n");
  let out = "", list = null, i = 0;
  const close = () => { if (list) { out += `</${list}>`; list = null; } };
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) {
      close(); const buf = []; i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      out += `<pre><code>${esc(buf.join("\n"))}</code></pre>`; i++; continue;
    }
    if (/^\s*\|.*\|\s*$/.test(l) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      close();
      const cells = r => r.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      out += "<table><thead><tr>" + cells(l).map(c => `<th>${mdInline(c)}</th>`).join("") + "</tr></thead><tbody>";
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) out += "<tr>" + cells(lines[i++]).map(c => `<td>${mdInline(c)}</td>`).join("") + "</tr>";
      out += "</tbody></table>"; continue;
    }
    let m;
    if ((m = l.match(/^(#{1,4})\s+(.*)/))) { close(); const n = m[1].length; const id = slug(m[2]); out += `<h${n} id="${id}">${mdInline(m[2])}</h${n}>`; }
    else if ((m = l.match(/^\s*[-*•]\s+(.*)/))) { if (list !== "ul") { close(); out += "<ul>"; list = "ul"; } out += `<li>${mdInline(m[1])}</li>`; }
    else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { close(); out += "<ol>"; list = "ol"; } out += `<li>${mdInline(m[1])}</li>`; }
    else if ((m = l.match(/^>\s?(.*)/))) { close(); out += `<blockquote>${mdInline(m[1])}</blockquote>`; }
    else if (/^\s*---+\s*$/.test(l)) { close(); out += "<hr>"; }
    else if (!l.trim()) { close(); }
    else { close(); out += `<p>${mdInline(l)}</p>`; }
    i++;
  }
  close();
  return out;
}
const slug = s => String(s).toLowerCase().replace(/[^\w\sàèéìòù-]/g, "").trim().replace(/\s+/g, "-");

/* ── Stato globale ─────────────────────────────────────────────────── */
const APP = {meta: null, key: "", colors: {}, sheets: {}, current: LS.get("sheet", null), view: "explore",
             functions: [], configs: [], gloss: []};

function cfgColor(c) { return APP.colors[c] || "#8a94a6"; }

/* ── Navigazione ───────────────────────────────────────────────────── */
function showView(v) {
  APP.view = v;
  $$("#mainTabs button").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  $$(".view").forEach(s => s.classList.toggle("active", s.id === "view-" + v));
  if (v === "ask") Ask.init();
  if (v === "explore" && window.Explorer) Explorer.open();
  if (v === "learn" && window.Learn) Learn.open();
  if (v === "tools") Tools.open();
  if (v === "guide") Guide.open();
  if (v === "sheets") Grid.render();
  history.replaceState(null, "", "#" + v);
}
$("#mainTabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b) showView(b.dataset.view); });
window.addEventListener("hashchange", () => {
  const v = location.hash.slice(1);
  if (v !== APP.view && $("#view-" + v) && !$(`#mainTabs [data-view="${v}"]`)?.hidden) showView(v);
});

/* ── Modal (PDF / immagini) ────────────────────────────────────────── */
const Modal = {
  pdf(fid, page, title) {
    const url = `/api/file/${fid}#page=${page || 1}`;
    $("#modalTitle").textContent = title || "Documento";
    $("#modalOpen").href = url;
    $("#modalBody").innerHTML = `<iframe src="${url}" title="${esc(title)}"></iframe>`;
    $("#modal").hidden = false;
  },
  img(src, title, big) {
    $("#modalTitle").textContent = title || "Anteprima";
    $("#modalOpen").href = big || src;
    $("#modalBody").innerHTML = `<img src="${esc(big || src)}" alt="">`;
    $("#modal").hidden = false;
  },
  pages(fid, first, last, title) {
    $("#modalTitle").textContent = title;
    $("#modalOpen").href = `/api/file/${fid}#page=${first}`;
    let h = "<div style='display:flex;flex-direction:column;align-items:center'>";
    for (let p = first; p <= Math.min(last, first + 30); p++)
      h += `<img class="pg" loading="lazy" src="/api/page.png?fid=${fid}&page=${p}&dpi=130" alt="pag. ${p}" title="pag. ${p}">`;
    $("#modalBody").innerHTML = h + "</div>";
    $("#modal").hidden = false;
  },
  close() { $("#modal").hidden = true; $("#modalBody").innerHTML = ""; },
};
$("#modalClose").onclick = Modal.close;
$("#modal").addEventListener("click", e => { if (e.target.id === "modal") Modal.close(); });

async function openDocLink(info, ev) {
  const items = [];
  let res = null;
  try { res = await api(`/api/doc?doc=${encodeURIComponent(info.doc)}&cfg=${encodeURIComponent(info.cfg)}`); } catch {}
  const title = `${info.doc} — ${info.cfg}${res && res.code ? " (" + res.code + ")" : ""}`;
  if (res && res.fid) items.push([`📄 Apri il PDF sul PC alla pag. ${info.page || 1}`, () => Modal.pdf(res.fid, info.page, title)]);
  if (info.url) items.push(["🌐 Apri su SharePoint", () => window.open(info.url, "_blank", "noopener")]);
  if (!items.length) { toast("Documento non trovato sul PC e senza collegamento SharePoint", "bad"); return; }
  if (items.length === 1 || !ev) { items[0][1](); return; }
  Popup.menu(ev.clientX, ev.clientY, [[`<span class="ttl">${esc(title)}</span>`, null], ...items]);
}

/* ── Popup generico ────────────────────────────────────────────────── */
const Popup = {
  el: $("#popup"),
  open(x, y, html, w) {
    const p = this.el;
    p.innerHTML = html; p.hidden = false;
    p.style.width = (w || 300) + "px";
    const r = p.getBoundingClientRect();
    p.style.left = Math.max(6, Math.min(x, innerWidth - r.width - 8)) + "px";
    p.style.top = Math.max(6, Math.min(y, innerHeight - r.height - 8)) + "px";
    return p;
  },
  menu(x, y, items) {
    const p = this.open(x, y, items.map((it, i) => it[1] ? `<button class="mi" data-i="${i}">${it[0]}</button>` : `<div>${it[0]}</div>`).join(""), 320);
    p.onclick = e => { const b = e.target.closest(".mi"); if (b) { this.close(); items[+b.dataset.i][1](); } };
  },
  close() { this.el.hidden = true; this.el.onclick = null; },
};
document.addEventListener("mousedown", e => { if (!Popup.el.hidden && !Popup.el.contains(e.target) && !e.target.closest(".fb,#btnCols,#btnCfg")) Popup.close(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") { Popup.close(); Modal.close(); } });

/* ════════════════════════════════════════════════════════════════════
   FOGLI — griglia virtualizzata stile Excel
   ════════════════════════════════════════════════════════════════════ */
const HEAD_H = 34, ROWHD_W = 46;
/* Filtri rapidi per foglio: row = testo presente nella riga; col + eq/has = valore di una colonna */
const QUICK = {
  "Funzioni": [
    {id: "ai", icon: "🧠", label: "Solo Funzioni AI", col: /^info doc/i, eq: "funzioni ai", tip: "Solo le righe «Funzioni AI» (sintesi della funzione per configurazione)"},
    {id: "link", icon: "🔗", label: "Solo link documenti", col: /^info doc/i, eq: "link", tip: "Solo le righe con i link ai documenti"},
    {id: "appr", icon: "📝", label: "Approfondimenti", col: /^info doc/i, has: "approf", tip: "Solo le righe «Approfondimenti»"},
    {id: "comp", icon: "🔌", label: "Componenti", col: /^info doc/i, has: "component", tip: "Solo le righe dei componenti del circuito elettrico"},
  ],
  "Requisiti": [
    {id: "diff", icon: "≠", label: "Con differenze", row: "found diff", tip: "Requisiti con testo diverso rispetto alla base (FOUND DIFF)"},
    {id: "miss", icon: "➕", label: "Non presenti nella base", row: "miss vzi_base req", tip: "Requisiti assenti nella configurazione base"},
  ],
  "Reqs not matched": [
    {id: "nolink", icon: "🔗", label: "Link documentale mancante", row: "mancanza link", tip: "Configurazioni senza link al documento nel foglio Funzioni"},
    {id: "sim", icon: "≈", label: "Requisiti simili", row: "requisito simile", tip: "Requisiti con ID diverso ma descrizione simile (messi uno accanto all'altro)"},
    {id: "pend", icon: "⏳", label: "Nota AI da generare", row: "nota ai non generata", tip: "Righe in attesa della nota AI"},
  ],
  "Index Funzioni": [
    {id: "nf", icon: "❌", label: "NOT FOUND", row: "not found", tip: "Funzioni non trovate in almeno una configurazione"},
    {id: "na", icon: "➖", label: "N/A", row: "n/a", tip: "Funzioni non applicabili in almeno una configurazione"},
  ],
};
const Grid = {
  S: null,                        // stato del foglio corrente
  el: $("#grid"), inner: $("#gridInner"),
  rh: LS.get("rowH", 28),
  mode: LS.get("filterMode", "head"),

  async load(name, keepState) {
    APP.current = name; LS.set("sheet", name);
    $$("#sheetTabs button").forEach(b => b.classList.toggle("active", b.dataset.name === name));
    let st = APP.sheets[name];
    if (!st || !st.data) {
      this.inner.innerHTML = `<div class="empty-grid"><span class="spin"></span> Caricamento del foglio «${esc(name)}»…</div>`;
      this.inner.style.height = "auto";
      let data;
      try { data = await api(`/api/sheet/${encodeURIComponent(name)}`); }
      catch (e) { this.inner.innerHTML = `<div class="empty-grid">${esc(e.message)}</div>`; return; }
      st = this.prepare(name, data, keepState ? APP.sheets[name] : null);
      APP.sheets[name] = st;
    }
    if (APP.current !== name) return;
    this.S = st;
    $("#sheetNote").hidden = !st.data.note;
    $("#sheetNote").textContent = st.data.note || "";
    $("#gSearch").value = st.search || "";
    this.apply();
  },

  prepare(name, data, old) {
    const saved = LS.get("view." + name, {});
    const n = data.cols.length;
    const rows = data.rows;
    const headKind = name === "Index Funzioni" ? "doc" : "func";
    const grp = new Int32Array(rows.length);
    let g = -1;
    rows.forEach((r, i) => { if (data.hierarchical && r.k === headKind) g = i; grp[i] = data.hierarchical ? (g < 0 ? i : g) : i; });
    // valori "trascinati" (FUNC ID / descrizione) per filtri e ordinamento
    const carry = new Set(data.carry || []);
    const val = (i, c) => {
      const v = rows[i].v[c] || "";
      if (v || !carry.has(c)) return v;
      return rows[grp[i]].v[c] || "";
    };
    const styles = (data.styles || []).map(s => [s.c ? `color:${s.c}` : "", s.bg ? `background:${s.bg}` : "", s.b ? "font-weight:700" : "", s.i ? "font-style:italic" : "", s.s ? "text-decoration:line-through" : ""].filter(Boolean).join(";"));
    return {
      name, data, rows, grp, val, styles,
      widths: (saved.widths && saved.widths.length === n) ? saved.widths : data.cols.map(c => Math.min(c.w, 380)),
      hidden: new Set(saved.hidden || []),
      freeze: saved.freeze ?? data.freezeCols ?? 0,
      filters: old ? old.filters : {}, sort: old ? old.sort : null, search: old ? old.search : "",
      quick: old ? old.quick : [],
      order: [], sel: null, anchor: null, lc: null,
    };
  },

  save() {
    const S = this.S; if (!S) return;
    LS.set("view." + S.name, {widths: S.widths, hidden: [...S.hidden], freeze: S.freeze});
  },

  vcols() { const S = this.S; return S.data.cols.map((_, i) => i).filter(i => !S.hidden.has(i)); },

  lower(i) {
    const S = this.S;
    if (!S.lc) S.lc = new Array(S.rows.length);
    if (!S.lc[i]) {
      const r = S.rows[i];
      let t = r.v.join("\u0001");
      for (const c of S.data.carry) if (!r.v[c]) t += "\u0001" + S.val(i, c);
      if (r.l) for (const k in r.l) if (r.l[k].doc) t += "\u0001" + r.l[k].doc;
      S.lc[i] = t.toLowerCase();
    }
    return S.lc[i];
  },

  passes(i, skipCol) {
    const S = this.S;
    if (S.quick && S.quick.length) for (const q of S.quick) if (!this.quickTest(q, i)) return false;
    for (const k in S.filters) {
      const c = +k; if (c === skipCol) continue;
      const f = S.filters[k], v = S.val(i, c);
      if (f.vals && !f.vals.has(v)) return false;
      if (f.text && !v.toLowerCase().includes(f.text)) return false;
    }
    if (S.search) {
      const terms = S.searchTerms;
      const t = this.lower(i);
      for (const w of terms) if (!t.includes(w)) return false;
    }
    return true;
  },

  apply() {
    const S = this.S; if (!S) return;
    const t0 = performance.now();
    S.searchTerms = (S.search || "").toLowerCase().split(/\s+/).filter(Boolean);
    S.hlRe = S.searchTerms.length ? new RegExp("(" + S.searchTerms.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")", "gi") : null;
    const active = Object.keys(S.filters).length || S.searchTerms.length || (S.quick && S.quick.length);
    const n = S.rows.length;
    let keep;
    if (!active) keep = null;
    else {
      const match = new Uint8Array(n), grpHit = new Uint8Array(n);
      let hits = 0;
      for (let i = 0; i < n; i++) if (this.passes(i)) { match[i] = 1; grpHit[S.grp[i]] = 1; hits++; }
      S.matchCount = hits;
      keep = new Uint8Array(n);
      for (let i = 0; i < n; i++) {
        if (this.mode === "rows") keep[i] = match[i];
        else if (this.mode === "block") keep[i] = grpHit[S.grp[i]];
        else keep[i] = match[i] || (S.grp[i] === i && grpHit[i]);
      }
    }
    let order = [];
    for (let i = 0; i < n; i++) if (!keep || keep[i]) order.push(i);
    if (S.sort) {
      const {col, dir} = S.sort;
      const num = s => { const x = parseFloat(String(s).replace(",", ".")); return isNaN(x) || !/^\s*-?[\d.,]+\s*%?\s*$/.test(s) ? null : x; };
      const cmp = (a, b) => {
        if (!a && b) return 1; if (a && !b) return -1;
        const na = num(a), nb = num(b);
        const r = na != null && nb != null ? na - nb : COLL.compare(a, b);
        return r * dir;
      };
      if (S.data.hierarchical) {
        const groups = new Map();
        for (const i of order) { const g = S.grp[i]; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(i); }
        const key = g => { for (const i of groups.get(g)) { const v = S.val(i, col); if (v) return v; } return ""; };
        const keys = new Map([...groups.keys()].map(g => [g, key(g)]));
        order = [...groups.keys()].sort((a, b) => cmp(keys.get(a), keys.get(b)) || a - b).flatMap(g => groups.get(g));
      } else {
        order.sort((a, b) => cmp(S.val(a, col), S.val(b, col)) || a - b);
      }
    }
    S.order = order;
    S.sel = null; S.anchor = null;
    $("#gSearchCount").textContent = S.searchTerms.length ? `${S.matchCount} righe` : "";
    const nf = Object.keys(S.filters).length;
    $("#rowCount").textContent = `${order.length.toLocaleString("it")} di ${n.toLocaleString("it")} righe`;
    $("#filtersInfo").innerHTML = nf ? `<b>${nf}</b> filtr${nf === 1 ? "o" : "i"} attiv${nf === 1 ? "o" : "i"}` : "";
    this.drawChips();
    this.el.scrollTop = Math.min(this.el.scrollTop, Math.max(0, order.length * this.rh - 100));
    this.render(true);
    this.showDetail();
    if (performance.now() - t0 > 200) console.debug("apply", performance.now() - t0);
  },

  layout() {
    const S = this.S, vc = this.vcols();
    const left = []; let x = ROWHD_W;
    let frozen = Math.min(S.freeze, vc.length);
    vc.forEach((c, k) => { left[k] = x; x += S.widths[c]; });
    const lim = (this.el.clientWidth || 1000) * 0.55;
    while (frozen > 0 && (left[frozen] ?? x) - ROWHD_W > lim) frozen--;
    return {vc, left, frozen, total: x};
  },

  headerHTML(L) {
    const S = this.S, cols = S.data.cols;
    let h = `<div class="ghead" style="width:${L.total}px"><div class="rowhd" title="Righe">#</div>`;
    L.vc.forEach((c, k) => {
      const col = cols[c], f = S.filters[c];
      const frz = k < L.frozen;
      const so = S.sort && S.sort.col === c ? (S.sort.dir > 0 ? "▲" : "▼") : "";
      const style = `width:${S.widths[c]}px;${frz ? `left:${L.left[k]}px;` : ""}${col.cfg ? `--cc:${cfgColor(col.t)};` : ""}`;
      h += `<div class="hc${frz ? " frz" : ""}${frz && k === L.frozen - 1 ? " lastfrz" : ""}${col.cfg ? " cfg" : ""}" data-c="${c}" style="${style}" title="${esc(col.t)} — clic per ordinare">
        <span class="t">${esc(col.t)}</span><span class="so">${so}</span>
        <button class="fb${f ? " on" : ""}" data-c="${c}" title="Filtro">${f ? "⧩" : "▾"}</button><span class="rz" data-c="${c}"></span></div>`;
    });
    return h + "</div>";
  },

  cellHTML(i, c, S) {
    const row = S.rows[i];
    let v = row.v[c] || "";
    const link = row.l && row.l[c];
    if (link) {
      if (link.doc) {
        const label = `📄 ${link.doc}${link.page ? " · p." + link.page : ""}`;
        return `<a class="lk" data-act="doc">${esc(label)}</a>`;
      }
      if (link.url) return `<a class="lk" href="${esc(link.url)}" target="_blank" rel="noopener">${this.hl(v || link.url)}</a>`;
    }
    if (!v && S.data.carry.includes(c) && S.grp[i] !== i && this.rh > 28) return "";
    if (v.length > 900) v = v.slice(0, 900) + "…";
    return this.hl(v);
  },

  hl(v) {
    const S = this.S;
    const h = esc(v);
    return S.hlRe ? h.replace(S.hlRe, "<mark>$1</mark>") : h;
  },

  render(full) {
    const S = this.S;
    if (!S || APP.view !== "sheets") return;
    const L = this.layout();
    const rh = this.rh, n = S.order.length;
    this.inner.className = "grid-inner rh" + rh;
    this.inner.style.width = L.total + "px";
    this.inner.style.height = HEAD_H + n * rh + 2 + "px";
    const top = this.el.scrollTop, hgt = this.el.clientHeight || 600;
    const a = Math.max(0, Math.floor((top - HEAD_H) / rh) - 8), b = Math.min(n, Math.ceil((top + hgt) / rh) + 8);
    if (!full && this._range && this._range[0] === a && this._range[1] === b) return;
    this._range = [a, b];
    let h = this.headerHTML(L);
    if (!n) h += `<div class="empty-grid" style="position:absolute;top:${HEAD_H}px;left:0;width:100%">Nessuna riga corrisponde ai filtri. <button class="btn" onclick="Grid.clearAll()">Rimuovi filtri</button></div>`;
    const sel = S.sel, rng = this.selRange();
    for (let d = a; d < b; d++) {
      const i = S.order[d], row = S.rows[i];
      const kc = "k-" + (S.name === "Index Funzioni" ? (row.k === "doc" ? "func" : "") : (row.k || ""));
      h += `<div class="r ${kc}" style="top:${HEAD_H + d * rh}px;height:${rh}px;width:${L.total}px"><div class="rowhd">${i + 2}</div>`;
      L.vc.forEach((c, k) => {
        const frz = k < L.frozen;
        const st = row.s && row.s[c] != null ? S.styles[row.s[c]] : "";
        let cls = "c";
        if (frz) cls += " frz" + (k === L.frozen - 1 ? " lastfrz" : "");
        if (row.n && row.n[c]) cls += " cm";
        if (sel && sel.d === d && sel.c === c) cls += " sel";
        else if (rng && d >= rng.d1 && d <= rng.d2 && k >= rng.k1 && k <= rng.k2) cls += " insel";
        const title = row.n && row.n[c] ? ` title="${esc(row.n[c])}"` : "";
        h += `<div class="${cls}" data-d="${d}" data-c="${c}" style="width:${S.widths[c]}px;${frz ? `left:${L.left[k]}px;` : ""}${st}"${title}>${this.cellHTML(i, c, S)}</div>`;
      });
      h += "</div>";
    }
    this.inner.innerHTML = h;
  },

  selRange() {
    const S = this.S;
    if (!S.sel || !S.anchor) return null;
    const vc = this.vcols();
    const k1 = vc.indexOf(S.sel.c), k2 = vc.indexOf(S.anchor.c);
    return {d1: Math.min(S.sel.d, S.anchor.d), d2: Math.max(S.sel.d, S.anchor.d), k1: Math.min(k1, k2), k2: Math.max(k1, k2), vc};
  },

  select(d, c, extend) {
    const S = this.S;
    if (d < 0 || d >= S.order.length) return;
    S.sel = {d, c};
    if (!extend) S.anchor = {d, c};
    this.render(true);
    this.showDetail();
    this.updateSelInfo();
  },

  ensureVisible() {
    const S = this.S; if (!S.sel) return;
    const y = HEAD_H + S.sel.d * this.rh, el = this.el;
    if (y - HEAD_H < el.scrollTop) el.scrollTop = y - HEAD_H;
    else if (y + this.rh > el.scrollTop + el.clientHeight) el.scrollTop = y + this.rh - el.clientHeight + 16;
  },

  rangeValues() {
    const S = this.S, r = this.selRange();
    if (!r) return [];
    const out = [];
    for (let d = r.d1; d <= r.d2; d++) {
      const i = S.order[d];
      out.push(r.vc.slice(r.k1, r.k2 + 1).map(c => S.rows[i].v[c] || ""));
    }
    return out;
  },

  updateSelInfo() {
    const vals = this.rangeValues().flat();
    const nums = vals.map(v => parseFloat(String(v).replace(",", "."))).filter((x, k) => !isNaN(x) && /^\s*-?[\d.,]+\s*%?\s*$/.test(vals[k]));
    let s = vals.length > 1 ? `Conteggio: ${vals.filter(Boolean).length}` : "";
    if (nums.length > 1) {
      const sum = nums.reduce((a, b) => a + b, 0);
      s += ` · Somma: ${sum.toLocaleString("it")} · Media: ${(sum / nums.length).toLocaleString("it", {maximumFractionDigits: 2})}`;
    }
    $("#selInfo").textContent = s;
  },

  showDetail() {
    const S = this.S, box = $("#detail");
    if (!S || !S.sel) {
      $("#cellRef").textContent = "—"; $("#cellVal").textContent = "";
      box.innerHTML = `<div class="detail-empty">Seleziona una cella per vederne qui il contenuto completo, i commenti e i collegamenti.</div>`;
      return;
    }
    const i = S.order[S.sel.d], c = S.sel.c, row = S.rows[i], col = S.data.cols[c];
    const v = row.v[c] || "", note = row.n && row.n[c], link = row.l && row.l[c];
    const letter = colLetter(c) + (i + 2);
    $("#cellRef").textContent = `${letter} · ${col.t}`;
    $("#cellVal").textContent = v.replace(/\n/g, " ⏎ ");
    const gv = S.data.hierarchical ? S.rows[S.grp[i]].v[0] : "";
    let h = `<h4>${esc(S.name)} · cella ${letter}</h4><div style="font-weight:700;font-size:15px;margin-bottom:8px">${esc(col.t)}</div>`;
    if (gv && c !== 0) h += `<h4>${S.name === "Index Funzioni" ? "Documento" : "Funzione"}</h4><div class="dv">${esc(gv)}${S.rows[S.grp[i]].v[1] && S.name !== "Index Funzioni" ? "<br><small>" + esc(S.rows[S.grp[i]].v[1]) + "</small>" : ""}</div>`;
    if (row.d && S.name === "Funzioni") h += `<h4>Documento</h4><div class="dv">${esc(row.d)}${row.v[4] ? " — " + esc(row.v[4]) : ""}</div>`;
    h += `<h4>Contenuto</h4><div class="dv">${v ? this.hl(v) : "<i style='color:#999'>(vuota)</i>"}</div>`;
    if (note) h += `<h4>Commento</h4><div class="dv dcm">${esc(note)}</div>`;
    h += `<div class="acts">`;
    if (link && link.doc) h += `<button class="btn" data-act="doclink">📄 Apri documento${link.page ? " (p." + link.page + ")" : ""}</button>`;
    if (link && link.url) h += `<a class="btn" href="${esc(link.url)}" target="_blank" rel="noopener">🌐 SharePoint</a>`;
    if (v) h += `<button class="btn" data-act="copy">⧉ Copia</button><button class="btn" data-act="filterv">⧩ Filtra per questo valore</button>`;
    const fid = S.data.hierarchical && S.name !== "Index Funzioni" ? gv : (S.name === "Reqs not matched" ? row.v[0] : (S.name === "Index Funzioni" ? row.v[0] : ""));
    if (fid && /_/.test(fid)) {
      h += `<button class="btn" data-act="only" data-f="${esc(fid)}">🔎 Mostra solo questa funzione</button>`;
      h += `<button class="btn primary" data-act="ask" data-f="${esc(fid)}">💬 Chiedi su ${esc(fid)}</button>`;
    }
    h += `</div>`;
    box.innerHTML = h;
  },

  clearAll() {
    const S = this.S; if (!S) return;
    S.filters = {}; S.sort = null; S.search = ""; S.quick = []; $("#gSearch").value = "";
    this.apply();
  },

  // ── filtri rapidi (icone) e chip dei filtri attivi ──
  quickDefs() { return QUICK[this.S ? this.S.name : ""] || []; },
  quickTest(id, i) {
    const S = this.S, q = this.quickDefs().find(x => x.id === id);
    if (!q) return true;
    if (q.row) return this.lower(i).includes(q.row);
    if (q.col) {
      if (q._c === undefined || q._s !== S.name) { q._c = S.data.cols.findIndex(c => q.col.test(c.t)); q._s = S.name; }
      if (q._c < 0) return true;
      const v = S.val(i, q._c).toLowerCase();
      return q.eq ? v.trim() === q.eq : v.includes(q.has);
    }
    return true;
  },
  drawQuick() {
    const S = this.S, defs = this.quickDefs();
    $("#quickFilters").innerHTML = defs.length ? defs.map(q => `<button class="fchip${S && S.quick.includes(q.id) ? " on" : ""}" data-q="${q.id}" title="${esc(q.tip || "")}">${q.icon} ${esc(q.label)}</button>`).join("")
      : `<small style="color:var(--mute)">nessuno per questo foglio</small>`;
  },
  toggleQuick(id) {
    const S = this.S; if (!S) return;
    S.quick = S.quick.includes(id) ? S.quick.filter(x => x !== id) : [...S.quick, id];
    this.apply();
  },
  drawChips() {
    const S = this.S, bar = $("#chipbar");
    this.drawQuick();
    const chips = [];
    if (S.searchTerms.length) chips.push([`🔎 Ricerca: «${esc(S.search)}»`, "search"]);
    for (const q of S.quick) { const d = this.quickDefs().find(x => x.id === q); if (d) chips.push([`${d.icon} ${esc(d.label)}`, "q:" + q]); }
    for (const k in S.filters) {
      const f = S.filters[k], col = S.data.cols[k].t.replace(/\n/g, " ");
      let what = [];
      if (f.vals) { const v = [...f.vals]; what.push(v.slice(0, 2).map(x => "«" + esc((x || "(vuote)").slice(0, 30)) + "»").join(", ") + (v.length > 2 ? ` +${v.length - 2}` : "")); }
      if (f.text) what.push(`contiene «${esc(f.text)}»`);
      chips.push([`⧩ <b>${esc(col)}</b>: ${what.join(" e ")}`, "f:" + k]);
    }
    if (S.sort) chips.push([`${S.sort.dir > 0 ? "▲" : "▼"} Ordinato per <b>${esc(S.data.cols[S.sort.col].t)}</b>`, "sort"]);
    bar.hidden = !chips.length;
    bar.innerHTML = chips.map(([h, k]) => `<span class="achip">${h}<button data-rm="${k}" title="Rimuovi">✕</button></span>`).join("")
      + (chips.length > 1 ? `<button class="link" data-rm="all">✖ Rimuovi tutti i filtri</button>` : "");
  },
  removeChip(k) {
    const S = this.S; if (!S) return;
    if (k === "all") return this.clearAll();
    if (k === "search") { S.search = ""; $("#gSearch").value = ""; }
    else if (k === "sort") S.sort = null;
    else if (k.startsWith("q:")) S.quick = S.quick.filter(x => x !== k.slice(2));
    else if (k.startsWith("f:")) delete S.filters[k.slice(2)];
    this.apply();
  },

  setFilter(c, f) {
    const S = this.S;
    if (!f || (!f.vals && !f.text)) delete S.filters[c]; else S.filters[c] = f;
    this.apply();
  },

  filterPopup(c, x, y) {
    const S = this.S, col = S.data.cols[c];
    const counts = new Map();
    for (let i = 0; i < S.rows.length; i++) if (this.passes(i, c)) { const v = S.val(i, c); counts.set(v, (counts.get(v) || 0) + 1); }
    const values = [...counts.keys()].sort((a, b) => !a ? 1 : !b ? -1 : COLL.compare(a, b));
    const cur = S.filters[c] || {};
    const checked = new Set(cur.vals ? [...cur.vals] : values);
    const p = Popup.open(x, y, `
      <div class="ttl">${esc(col.t)}</div>
      <button class="mi" data-a="asc">↑ Ordina dalla A alla Z</button>
      <button class="mi" data-a="desc">↓ Ordina dalla Z alla A</button>
      <button class="mi" data-a="clr" ${S.filters[c] ? "" : "disabled"}>✖ Cancella filtro da «${esc(col.t)}»</button>
      <hr>
      <input type="text" class="ftext" placeholder="Filtro testo: contiene…" value="${esc(cur.text || "")}">
      <input type="search" class="fsearch" placeholder="Cerca nell'elenco valori">
      <label style="display:flex;gap:6px;font-weight:600"><input type="checkbox" class="fall"> (Seleziona tutto)</label>
      <div class="vals"></div>
      <div class="row"><span style="margin-right:auto;font-size:11px;color:#7b8496" class="vinfo"></span><button class="btn" data-a="cancel">Annulla</button><button class="btn primary" data-a="ok">OK</button></div>`, 330);
    const list = $(".vals", p), fs = $(".fsearch", p), all = $(".fall", p);
    let shown = [];
    const draw = () => {
      const q = fs.value.toLowerCase();
      shown = q ? values.filter(v => (v || "(vuote)").toLowerCase().includes(q)) : values;
      list.innerHTML = shown.slice(0, 1500).map((v, k) => `<label><input type="checkbox" data-k="${k}" ${checked.has(v) ? "checked" : ""}><span>${v ? esc(v.length > 140 ? v.slice(0, 140) + "…" : v) : "<i>(Vuote)</i>"}</span><small>${counts.get(v)}</small></label>`).join("");
      all.checked = shown.every(v => checked.has(v));
      $(".vinfo", p).textContent = `${values.length.toLocaleString("it")} valori` + (shown.length > 1500 ? " (primi 1500)" : "");
    };
    draw();
    fs.oninput = draw;
    list.onchange = e => { const v = shown[+e.target.dataset.k]; e.target.checked ? checked.add(v) : checked.delete(v); all.checked = shown.every(v => checked.has(v)); };
    all.onchange = () => { shown.forEach(v => all.checked ? checked.add(v) : checked.delete(v)); draw(); };
    p.onclick = e => {
      const a = e.target.dataset.a; if (!a) return;
      if (a === "asc" || a === "desc") { S.sort = {col: c, dir: a === "asc" ? 1 : -1}; Popup.close(); this.apply(); }
      else if (a === "clr") { Popup.close(); this.setFilter(c, null); }
      else if (a === "cancel") Popup.close();
      else if (a === "ok") {
        const text = $(".ftext", p).value.trim().toLowerCase();
        let vals = fs.value ? new Set(shown.filter(v => checked.has(v))) : checked;
        if (!fs.value && vals.size === values.length) vals = null;
        Popup.close();
        this.setFilter(c, {vals, text});
      }
    };
    $(".ftext", p).onkeydown = e => { if (e.key === "Enter") p.querySelector('[data-a="ok"]').click(); };
    setTimeout(() => fs.focus(), 10);
  },

  colsPopup(x, y, onlyCfg) {
    const S = this.S; if (!S) return;
    const cols = S.data.cols.map((c, i) => [c, i]).filter(([c]) => !onlyCfg || c.cfg);
    if (onlyCfg && !cols.length) { toast("Questo foglio non ha colonne di configurazione"); return; }
    const p = Popup.open(x, y, `<div class="ttl">${onlyCfg ? "Configurazioni visibili" : "Colonne visibili"}</div>
      <div class="row" style="justify-content:flex-start"><button class="btn small" data-a="all">Tutte</button><button class="btn small" data-a="none">Nessuna</button>${onlyCfg ? "" : `<label style="margin-left:auto;font-size:12px">Blocca prime <select class="frz">${[0, 1, 2, 3, 4, 5].map(k => `<option ${k === S.freeze ? "selected" : ""}>${k}</option>`).join("")}</select> col.</label>`}</div>
      <div class="vals">${cols.map(([c, i]) => `<label><input type="checkbox" data-i="${i}" ${S.hidden.has(i) ? "" : "checked"}>${c.cfg ? `<span class="cfgb" style="--cc:${cfgColor(c.t)}">${esc(c.t)}</span>` : `<span>${esc(c.t)}</span>`}</label>`).join("")}</div>
      <button class="btn small" data-a="reset">Ripristina larghezze e colonne</button>`, 300);
    p.onchange = e => {
      if (e.target.classList.contains("frz")) S.freeze = +e.target.value;
      else if (e.target.dataset.i) { const i = +e.target.dataset.i; e.target.checked ? S.hidden.delete(i) : S.hidden.add(i); }
      this.save(); this.render(true);
    };
    p.onclick = e => {
      const a = e.target.dataset.a; if (!a) return;
      if (a === "reset") { S.hidden.clear(); S.widths = S.data.cols.map(c => Math.min(c.w, 380)); S.freeze = S.data.freezeCols; Popup.close(); }
      else cols.forEach(([, i]) => a === "all" ? S.hidden.delete(i) : S.hidden.add(i));
      $$("input[data-i]", p).forEach(cb => cb.checked = !S.hidden.has(+cb.dataset.i));
      this.save(); this.render(true);
    };
  },

  exportCSV() {
    const S = this.S; if (!S) return;
    const vc = this.vcols();
    const q = v => /[";\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    const lines = [vc.map(c => q(S.data.cols[c].t)).join(";")];
    for (const i of S.order) lines.push(vc.map(c => q(S.val(i, c))).join(";"));
    const blob = new Blob(["\ufeff" + lines.join("\r\n")], {type: "text/csv;charset=utf-8"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${S.name.replace(/\W+/g, "_")}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    toast(`Esportate ${S.order.length} righe`, "ok");
  },
};
const colLetter = c => { let s = ""; c++; while (c) { const m = (c - 1) % 26; s = String.fromCharCode(65 + m) + s; c = (c - m - 1) / 26; } return s; };

// eventi griglia
Grid.el.addEventListener("scroll", () => requestAnimationFrame(() => Grid.render(false)), {passive: true});
window.addEventListener("resize", () => Grid.render(true));
Grid.inner.addEventListener("mousedown", e => {
  const S = Grid.S; if (!S) return;
  const rz = e.target.closest(".rz");
  if (rz) {
    e.preventDefault(); e.stopPropagation();
    const c = +rz.dataset.c, x0 = e.clientX, w0 = S.widths[c];
    const mv = ev => { S.widths[c] = Math.max(40, w0 + ev.clientX - x0); Grid.render(true); };
    const up = () => { document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up); Grid.save(); };
    document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up);
    return;
  }
  const fb = e.target.closest(".fb");
  if (fb) { e.stopPropagation(); const r = fb.getBoundingClientRect(); Grid.filterPopup(+fb.dataset.c, r.left - 280, r.bottom + 4); return; }
  const hc = e.target.closest(".hc");
  if (hc) {
    const c = +hc.dataset.c;
    S.sort = !S.sort || S.sort.col !== c ? {col: c, dir: 1} : S.sort.dir > 0 ? {col: c, dir: -1} : null;
    Grid.apply(); return;
  }
  const cell = e.target.closest(".c");
  if (cell) {
    const d = +cell.dataset.d, c = +cell.dataset.c;
    if (e.target.closest('a.lk[data-act="doc"]')) {
      const link = S.rows[S.order[d]].l[c];
      Grid.select(d, c); openDocLink(link, e); return;
    }
    if (e.target.closest("a.lk")) return;
    Grid.select(d, c, e.shiftKey);
    Grid.el.focus({preventScroll: true});
  }
});
Grid.inner.addEventListener("dblclick", e => {
  const S = Grid.S, cell = e.target.closest(".c"); if (!cell || !S) return;
  const i = S.order[+cell.dataset.d], c = +cell.dataset.c;
  Grid.setFilter(c, {vals: new Set([S.val(i, c)]), text: ""});
  toast(`Filtro: ${S.data.cols[c].t} = «${(S.val(i, c) || "(vuote)").slice(0, 60)}»`);
});
Grid.el.addEventListener("keydown", e => {
  const S = Grid.S; if (!S || !S.sel) return;
  const vc = Grid.vcols(); let {d, c} = S.sel; let k = vc.indexOf(c);
  const page = Math.floor(Grid.el.clientHeight / Grid.rh) - 2;
  const mv = {ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowRight: [0, 1], ArrowLeft: [0, -1], PageDown: [page, 0], PageUp: [-page, 0], Enter: [1, 0], Tab: [0, 1]}[e.key];
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "c") {
    const v = Grid.rangeValues().map(r => r.join("\t")).join("\r\n"); copyText(v); e.preventDefault(); return;
  }
  if (e.key === "Home") { k = 0; } else if (e.key === "End") { k = vc.length - 1; }
  else if (!mv) return;
  else { d = Math.max(0, Math.min(S.order.length - 1, d + mv[0])); k = Math.max(0, Math.min(vc.length - 1, k + mv[1])); }
  e.preventDefault();
  Grid.select(d, vc[k], e.shiftKey && e.key.startsWith("Arrow"));
  Grid.ensureVisible();
});
$("#detail").addEventListener("click", e => {
  const b = e.target.closest("[data-act]"); const S = Grid.S; if (!b || !S || !S.sel) return;
  const i = S.order[S.sel.d], c = S.sel.c, row = S.rows[i];
  const a = b.dataset.act;
  if (a === "doclink") openDocLink(row.l[c], e);
  else if (a === "copy") copyText(row.v[c]);
  else if (a === "filterv") Grid.setFilter(c, {vals: new Set([S.val(i, c)]), text: ""});
  else if (a === "only") { S.filters = {}; Grid.setFilter(0, {vals: new Set([b.dataset.f]), text: ""}); if (Grid.mode === "rows") setFilterMode("block"); }
  else if (a === "ask") { showView("ask"); Ask.prefill(`Come funziona la funzione ${b.dataset.f}?`); }
});
let searchT;
$("#gSearch").addEventListener("input", e => { clearTimeout(searchT); searchT = setTimeout(() => { if (Grid.S) { Grid.S.search = e.target.value.trim(); Grid.apply(); } }, 180); });
function setFilterMode(m) {
  Grid.mode = m; LS.set("filterMode", m);
  $$("#filterMode button").forEach(b => b.classList.toggle("on", b.dataset.m === m));
  Grid.apply();
}
$$("#filterMode button").forEach(b => b.classList.toggle("on", b.dataset.m === Grid.mode));
$("#filterMode").onclick = e => { const b = e.target.closest("button"); if (b) setFilterMode(b.dataset.m); };
$("#quickFilters").onclick = e => { const b = e.target.closest("[data-q]"); if (b) Grid.toggleQuick(b.dataset.q); };
$("#chipbar").onclick = e => { const b = e.target.closest("[data-rm]"); if (b) Grid.removeChip(b.dataset.rm); };
$("#rowH").value = String(Grid.rh);
$("#rowH").onchange = e => { Grid.rh = +e.target.value; LS.set("rowH", Grid.rh); Grid.render(true); };
$("#btnCsv").onclick = () => Grid.exportCSV();
$("#btnCols").onclick = e => { const r = e.target.getBoundingClientRect(); Grid.colsPopup(r.left, r.bottom + 4, false); };
$("#btnCfg").onclick = e => { const r = e.target.getBoundingClientRect(); Grid.colsPopup(r.left, r.bottom + 4, true); };
const detailOn = LS.get("detail", true);
$("#detail").classList.toggle("off", !detailOn); $("#btnDetail").classList.toggle("on", detailOn);
$("#btnDetail").onclick = () => { const on = $("#detail").classList.toggle("off"); $("#btnDetail").classList.toggle("on", !on); LS.set("detail", !on); Grid.render(true); };
$("#sheetTabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b) Grid.load(b.dataset.name); });
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f" && APP.view === "sheets") { e.preventDefault(); $("#gSearch").focus(); $("#gSearch").select(); }
});

function renderSheetTabs() {
  const m = APP.meta && APP.meta.meta;
  if (!m) return;
  $("#sheetTabs").innerHTML = m.sheets.map(s => `<button data-name="${esc(s.name)}" class="${s.name === APP.current ? "active" : ""}">${esc(s.name)}<small>${s.rows.toLocaleString("it")}</small></button>`).join("")
    + (m.missing.length ? `<span class="badge warn" title="Fogli non presenti nel file">Mancano: ${esc(m.missing.join(", "))}</span>` : "");
}

/* ════════════════════════════════════════════════════════════════════
   Componenti condivisi (Esplora + Chiedi)
   ════════════════════════════════════════════════════════════════════ */
const STATE_UI = {
  b: {icon: "★", cls: "st-b", label: "Riferimento (descrizione propria)"},
  g: {icon: "✔", cls: "st-g", label: "Simile alla base (≥ 90 %)"},
  o: {icon: "≈", cls: "st-o", label: "Differenze moderate"},
  r: {icon: "≠", cls: "st-r", label: "Differenze rilevanti"},
  l: {icon: "○", cls: "st-l", label: "Collegata, non ancora analizzata"},
  "": {icon: "–", cls: "st-n", label: "Non trattata"},
};
const pagesTxt = r => r.first ? (r.last && r.last !== r.first ? `pagg. ${r.first}–${r.last}` : `pag. ${r.first}`) : (r.page ? `pag. ${r.page}` : "");

/* Un solo pulsante principale per documento (+ icone secondarie) */
function refButtons(r, title) {
  if (!r) return "";
  const t = esc(title || `${r.doc} — ${(r.configs || [r.config]).join(", ")}`);
  const pg = r.first || r.page || 1;
  let h = "";
  if (r.fid) h += `<button class="btn primary small" data-pdf="${r.fid}" data-page="${pg}" data-title="${t}" title="Apri il PDF del computer alla pagina in cui è trattata la funzione">📄 Apri ${pagesTxt(r) ? "a " + pagesTxt(r) : ""}</button>`;
  else if (r.url) h += `<a class="btn primary small" href="${esc(r.url)}" target="_blank" rel="noopener" title="Il PDF non è sul computer: si apre SharePoint">🌐 Apri su SharePoint</a>`;
  if (r.fid && r.first && r.last && r.last > r.first) h += `<button class="btn icon small" data-pages="${r.fid}" data-first="${r.first}" data-last="${r.last}" data-title="${t} — ${pagesTxt(r)}" title="Sfoglia le pagine della funzione come immagini">🖼</button>`;
  if (r.fid && r.url) h += `<a class="btn icon small" href="${esc(r.url)}" target="_blank" rel="noopener" title="Apri su SharePoint">🌐</a>`;
  return h;
}

/* Elenco documenti compatto: configurazioni con lo stesso file/pagine raggruppate */
function docListHTML(items) {
  return `<div class="doclist">${items.map(d => `<div class="docrow">
    <div class="dl-ico">${d.local ? "📄" : "🌐"}</div>
    <div class="dl-main"><b>${esc(d.doc)}</b> <span class="code">${esc(d.code || "")}</span> <span class="pg">${pagesTxt(d)}</span>
      <div class="dl-cfgs">${(d.configs || [d.config]).map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`).join("")}${d.local ? "" : `<span class="badge warn" title="PDF non trovato nelle cartelle del computer">solo SharePoint</span>`}</div></div>
    <div class="dl-acts">${refButtons(d)}</div></div>`).join("")}</div>`;
}

/* Glossario appreso: evidenzia i termini noti con il loro significato */
let _glRe = null, _glMap = null, _glN = -1;
function glossify(html) {
  const g = APP.gloss || [];
  if (!g.length) return html;
  if (_glN !== g.length) {
    _glMap = new Map();
    g.forEach(t => [t.term, ...(t.aliases || [])].forEach(k => _glMap.set(k.toUpperCase(), t)));
    const keys = [..._glMap.keys()].sort((a, b) => b.length - a.length).map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    _glRe = keys.length ? new RegExp(`(^|[^\\w-])(${keys.join("|")})(?![\\w-])`, "gi") : null;
    _glN = g.length;
  }
  if (!_glRe) return html;
  return html.split(/(<[^>]+>)/).map(part => part.startsWith("<") ? part : part.replace(_glRe, (m, pre, w) => {
    const t = _glMap.get(w.toUpperCase());
    return t ? `${pre}<abbr class="gl" title="🧠 ${esc(t.term)}: ${esc(t.meaning)}">${w}</abbr>` : m;
  })).join("");
}
async function loadGlossary() {
  try { const k = await api("/api/knowledge"); APP.gloss = k.terms || []; APP.glossCats = k.categories || {}; } catch {}
}

/* Blocco "configurazione" (usato in Esplora e nelle risposte "tutte le configurazioni") */
function cfgCardHTML(k, base, opt = {}) {
  const st = STATE_UI[k.state || ""] || STATE_UI[""];
  const sim = k.sim != null ? Math.round(k.sim * 10) / 10 : null;
  let body;
  if (k.reference) {
    body = `<div class="ref-note">Variante di <b>${esc(base)}</b>${sim != null ? ` — similarità del testo <b>${sim}%</b>` : ""}.
      ${k.extra && k.extra.length ? "Le differenze sono descritte qui sotto." : "Il funzionamento è quello della configurazione di riferimento."}</div>`;
  } else if (k.text) body = `<div class="cc-text">${glossify(md(k.text))}</div>`;
  else body = `<div class="ref-note muted">Nessuna sintesi «Funzioni AI» per questa configurazione.</div>`;
  const extra = (k.extra || []).map(x => `<details class="cc-extra"${opt.openExtra ? " open" : ""}><summary>${/approf/i.test(x.label) ? "📝" : /component/i.test(x.label) ? "🔌" : "📐"} ${esc(x.label)} <small>${esc(x.doc)}</small></summary><div class="md">${glossify(md(x.text))}</div></details>`).join("");
  const trains = k.trains && k.trains.length ? `<details class="cc-trains"><summary title="Treni (veicoli) con questa configurazione, dal foglio Flotte">🚆 ${k.trains.length} treni${k.fleet ? " · " + esc(k.fleet) : ""}</summary><div>${k.trains.map(t => `<span class="tn">${esc(t)}</span>`).join("")}</div></details>` : "";
  const same = k.sameDoc && k.sameDoc.length ? `<div class="cc-same" title="Configurazioni che usano lo stesso documento e le stesse pagine">🔗 stesso documento di ${k.sameDoc.map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`).join(" ")}</div>` : "";
  const gauge = sim != null ? `<div class="gauge" title="Similarità con ${esc(base)}: ${sim}%"><i style="width:${Math.max(3, Math.min(100, sim))}%"></i></div>` : "";
  return `<div class="ccard ${st.cls}${k.base ? " isbase" : ""}" style="--cc:${cfgColor(k.config)}">
    <div class="cc-head"><span class="cfgb" style="--cc:${cfgColor(k.config)}">${esc(k.config)}</span>
      <span class="stchip ${st.cls}" title="${esc(st.label)}">${st.icon} ${k.base ? "Riferimento" : sim != null ? sim + "%" : esc(st.label.split(" (")[0])}</span></div>
    ${gauge}
    <div class="cc-doc">${k.ref ? `📄 ${esc(k.ref.doc)} <span class="code">${esc(k.ref.code || "")}</span> ${pagesTxt(k.ref)}` : `<span class="muted">Nessun documento collegato</span>`}${k.index ? ` · <span class="badge ${/^MATCHED/i.test(k.index) ? "ok" : /NOT/i.test(k.index) ? "bad" : ""}" title="Esito in Index Funzioni">${esc(k.index)}</span>` : ""}</div>
    ${same}${body}${extra}
    <div class="cc-foot">${trains}<span class="spacer"></span>${k.ref ? refButtons(k.ref, `${k.ref.doc} — ${k.config}`) : ""}</div></div>`;
}

/* Risultati della ricerca nei PDF, raggruppati per documento, con anteprima */
function searchHTML(groups, info) {
  if (!groups.length) return `<div class="tx info">Nessun documento contiene le parole cercate${info ? " (" + esc(info) + ")" : ""}.</div>`;
  return `<div class="sgroups">${groups.map(g => `<div class="sgroup${g.partial ? " partial" : ""}">
    <div class="sthumb" data-pdf="${g.fid}" data-page="${g.pages[0].page}" data-title="${esc(g.file)}" title="Apri alla pag. ${g.pages[0].page}"><img loading="lazy" decoding="async" src="/api/page.png?fid=${g.fid}&page=${g.pages[0].page}&dpi=45" alt=""></div>
    <div class="sbody"><div class="sfile">📄 <b>${esc(g.file)}</b> <small>${esc(g.folder)}</small>${g.partial ? ` <span class="badge" title="La pagina contiene solo alcune delle parole cercate">corrispondenza parziale</span>` : ""}</div>
      ${g.pages.map(p => `<div class="spage" data-pdf="${g.fid}" data-page="${p.page}" data-title="${esc(g.file)} — pag. ${p.page}"><span class="pgn">pag. ${p.page}</span><span class="snip">${esc(p.snippet).replace(/\[\[(.+?)\]\]/g, "<mark>$1</mark>")}</span></div>`).join("")}
    </div></div>`).join("")}</div>`;
}

/* ════════════════════════════════════════════════════════════════════
   CHIEDI
   ════════════════════════════════════════════════════════════════════ */
const Ask = {
  ready: false, busy: false, acSel: 0, acItems: [],
  async init() {
    if (!APP.gloss.length) loadGlossary();
    if (this.ready) return;
    try {
      const s = await api("/api/suggestions");
      if (!s.items.length && !s.functions.length) return;
      this.ready = true;
      APP.functions = s.functions; APP.configs = s.configs; Object.assign(APP.colors, s.colors || {});
      $("#sugList").innerHTML = s.items.map(q => `<button>${esc(q)}</button>`).join("");
    } catch (e) { toast(e.message, "bad"); }
    this.drawHist();
    this.syncAi();
  },
  syncAi() {
    const ok = APP.meta && APP.meta.ai && APP.meta.ai.ok;
    $("#optAi").disabled = !ok;
    $("#optAi").checked = ok && LS.get("autoAi", false);
    $("#optAiLbl").title = ok ? "Genera automaticamente una spiegazione con l'AI locale" : "AI locale non disponibile: " + (APP.meta && APP.meta.ai ? APP.meta.ai.msg : "");
    $("#optDocs").checked = LS.get("searchDocs", false);
  },
  prefill(q) { this.setMode("ask"); $("#q").value = q; $("#q").focus(); },
  mode: "ask", sT: null, sSeq: 0,
  setMode(m) {
    this.mode = m;
    $$("#askMode button").forEach(b => b.classList.toggle("on", b.dataset.m === m));
    $("#thread").hidden = m === "search";
    $("#searchPane").hidden = m !== "search";
    $(".askopts").hidden = m === "search";
    $("#q").placeholder = m === "search" ? "Scrivi le parole da cercare nei PDF (es. hotbox Pt100, \"line voltage\", HABD)… i risultati compaiono mentre scrivi"
      : "Es. Come funziona la funzione BOG_Hotbox_Detection nella configurazione VZI_Base?";
    if (m === "search") { this.closeAc(); this.liveSearch(); if (!$("#searchPane").innerHTML) $("#searchPane").innerHTML = `<div class="welcome"><h2>🔎 Ricerca nei documenti del computer</h2><p>Scrivi una o più parole (in inglese, come nei documenti). Vengono mostrate prima le pagine che contengono <b>tutte</b> le parole; usa le virgolette per una frase esatta. Clic su un risultato per aprire il PDF alla pagina.</p></div>`; }
    $("#q").focus();
  },
  liveSearch() {
    clearTimeout(this.sT);
    const q = $("#q").value.trim();
    if (!q) return;
    this.sT = setTimeout(async () => {
      const seq = ++this.sSeq;
      let r;
      try { r = await api("/api/search?q=" + encodeURIComponent(q)); } catch (e) { $("#searchPane").innerHTML = `<div class="tx bad">${esc(e.message)}</div>`; return; }
      if (seq !== this.sSeq) return;
      const st = r.stats || {};
      const head = `<div class="shead"><b>${r.groups.length}</b> documenti · ${r.hits} pagine · ⚡ ${r.ms} ms <span class="muted">· ${st.indexed_files || 0} PDF indicizzati${st.running ? ` (indicizzazione in corso ${st.done}/${st.total})` : ""}</span></div>`;
      $("#searchPane").innerHTML = head + searchHTML(r.groups, [r.phrase && `"${r.phrase}"`, ...(r.terms || [])].filter(Boolean).join(" "));
    }, 220);
  },
  drawHist() {
    const h = LS.get("hist", []);
    $("#histList").innerHTML = h.length ? h.map(q => `<button>${esc(q)}</button>`).join("") : "<small style='color:#7b8496'>Nessuna domanda</small>";
  },
  remember(q) {
    const h = LS.get("hist", []).filter(x => x !== q); h.unshift(q); LS.set("hist", h.slice(0, 25)); this.drawHist();
  },
  async send(q) {
    q = (q || "").trim();
    if (!q || this.busy) return;
    this.busy = true;
    $("#welcome") && $("#welcome").remove();
    $("#q").value = ""; this.closeAc();
    this.remember(q);
    const th = $("#thread");
    th.insertAdjacentHTML("beforeend", `<div class="q-bubble">${esc(q)}</div>`);
    const box = document.createElement("div");
    box.className = "ans";
    box.innerHTML = `<div class="typing"><i></i><i></i><i></i></div>`;
    th.appendChild(box);
    box.scrollIntoView({behavior: "smooth", block: "start"});
    try {
      const res = await api("/api/ask", {json: {q, docs: $("#optDocs").checked}});
      this.renderAnswer(box, res, q);
      if (res.ai && res.aiAvailable && $("#optAi").checked) this.streamAi(box, res.id);
    } catch (e) {
      box.innerHTML = `<div class="tx bad">${esc(e.message)}</div>`;
    } finally { this.busy = false; }
  },
  renderAnswer(box, res, q) {
    let h = `<div class="meta"><span class="badge info">${esc({differences: "Differenze", explain: "Funzionamento", components: "Componenti", documents: "Documenti", figures: "Figure e tabelle", requirements: "Requisiti", overview: "Panoramica"}[res.intent] || res.intent)}</span>`;
    if (res.allConfigs) h += `<span class="badge ok" title="La domanda chiede tutte le configurazioni">🚆 tutte le configurazioni</span>`;
    (res.configs || []).forEach(c => h += `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`);
    h += `<span class="spacer"></span><span title="Tempo di risposta">⚡ ${res.cached ? "dalla cache" : res.ms + " ms"}</span></div>`;
    if (res.notes && res.notes.length) h += `<div class="notes">Interpretazione: ${res.notes.map(esc).join(" · ")}</div>`;
    h += (res.blocks || []).map(b => this.block(b, q)).join("");
    if (res.followups && res.followups.length) h += `<div class="follow"><span>💡 Potresti chiedere anche:</span>${[...new Set(res.followups)].slice(0, 4).map(f => `<button class="chip" data-q="${esc(f)}">${esc(f)}</button>`).join("")}</div>`;
    if (res.ai) {
      h += res.aiAvailable
        ? `<div><button class="btn" data-ai="${esc(res.id)}">✨ Spiegazione discorsiva con l'AI locale</button></div>`
        : `<div class="tx info" style="font-size:12px">💡 Con l'AI locale (Ollama) installata potresti ottenere anche una spiegazione discorsiva: vedi la <a href="#guide" onclick="showView('guide')">Guida</a>.</div>`;
    }
    box.innerHTML = h;
    box._res = res;
    $$(".tbl", box).forEach(t => this.bindTable(t));
  },
  block(b, q) {
    const T = b.title ? `<div class="blk-title">${esc(b.title)}</div>` : "";
    switch (b.type) {
      case "title": return `<h3>${esc(b.text)}${b.sub ? `<small>${esc(b.sub)}</small>` : ""}</h3>`;
      case "text": return `<div class="tx md ${b.tone || ""}">${glossify(md(b.md))}</div>`;
      case "stats": return `<div class="stats">${b.items.map(s => `<div class="stat ${s.tone || ""}"><b>${esc(s.value)}</b><span>${esc(s.label)}</span></div>`).join("")}</div>`;
      case "chips": return `<div class="chips">${b.items.map(c => `<button class="chip" data-q="${esc(q + " (" + c.fid + ")")}"><b>${esc(c.label)}</b>${c.desc ? `<small>${esc(c.desc)}</small>` : ""}</button>`).join("")}</div>`;
      case "table": return this.table(b);
      case "cards": return `<div>${T}<div class="cards">${b.items.map(c => this.card(c)).join("")}</div></div>`;
      case "figures": return `<div>${T}<div class="figs">${b.items.map(f => this.fig(f)).join("")}</div></div>`;
      case "docs": return `<div>${T}${docListHTML(b.items)}</div>`;
      case "search": return `<div>${T}${searchHTML(b.groups)}</div>`;
      case "cfgblocks": {
        const tr = b.items.reduce((n, k) => n + (k.trains || []).length, 0);
        return `<div class="cfgblocks"><div class="blk-title">🚆 Configurazioni coinvolte: ${b.items.length}${tr ? ` · ${tr} treni` : ""}
          <span class="legend">${["b", "g", "o", "r"].map(x => `<span class="stchip ${STATE_UI[x].cls}">${STATE_UI[x].icon} ${STATE_UI[x].label}</span>`).join("")}</span></div>
          <div class="ccgrid">${b.items.map(k => cfgCardHTML(k, b.base)).join("")}</div></div>`;
      }
      case "hits": return `<div>${T}<div class="hits">${b.items.map(x => `<div class="hit" data-fid="${esc(x.fid)}" data-page="${x.page}" data-title="${esc(x.file)}"><div class="f">📄 ${esc(x.file)} · pag. ${x.page}</div><div class="s">${esc(x.snippet).replace(/\[\[(.+?)\]\]/g, "<mark>$1</mark>")}</div></div>`).join("")}</div></div>`;
      default: return "";
    }
  },
  table(b) {
    const cc = b.colors || {};
    const n = b.rows.length, max = b.maxRows || 0;
    const body = b.rows.map((r, k) => `<tr${max && k >= max ? " hidden data-x" : ""}>${r.map((v, j) => `<td>${cc[j] === "config" && v ? `<span class="cfgb" style="--cc:${cfgColor(v)}">${esc(v)}</span>` : mdInline(String(v ?? ""))}</td>`).join("")}</tr>`).join("");
    const inner = `${n > 8 ? `<div class="tools"><input type="search" placeholder="Filtra le ${n} righe…"><button class="btn small" data-csv>⧉ Copia</button></div>` : ""}
      <div class="scroll"><table><thead><tr>${b.columns.map((c, j) => `<th data-j="${j}">${esc(c)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>
      ${max && n > max ? `<div class="more"><button class="btn small" data-more>Mostra tutte le ${n} righe</button></div>` : ""}`;
    const title = esc(b.title || "Tabella") + ` <span class="badge">${n}</span>`;
    return `<div class="tbl"><details ${b.collapsed ? "" : "open"}><summary>${title}</summary>${inner}</details></div>`;
  },
  bindTable(t) {
    const inp = $("input", t), tb = $("tbody", t);
    if (inp) inp.oninput = () => { const q = inp.value.toLowerCase(); $$("tr", tb).forEach(tr => tr.hidden = q ? !tr.textContent.toLowerCase().includes(q) : tr.hasAttribute("data-x")); };
    t.addEventListener("click", e => {
      if (e.target.dataset.more !== undefined) { $$("tr", tb).forEach(tr => { tr.hidden = false; tr.removeAttribute("data-x"); }); e.target.parentElement.remove(); }
      if (e.target.dataset.csv !== undefined) copyText([...$$("tr", t)].filter(r => !r.hidden).map(r => [...r.children].map(c => c.textContent).join("\t")).join("\n"));
      const th = e.target.closest("th");
      if (th) {
        const j = +th.dataset.j, dir = th.dataset.dir === "1" ? -1 : 1;
        $$("th", t).forEach(x => delete x.dataset.dir); th.dataset.dir = dir === 1 ? "1" : "-1";
        [...tb.rows].sort((a, b) => COLL.compare(a.cells[j].textContent, b.cells[j].textContent) * dir).forEach(r => tb.appendChild(r));
      }
    });
  },
  card(c) {
    const pages = c.first ? (c.last && c.last !== c.first ? `pagg. ${c.first}–${c.last}` : `pag. ${c.first}`) : "pagina non indicata";
    let a = "";
    if (c.fid) {
      a += `<button class="btn primary small" data-pdf="${c.fid}" data-page="${c.first || c.page || 1}" data-title="${esc(c.doc + " — " + c.config)}">📄 Apri alla ${c.first ? "pag. " + (c.first || c.page) : "prima pagina"}</button>`;
      if (c.first) a += `<button class="btn small" data-pages="${c.fid}" data-first="${c.first}" data-last="${c.last || c.first}" data-title="${esc(c.doc + " — " + c.config + " — " + pages)}">🖼 Pagine della funzione</button>`;
    }
    if (c.url) a += `<a class="btn small" href="${esc(c.url)}" target="_blank" rel="noopener">🌐 SharePoint</a>`;
    return `<div class="dcard" style="--cc:${cfgColor(c.config)}"><span class="cfgb" style="--cc:${cfgColor(c.config)}">${esc(c.config)}</span>
      <div class="t">${esc(c.doc)}</div><div class="s">${esc(c.code || "")} · ${pages}</div>
      <div class="s">${c.local ? "✅ Presente sul PC: " + esc(c.file) : "⚠️ Non trovato sul PC (solo SharePoint)"}</div><div class="acts">${a}</div></div>`;
  },
  fig(f) {
    const bbox = f.bbox ? f.bbox.map(x => Math.round(x)).join(",") : "";
    const src = `/api/page.png?fid=${f.fid}&page=${f.page}${bbox ? "&bbox=" + bbox : ""}&dpi=90`;
    const big = src.replace("dpi=90", "dpi=200");
    let rows = "";
    if (f.rows && f.rows.length) rows = `<details><summary style="cursor:pointer;font-size:12px">Dati della tabella (${f.rows.length} righe)</summary><div class="tbl" style="margin-top:5px"><div class="scroll" style="max-height:240px"><table><tbody>${f.rows.map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div></details>`;
    return `<div class="fig"><div class="img" data-img="${esc(src)}" data-big="${esc(big)}" data-title="${esc(f.caption)}"><img decoding="async" src="${esc(src)}" alt="${esc(f.caption)}"></div>
      <div class="cap"><div><span class="badge ${f.kind === "table" ? "info" : "ok"}">${f.kind === "table" ? "Tabella" : "Figura"}</span> pag. ${f.page}</div><div>${esc(f.caption)}</div>${rows}
      <div><button class="btn small" data-pdf="${f.fid}" data-page="${f.page}" data-title="${esc(f.caption)}">📄 Apri la pagina</button></div></div></div>`;
  },
  async streamAi(box, id) {
    const btn = $(`[data-ai]`, box); if (btn) btn.parentElement.remove();
    const ai = document.createElement("div");
    ai.className = "aibox";
    ai.innerHTML = `<div class="h">✨ Spiegazione dell'AI locale <span class="badge">${esc(APP.meta.ai.msg.replace("Ollama attivo, modello ", ""))}</span></div><div class="md cursor"></div>`;
    box.appendChild(ai);
    const out = $(".md", ai);
    let txt = "";
    try {
      const r = await fetch(`/api/ask/ai/${id}`);
      const rd = r.body.getReader(), dec = new TextDecoder();
      let last = 0;
      for (;;) {
        const {value, done} = await rd.read();
        if (done) break;
        txt += dec.decode(value, {stream: true});
        if (performance.now() - last > 80) { out.innerHTML = md(txt); last = performance.now(); }
      }
    } catch (e) { txt += `\n\n[Errore: ${e.message}]`; }
    out.innerHTML = md(txt) + `<p style="font-size:11px;color:#7b8496">Testo generato dall'AI a partire dai dati del file e dei documenti: verificare sempre sulle fonti.</p>`;
    out.classList.remove("cursor");
  },
  // autocompletamento FUNC ID
  token() {
    const ta = $("#q"), pos = ta.selectionStart, txt = ta.value.slice(0, pos);
    const m = txt.match(/[\w\-]{3,}$/);
    return m ? {word: m[0], start: pos - m[0].length, end: pos} : null;
  },
  updateAc() {
    const t = this.token();
    if (!t || !APP.functions.length) return this.closeAc();
    const w = t.word.toLowerCase();
    const items = APP.functions.filter(([f]) => f.toLowerCase().includes(w)).slice(0, 12);
    if (!items.length || (items.length === 1 && items[0][0] === t.word)) return this.closeAc();
    this.acItems = items; this.acSel = 0; this.acTok = t;
    const ac = $("#ac");
    ac.innerHTML = items.map(([f, d], k) => `<div data-k="${k}" class="${k ? "" : "on"}"><b>${esc(f)}</b><small>${esc(d)}</small></div>`).join("");
    ac.hidden = false;
  },
  closeAc() { $("#ac").hidden = true; this.acItems = []; },
  pickAc(k) {
    const f = this.acItems[k][0], t = this.acTok, ta = $("#q");
    ta.value = ta.value.slice(0, t.start) + f + " " + ta.value.slice(t.end);
    ta.selectionStart = ta.selectionEnd = t.start + f.length + 1;
    this.closeAc(); ta.focus();
  },
};
$("#askForm").addEventListener("submit", e => { e.preventDefault(); Ask.mode === "search" ? Ask.liveSearch() : Ask.send($("#q").value); });
$("#q").addEventListener("input", () => Ask.mode === "search" ? Ask.liveSearch() : Ask.updateAc());
$("#askMode").onclick = e => { const b = e.target.closest("button"); if (b) Ask.setMode(b.dataset.m); };
$("#searchPane").addEventListener("click", e => { const t = e.target.closest("[data-pdf]"); if (t) Modal.pdf(t.dataset.pdf, +t.dataset.page, t.dataset.title); });
$("#q").addEventListener("keydown", e => {
  if (Ask.acItems.length) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      Ask.acSel = (Ask.acSel + (e.key === "ArrowDown" ? 1 : -1) + Ask.acItems.length) % Ask.acItems.length;
      $$("#ac div").forEach((d, k) => d.classList.toggle("on", k === Ask.acSel)); return;
    }
    if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) { e.preventDefault(); Ask.pickAc(Ask.acSel); return; }
    if (e.key === "Escape") { Ask.closeAc(); return; }
  }
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); Ask.mode === "search" ? Ask.liveSearch() : Ask.send($("#q").value); }
});
$("#ac").addEventListener("mousedown", e => { const d = e.target.closest("[data-k]"); if (d) { e.preventDefault(); Ask.pickAc(+d.dataset.k); } });
$("#q").addEventListener("blur", () => setTimeout(() => Ask.closeAc(), 150));
$("#sugList").addEventListener("click", e => { const b = e.target.closest("button"); if (b) Ask.send(b.textContent); });
$("#histList").addEventListener("click", e => { const b = e.target.closest("button"); if (b) Ask.send(b.textContent); });
$("#clearHist").onclick = () => { LS.set("hist", []); Ask.drawHist(); };
$("#optAi").onchange = e => LS.set("autoAi", e.target.checked);
$("#optDocs").onchange = e => LS.set("searchDocs", e.target.checked);
$("#thread").addEventListener("click", e => {
  const t = e.target;
  const pdf = t.closest("[data-pdf]"); if (pdf) return Modal.pdf(pdf.dataset.pdf, +pdf.dataset.page, pdf.dataset.title);
  const pg = t.closest("[data-pages]"); if (pg) return Modal.pages(pg.dataset.pages, +pg.dataset.first, +pg.dataset.last, pg.dataset.title);
  const im = t.closest("[data-img]"); if (im) return Modal.img(im.dataset.img, im.dataset.title, im.dataset.big);
  const hit = t.closest(".hit"); if (hit) return Modal.pdf(hit.dataset.fid, +hit.dataset.page, hit.dataset.title);
  const chip = t.closest(".chip"); if (chip) return Ask.send(chip.dataset.q);
  const ai = t.closest("[data-ai]"); if (ai) return Ask.streamAi(ai.closest(".ans"), ai.dataset.ai);
});

/* ════════════════════════════════════════════════════════════════════
   STRUMENTI (riservato)
   ════════════════════════════════════════════════════════════════════ */
const Tools = {
  pr: null, opts: null, mode: null, logN: 0, timer: null, frs: null, cfgItems: [],
  async open(force) {
    const box = $("#prereq");
    if (!this.pr || force) box.innerHTML = `<span class="spin"></span> Verifica dei prerequisiti…`;
    try { this.pr = await api("/api/tools/prereq" + (force ? "?force=1" : "")); }
    catch (e) { box.innerHTML = `<div class="tx bad">${esc(e.message)}</div>`; return; }
    this.renderPrereq();
    $("#toolsLock").textContent = this.pr.ok ? "🔓" : "🔒";
    $("#toolsBody").hidden = !this.pr.ok;
    if (this.pr.ok) { await this.loadOptions(); this.poll(); }
  },
  renderPrereq() {
    const pr = this.pr, box = $("#prereq");
    const checks = pr.checks.map(c => `<div class="chk ${c.ok ? "ok" : "ko"}"><span class="ic">${c.ok ? "✅" : "❌"}</span>
      <div><b>${esc(c.label)}</b><div class="d">${esc(c.detail)}</div></div>
      ${c.ok ? "" : `<div class="fix"><code>${esc(c.fix)}</code><button class="btn small" data-copy="${esc(c.fix)}">⧉</button></div>`}</div>`).join("");
    if (pr.ok) {
      box.innerHTML = `<details><summary style="cursor:pointer"><b>✅ Ambiente pronto</b> — tutti i prerequisiti sono installati: puoi lanciare le opzioni e modificare CONFIG. <button class="btn small" data-recheck>↻ Ricontrolla</button></summary><div class="checks">${checks}</div></details>`;
      return;
    }
    box.innerHTML = `<h2 style="margin-top:0">🔒 Sezione riservata: completa l'installazione</h2>
      <p>Il lancio delle opzioni del programma e la sezione CONFIG richiedono che sul PC siano installati Python, i pacchetti del programma, <b>Ollama</b> con il modello AI e che i percorsi del file Excel e dei documenti siano corretti. Segui i passi; poi premi <b>Ricontrolla</b>.</p>
      <ol class="steps">
        <li><b>Python 3.10+</b>: scaricalo da <a href="https://www.python.org/downloads/" target="_blank" rel="noopener">python.org</a> e durante l'installazione spunta «Add python.exe to PATH».</li>
        <li><b>Pacchetti del programma</b>: apri il Prompt dei comandi nella cartella del programma (<code>${esc(pr.program_dir)}</code>) ed esegui <code>python -m pip install -r requirements.txt</code>.</li>
        <li><b>Ollama</b>: scaricalo da <a href="https://ollama.com/download" target="_blank" rel="noopener">ollama.com/download</a>, installalo e avvialo (icona del lama nella barra di sistema).</li>
        <li><b>Modello AI</b>: nel Prompt dei comandi esegui il comando indicato sotto (<code>ollama pull …</code>); il download richiede alcuni GB.</li>
        <li><b>Percorsi</b>: indica qui sotto dove si trovano il file Excel e la cartella documenti sincronizzata con OneDrive.</li>
      </ol>
      <div class="checks">${checks}</div>
      <div class="row" style="display:flex;gap:8px"><button class="btn primary" data-recheck>↻ Ricontrolla</button><a class="btn" href="#guide" onclick="showView('guide')">❔ Guida completa</a></div>
      <h3>Percorsi e modello</h3><div id="setupCfg"></div>`;
    this.loadConfig($("#setupCfg"), true);
  },
  async loadOptions() {
    if (!this.opts) {
      this.opts = await api("/api/tools/options");
      $("#optGrid").innerHTML = this.opts.options.map(o => `<button class="opt" data-mode="${o.mode}"><span class="n">${o.mode}</span><b>${esc(o.title)}</b><span>${esc(o.desc)}</span></button>`).join("");
    }
  },
  async form(mode) {
    this.mode = mode;
    $$(".opt").forEach(b => b.classList.toggle("active", b.dataset.mode === mode));
    const o = this.opts.options.find(x => x.mode === mode), P = new Set(o.params);
    if ((P.has("frs") || P.has("doc")) && !this.frs) {
      try { this.frs = (await api("/api/tools/frs")).items; } catch { this.frs = []; }
    }
    const cfgs = this.opts.configs || [];
    let h = `<h3 style="margin:0">Opzione ${o.mode} — ${esc(o.title)}</h3><p style="color:#4b5568;margin:4px 0">${esc(o.desc)}</p><div class="form">`;
    if (P.has("frs")) h += `<label class="l">FRS da elaborare</label><div><input type="search" id="frsFilter" placeholder="Filtra…" style="width:260px;margin-bottom:6px"><div class="multi" id="fFrs">${this.frs.map(f => `<label><input type="checkbox" value="${esc(f)}">${esc(f)}</label>`).join("")}</div><div class="h">Nessuna selezione = tutti i documenti.</div></div>`;
    if (P.has("doc")) h += `<label class="l">DOC ID da confrontare</label><div><input type="text" id="fDoc" list="dlDoc" placeholder="es. FRS_Coupler, FRS_Bogies" style="width:100%"><datalist id="dlDoc">${(this.frs || []).map(f => `<option value="${esc(f)}">`).join("")}</datalist><div class="h">Separati da virgola.</div></div>`;
    if (P.has("start")) h += `<label class="l">Inizia dal FUNC ID</label><div><input type="text" id="fStart" list="dlFn" placeholder="(dall'inizio)" style="width:100%"><datalist id="dlFn">${this.opts.functions.map(f => `<option value="${esc(f)}">`).join("")}</datalist></div>`;
    if (P.has("configs")) h += `<label class="l">Configurazioni da confrontare</label><div><div class="multi" id="fCfg">${cfgs.map(c => `<label><input type="checkbox" value="${esc(c)}" checked><span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span></label>`).join("")}</div><div class="h">Almeno due. Tutte selezionate = confronto completo.</div></div>`;
    if (P.has("max_cells")) h += `<label class="l">Numero massimo di celle</label><div><input type="number" id="fMax" min="0" value="0" style="width:120px"><div class="h">0 = tutte (valore di config: MAX_CELLS_PER_RUN).</div></div>`;
    if (P.has("overwrite")) h += `<label class="l">Celle già compilate</label><div><select id="fOver"><option value="A">A — automatico: rielabora solo se il documento è cambiato</option><option value="N">N — solo le celle vuote</option><option value="S">S — rielabora tutte</option></select></div>`;
    if (P.has("no_rnm")) h += `<label class="l">Reqs not matched</label><label><input type="checkbox" id="fNoRnm"> Non aggiornare il foglio «Reqs not matched» al termine</label>`;
    if (P.has("results_only")) h += `<label class="l">Salvataggio</label><div><label><input type="checkbox" id="fRes"> Non modificare il DB Flotte: scrivi i risultati in <code>RESULTS/RESULTS_&lt;data&gt;_Opzione_${o.mode}.xlsx</code></label><div class="h">Senza questa spunta il file Excel viene aggiornato (la versione precedente è archiviata in _OLD) e questa pagina si ricarica automaticamente al termine.</div></div>`;
    h += `</div><div style="display:flex;gap:8px;margin-top:14px"><button class="btn primary" id="btnRun">▶ Avvia opzione ${o.mode}</button><span class="h" id="runHint" style="align-self:center;color:#7b8496"></span></div>`;
    $("#runForm").innerHTML = h; $("#runForm").hidden = false;
    const ff = $("#frsFilter");
    if (ff) ff.oninput = () => $$("#fFrs label").forEach(l => l.hidden = !l.textContent.toLowerCase().includes(ff.value.toLowerCase()));
    $("#btnRun").onclick = () => this.run();
    this.syncRunBtn();
  },
  async run() {
    const p = {mode: this.mode};
    const v = id => { const el = $(id); return el ? el.value : ""; };
    const checked = id => $$(`${id} input:checked`).map(x => x.value);
    if ($("#fFrs")) p.frs = checked("#fFrs");
    if ($("#fDoc")) { p.doc = v("#fDoc"); if (!p.doc.trim()) return toast("Indica almeno un DOC ID", "bad"); }
    if ($("#fStart")) p.start = v("#fStart");
    if ($("#fCfg")) { p.configs = checked("#fCfg"); if (p.configs.length < 2) return toast("Seleziona almeno due configurazioni", "bad"); if (p.configs.length === $$("#fCfg input").length) p.configs = []; }
    if ($("#fMax")) p.max_cells = +v("#fMax") || 0;
    if ($("#fOver")) p.overwrite = v("#fOver");
    if ($("#fNoRnm")) p.no_rnm = $("#fNoRnm").checked;
    if ($("#fRes")) p.results_only = $("#fRes").checked;
    if (!p.results_only && !confirm(`L'opzione ${this.mode} aggiornerà il file Excel (la versione precedente viene archiviata in _OLD).\nChiudere il file in Excel prima di continuare.\n\nAvviare?`)) return;
    try {
      await api("/api/tools/run", {json: p});
      $("#console").innerHTML = ""; this.logN = 0;
      toast(`Opzione ${this.mode} avviata`, "ok");
      this.poll();
    } catch (e) { toast(e.message, "bad", 7000); }
  },
  syncRunBtn(job) {
    const running = job ? job.running : (this.job && this.job.running);
    const b = $("#btnRun"); if (b) b.disabled = !!running;
    const hint = $("#runHint"); if (hint) hint.textContent = running ? "Un'opzione è già in esecuzione." : "";
  },
  async poll() {
    clearTimeout(this.timer);
    if (APP.view !== "tools" || !this.pr || !this.pr.ok) return;
    try {
      const r = await api(`/api/tools/log?since=${this.logN}`);
      const con = $("#console");
      const atBottom = con.scrollHeight - con.scrollTop - con.clientHeight < 40;
      if (r.next < this.logN) { con.innerHTML = ""; }
      if (r.lines.length) {
        con.insertAdjacentHTML("beforeend", r.lines.map(l => {
          const cls = /error|errore|traceback|exception/i.test(l) ? "e" : /warn|attenzione|⚠/i.test(l) ? "w" : /✓|complet|salvat/i.test(l) ? "o" : "";
          return `<span class="${cls}">${esc(l)}</span>\n`;
        }).join(""));
        if (atBottom) con.scrollTop = con.scrollHeight;
      }
      this.logN = r.next;
      const job = r.job;
      const prev = this.job;
      this.job = job;
      const st = $("#jobState");
      if (!job) { st.className = "badge"; st.textContent = "nessuna"; }
      else if (job.running) { st.className = "badge warn"; st.innerHTML = `<span class="spin"></span> opzione ${job.mode} in esecuzione · ${Math.round(Date.now() / 1000 - job.started)} s`; }
      else { st.className = "badge " + (job.code === 0 ? "ok" : "bad"); st.textContent = `opzione ${job.mode}: ${job.code === 0 ? "completata" : job.code === 130 ? "interrotta" : "errore " + job.code}`; }
      $("#btnStop").hidden = !(job && job.running);
      this.syncRunBtn(job);
      if (prev && prev.running && job && !job.running) toast(job.code === 0 ? `Opzione ${job.mode} completata: ricarico il file Excel` : `Opzione ${job.mode} terminata (codice ${job.code})`, job.code === 0 ? "ok" : "bad", 7000);
      this.timer = setTimeout(() => this.poll(), job && job.running ? 800 : 4000);
    } catch { this.timer = setTimeout(() => this.poll(), 5000); }
  },
  async loadConfig(target, setup) {
    target = target || $("#sub-config");
    target.innerHTML = `<span class="spin"></span> Lettura di config.py…`;
    let res;
    try { res = await api("/api/tools/config"); } catch (e) { target.innerHTML = `<div class="tx bad">${esc(e.message)}</div>`; return; }
    this.cfgItems = res.items;
    const nOv = res.items.filter(i => i.overridden).length;
    let h = "";
    if (!setup) h += `<div class="card"><div class="cfgtop"><input type="search" id="cfgSearch" placeholder="Cerca variabile o descrizione…"><label><input type="checkbox" id="cfgOnlyOv"> Solo valori forzati</label>
      <span class="badge ${nOv ? "warn" : ""}">${nOv} valori forzati</span><button class="btn danger" id="cfgResetAll" ${nOv ? "" : "disabled"}>Ripristina tutti</button></div>
      <p style="font-size:12px;color:#4b5568;margin:8px 0 0">I valori forzati sono salvati in <code>${esc(res.overrides_file)}</code> e sostituiscono quelli di <code>${esc(res.file)}</code> (che non viene modificato). Valgono per le prossime esecuzioni delle opzioni e per questa pagina.</p></div>`;
    const secs = new Map();
    res.items.forEach(i => { const s = i.section || "Altro"; if (!secs.has(s)) secs.set(s, []); secs.get(s).push(i); });
    for (const [s, items] of secs) {
      const ov = items.filter(i => i.overridden).length;
      h += `<details class="cfgsec" ${setup ? "open" : ""}><summary>${esc(s)}<span class="badge ${ov ? "warn" : ""}">${items.length} variabili${ov ? ` · ${ov} forzate` : ""}</span></summary>${items.map(i => this.cvar(i)).join("")}</details>`;
    }
    target.innerHTML = h;
    target.onclick = e => this.cfgClick(e, target, setup);
    target.onchange = e => { if (e.target.dataset.bool) this.saveVar(e.target.dataset.bool, e.target.checked, target, setup); };
    const cs = $("#cfgSearch", target), oo = $("#cfgOnlyOv", target);
    const filt = () => {
      const q = (cs ? cs.value : "").toLowerCase(), only = oo && oo.checked;
      $$(".cfgsec", target).forEach(sec => {
        let any = 0;
        $$(".cvar", sec).forEach(v => { const ok = (!q || v.dataset.s.includes(q)) && (!only || v.classList.contains("ov")); v.hidden = !ok; any += ok; });
        sec.hidden = !any; if ((q || only) && any) sec.open = true;
      });
    };
    if (cs) cs.oninput = filt; if (oo) oo.onchange = filt;
  },
  cvar(i) {
    const val = i.value, k = i.kind;
    const show = v => k === "json" || k === "none" ? JSON.stringify(v) : String(v ?? "");
    let ed;
    if (k === "bool") ed = `<label class="switch"><input type="checkbox" data-bool="${i.name}" ${val ? "checked" : ""}><span></span></label><span style="font-size:12px;padding-top:3px">${val ? "True (attivo)" : "False (disattivo)"}</span>`;
    else if (k === "int" || k === "float") ed = `<input type="number" step="${k === "int" ? 1 : "any"}" value="${esc(val)}" data-in="${i.name}" style="width:160px"><button class="btn small" data-save="${i.name}">Salva</button>`;
    else if (k === "json" || (k === "str" && String(val).length > 70)) ed = `<textarea rows="${Math.min(8, Math.max(2, Math.ceil(show(val).length / 90)))}" data-in="${i.name}">${esc(show(val))}</textarea><button class="btn small" data-save="${i.name}">Salva</button>`;
    else if (k === "str" || k === "path" || k === "none") ed = `<input type="text" value="${esc(show(val))}" data-in="${i.name}"><button class="btn small" data-save="${i.name}">Salva</button>`;
    else ed = `<code style="font-size:12px">${esc(show(val))}</code><span class="badge">non modificabile</span>`;
    if (i.overridden) ed += `<button class="btn small" data-reset="${i.name}" title="Torna al valore di config.py">↺ Ripristina</button>`;
    const def = i.overridden ? `Valore in config.py: <code>${esc(show(i.default))}</code>` : "";
    const comp = i.computed ? `<div class="sub2">ⓘ calcolato in config.py da: <code>${esc(i.source.slice(0, 120))}</code></div>` : "";
    return `<div class="cvar ${i.overridden ? "ov" : ""}" data-s="${esc((i.name + " " + i.description + " " + (i.subsection || "")).toLowerCase())}">
      <div><div class="nm">${esc(i.name)} ${i.overridden ? '<span class="badge warn">FORZATO</span>' : ""}</div>${i.subsection ? `<div class="sub2">${esc(i.subsection)}</div>` : ""}${comp}</div>
      <div class="desc">${esc(i.description)}</div><div class="ed">${ed}</div>${def ? `<div class="def">${def}</div>` : ""}</div>`;
  },
  async cfgClick(e, target, setup) {
    const t = e.target;
    if (t.dataset.save) { const inp = $(`[data-in="${t.dataset.save}"]`, target); this.saveVar(t.dataset.save, inp.value, target, setup); }
    else if (t.dataset.reset) this.resetVar(t.dataset.reset, target, setup);
    else if (t.id === "cfgResetAll" && confirm("Ripristinare tutti i valori di config.py?")) this.resetVar(null, target, setup);
  },
  async saveVar(name, value, target, setup) {
    try {
      await api("/api/tools/config", {json: {name, value}});
      toast(`${name} forzato`, "ok");
      await this.loadConfig(target, setup);
      if (setup) this.open(true);
    } catch (e) { toast(e.message, "bad", 6000); }
  },
  async resetVar(name, target, setup) {
    try {
      await api("/api/tools/config/reset", {json: {name}});
      toast(name ? `${name} ripristinato` : "Tutti i valori ripristinati", "ok");
      await this.loadConfig(target, setup);
    } catch (e) { toast(e.message, "bad"); }
  },
  async loadIndex() {
    const box = $("#sub-index");
    let st = {};
    try { st = await api("/api/docindex"); } catch {}
    const d = APP.meta.docs;
    box.innerHTML = `<div class="card"><h3 style="margin-top:0">Documenti sul computer</h3>
      <p>La sezione Chiedi trova i PDF nelle cartelle seguenti (configurabili con <code>ONEDRIVE_DOCS_ROOT</code> e <code>WEB_EXTRA_DOC_DIRS</code>):</p>
      <ul>${d.roots.map(r => `<li><code>${esc(r)}</code></li>`).join("") || "<li>nessuna cartella trovata</li>"}</ul>
      <div class="stats"><div class="stat"><b>${d.files}</b><span>documenti trovati</span></div><div class="stat"><b>${st.indexed_files ?? "–"}</b><span>PDF indicizzati per la ricerca testuale</span></div><div class="stat"><b>${st.running ? `${st.done}/${st.total}` : "pronto"}</b><span>${st.running ? "indicizzazione in corso" : "stato indice"}</span></div></div>
      <p style="font-size:12px;color:#4b5568">L'indice testuale è incrementale: viene aggiornato solo per i PDF nuovi o modificati, la prima volta che si usa «Cerca anche nei documenti del computer» o con il pulsante qui sotto.</p>
      <button class="btn primary" id="btnIdx">↻ Aggiorna indice documenti</button></div>`;
    $("#btnIdx").onclick = async () => { await api("/api/docindex", {method: "POST"}); toast("Aggiornamento dell'indice avviato in background", "ok"); setTimeout(() => this.loadIndex(), 1500); };
  },
};
$("#prereq").addEventListener("click", e => {
  if (e.target.closest("[data-recheck]")) { e.preventDefault(); Tools.open(true); }
  const c = e.target.closest("[data-copy]"); if (c) copyText(c.dataset.copy);
});
$("#optGrid").addEventListener("click", e => { const b = e.target.closest(".opt"); if (b) Tools.form(b.dataset.mode); });
$("#btnStop").onclick = async () => { if (confirm("Interrompere l'opzione? I progressi vengono salvati e potrai riprendere.")) { await api("/api/tools/stop", {method: "POST"}); toast("Interruzione richiesta: salvataggio in corso…"); } };
$("#toolTabs").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  $$("#toolTabs button").forEach(x => x.classList.toggle("active", x === b));
  $$("#toolsBody .sub").forEach(s => s.classList.toggle("active", s.id === "sub-" + b.dataset.sub));
  if (b.dataset.sub === "config") Tools.loadConfig();
  if (b.dataset.sub === "index") Tools.loadIndex();
});

/* ════════════════════════════════════════════════════════════════════
   GUIDA
   ════════════════════════════════════════════════════════════════════ */
const Guide = {
  done: false,
  async open() {
    if (this.done) return;
    const r = await fetch("/api/guide");
    const html = md(await r.text());
    const el = $("#guide");
    el.innerHTML = html;
    const h2 = $$("h2", el);
    if (h2.length > 2) {
      const toc = document.createElement("div");
      toc.className = "toc";
      toc.innerHTML = "<b>Indice</b><ol>" + h2.map(h => `<li><a href="#${h.id}" data-to="${h.id}">${h.textContent}</a></li>`).join("") + "</ol>";
      el.querySelector("h1") ? el.querySelector("h1").after(toc) : el.prepend(toc);
      toc.onclick = e => { const a = e.target.closest("[data-to]"); if (a) { e.preventDefault(); document.getElementById(a.dataset.to).scrollIntoView({behavior: "smooth"}); } };
    }
    this.done = true;
  },
};

/* ════════════════════════════════════════════════════════════════════
   Stato del server / aggiornamento automatico
   ════════════════════════════════════════════════════════════════════ */
async function refreshMeta() {
  let m;
  try { m = await api("/api/meta"); }
  catch { setStatus("err", "Server non raggiungibile: avviare AVVIA_WEB.bat"); return setTimeout(refreshMeta, 5000); }
  const first = !APP.meta;
  APP.meta = m;
  $("#toolsTab").hidden = !m.local;
  if (m.meta) {
    Object.assign(APP.colors, m.meta.colors || {});
    $("#fileName").textContent = `${m.meta.name} · ${m.meta.mtime}`;
    $("#fileName").title = m.meta.file;
  }
  if (m.error) setStatus("err", m.error);
  else if (!m.ready || m.loading) setStatus("", m.ready ? "Aggiornamento del file in corso…" : "Lettura del file Excel…");
  else setStatus("ok", `File aggiornato al ${m.meta.mtime} · AI: ${m.ai.ok ? "attiva" : "non disponibile"}${m.job && m.job.running ? ` · opzione ${m.job.mode} in esecuzione` : ""}`);
  if (m.ready && m.key !== APP.key) {
    const changed = !!APP.key;
    APP.key = m.key;
    renderSheetTabs();
    const names = m.meta.sheets.map(s => s.name);
    if (!APP.current || !names.includes(APP.current)) APP.current = names[0];
    if (changed) {
      for (const k in APP.sheets) APP.sheets[k].data = null;
      Ask.ready = false;
      toast("Il file Excel è stato aggiornato: dati ricaricati", "ok", 6000);
    }
    if (APP.current) Grid.load(APP.current, true);
    if (changed && window.Explorer) Explorer.reset(true);
  }
  Ask.syncAi && APP.view === "ask" && Ask.ready && (() => { const ok = m.ai && m.ai.ok; $("#optAi").disabled = !ok; })();
  setTimeout(refreshMeta, first || !m.ready || m.loading ? 1500 : 5000);
}
function setStatus(kind, text) { $("#status").className = "status " + kind; $("#statusText").textContent = text; $("#status").title = text; }

const start = (location.hash || "#explore").slice(1);
refreshMeta().then(() => showView(["explore", "sheets", "ask", "learn", "tools", "guide"].includes(start) ? start : "explore"));
window.Grid = Grid; window.showView = showView;
