/* AskTrainMind – vista «Esplora» a blocchi verticali:
   ① Configurazioni treno → ② FRS / DOC ID → ③ Funzioni → ④ Funzioni AI + Requisiti */
"use strict";

window.Explorer = {
  data: null, key: null, loading: null,
  sel: {cfg: [], doc: [], fn: []},
  f: {q: "", st: [], req: false, rnm: false},
  details: {},          // fid -> risposta /api/explorer/func (cache)
  dopt: {},             // fid -> {all, tab, rf, rq}

  async open() {
    if (this.data && this.key === APP.key) return this.render();
    if (!this.loading) this.loading = this.load();
    await this.loading;
  },
  async load() {
    $("#xWrap").innerHTML = `<div class="empty-grid"><span class="spin"></span> Caricamento della struttura…</div>`;
    try {
      const [d] = await Promise.all([api("/api/explorer"), APP.gloss.length ? null : loadGlossary()]);
      this.data = d; this.key = APP.key; this.details = {};
      const s = LS.get("xsel", null);
      if (s && s.key === APP.key) { this.sel = s.sel; this.f = Object.assign(this.f, s.f || {}); }
      const names = new Set(d.configs.map(c => c.name));
      this.sel.cfg = this.sel.cfg.filter(c => names.has(c));
      this.sel.fn = this.sel.fn.filter(x => d.funcs[x]);
      this.drawFilters();
      this.render();
    } catch (e) {
      $("#xWrap").innerHTML = `<div class="empty-grid">⚠️ ${esc(e.message)}</div>`;
    } finally { this.loading = null; }
  },
  reset(reload) {
    if (reload) { this.data = null; this.details = {}; if (APP.view === "explore") this.open(); return; }
    this.sel = {cfg: [], doc: [], fn: []};
    this.f = {q: "", st: [], req: false, rnm: false};
    $("#xSearch").value = "";
    this.drawFilters(); this.render();
  },
  save() { LS.set("xsel", {key: APP.key, sel: this.sel, f: this.f}); },

  /* ── filtri ── */
  drawFilters() {
    const d = this.data; if (!d) return;
    $("#xStates").innerHTML = `<span class="xlab">Esito:</span>` + ["g", "o", "r", "l"].map(k =>
      `<button class="fchip ${STATE_UI[k].cls}${this.f.st.includes(k) ? " on" : ""}" data-st="${k}" title="${esc(STATE_UI[k].label)}">${STATE_UI[k].icon} ${esc(STATE_UI[k].label.split(" (")[0])}</button>`).join("");
    $("#xReq").classList.toggle("on", this.f.req);
    $("#xRnm").classList.toggle("on", this.f.rnm);
    $("#xSearch").value = this.f.q;
  },
  fnPass(fid, cfgs) {
    const F = this.data.funcs[fid], f = this.f;
    if (!F) return false;
    if (f.req && !F.req) return false;
    if (f.rnm && !F.rnm) return false;
    if (f.st.length && !cfgs.some(c => f.st.includes(F.st[c] || ""))) return false;
    if (f.q) {
      const h = (fid + " " + (F.desc || "") + " " + F.docs.join(" ")).toLowerCase();
      if (!f.q.toLowerCase().split(/\s+/).every(w => h.includes(w))) return false;
    }
    return true;
  },
  anyFilter() { const f = this.f; return !!(f.q || f.st.length || f.req || f.rnm); },

  /* ── selezioni ── */
  toggle(kind, v, multi) {
    const a = this.sel[kind];
    const i = a.indexOf(v);
    if (i >= 0) a.splice(i, 1); else if (multi === false) this.sel[kind] = [v]; else a.push(v);
    if (kind === "cfg") {
      const ok = new Set(this.docsFor().map(x => x.doc));
      this.sel.doc = this.sel.doc.filter(x => ok.has(x));
    }
    this.save(); this.render(kind);
  },
  docsFor() {
    const d = this.data, m = new Map();
    for (const c of this.sel.cfg) for (const x of d.docs[c] || []) {
      let e = m.get(x.doc);
      if (!e) m.set(x.doc, e = {doc: x.doc, codes: {}, funcs: new Set()});
      e.codes[c] = x.code;
      x.funcs.forEach(f => e.funcs.add(f));
    }
    return [...m.values()].sort((a, b) => a.doc.localeCompare(b.doc));
  },

  /* ── rendering ── */
  render(changed) {
    const d = this.data; if (!d) return;
    const W = $("#xWrap");
    let h = this.lvlConfigs();
    const docs = this.sel.cfg.length ? this.docsFor() : [];
    if (this.sel.cfg.length) h += this.lvlDocs(docs);
    const fnList = this.fnCandidates(docs);
    if (fnList) h += this.lvlFuncs(fnList);
    if (this.sel.fn.length) h += this.lvlDetail();
    const before = new Set([...W.querySelectorAll(".xlvl,.dpanel")].map(x => x.id));
    W.innerHTML = h;
    W.querySelectorAll(".xlvl,.dpanel").forEach(x => { if (!before.has(x.id)) x.classList.add("anim"); });
    this.crumbs();
    this.sel.fn.forEach(fid => this.fillDetail(fid));
    if (changed) {
      const next = {cfg: "#xl-doc", doc: "#xl-fn", fn: "#xl-det"}[changed];
      const el = next && $(next);
      if (el) setTimeout(() => el.scrollIntoView({behavior: "smooth", block: "start"}), 30);
    }
  },
  lvlHead(n, title, sub, extra = "") {
    return `<div class="xlvl-h"><span class="xnum">${n}</span><h3>${title}</h3><small>${sub}</small><span class="spacer"></span>${extra}</div>`;
  },
  stateBar(states, tot) {
    tot = tot || Object.values(states).reduce((a, b) => a + b, 0) || 1;
    return `<div class="sbar">${["b", "g", "o", "r", "l"].filter(k => states[k]).map(k =>
      `<i class="${STATE_UI[k].cls}" style="flex:${states[k]}" title="${esc(STATE_UI[k].label)}: ${states[k]}"></i>`).join("")}</div>`;
  },
  lvlConfigs() {
    const d = this.data;
    return `<section class="xlvl" id="xl-cfg">${this.lvlHead("1", "Configurazioni treno", "Clic per aprire una o più configurazioni (selezione multipla)",
      `<button class="btn small" data-act="allcfg" title="Seleziona tutte le configurazioni con documenti">☑ Tutte</button>`)}
      <div class="xgrid cfgs">${d.configs.map(c => {
        const on = this.sel.cfg.includes(c.name), empty = !c.funcs;
        return `<button class="xtile cfgtile${on ? " on" : ""}${empty ? " empty" : ""}" style="--cc:${cfgColor(c.name)}" data-cfg="${esc(c.name)}"
          title="${empty ? "Nessun documento collegato nel foglio Funzioni" : esc(c.fleet || c.name)}">
          <div class="t-top"><b>${esc(c.name)}</b>${c.base ? `<span class="badge info" title="Configurazione di riferimento">★ base</span>` : ""}${on ? `<span class="tick">✔</span>` : ""}</div>
          <div class="t-sub">${esc(c.fleet || "")}${c.bl ? ` · BL ${esc(c.bl)}` : ""}</div>
          <div class="t-kpi"><span title="Documenti FRS collegati">📚 ${c.docs}</span><span title="Funzioni trattate">⚙️ ${c.funcs}</span><span title="Treni (dal foglio Flotte)">🚆 ${(c.trains || []).length}</span></div>
          ${empty ? `<div class="t-empty">nessun documento</div>` : this.stateBar(c.states)}</button>`;
      }).join("")}</div></section>`;
  },
  lvlDocs(docs) {
    const q = this.f.q.toLowerCase();
    const vis = docs.filter(x => !q || x.doc.toLowerCase().includes(q) || [...x.funcs].some(f => this.fnPass(f, this.sel.cfg)));
    return `<section class="xlvl" id="xl-doc">${this.lvlHead("2", "FRS / DOC ID", `${vis.length} documenti per ${this.sel.cfg.map(esc).join(", ")}`,
      `<button class="btn small" data-act="alldoc">☑ Tutti</button><button class="btn small" data-act="nodoc">☐ Nessuno</button>`)}
      <div class="xgrid docs">${vis.map(x => {
        const on = this.sel.doc.includes(x.doc);
        const n = [...x.funcs].filter(f => this.fnPass(f, this.sel.cfg)).length;
        return `<button class="xtile doctile${on ? " on" : ""}${n ? "" : " dim"}" data-doc="${esc(x.doc)}">
          <div class="t-top"><b>📘 ${esc(x.doc.replace(/^FRS_/, ""))}</b>${on ? `<span class="tick">✔</span>` : ""}</div>
          <div class="t-codes">${this.sel.cfg.map(c => x.codes[c] !== undefined
            ? `<span class="dot" style="--cc:${cfgColor(c)}" title="${esc(c)}: ${esc(x.codes[c] || "senza codice")}"></span>`
            : `<span class="dot off" title="${esc(c)}: link documentale mancante"></span>`).join("")}
            <small>${esc(Object.values(x.codes).filter(Boolean)[0] || "")}</small></div>
          <div class="t-kpi"><span>⚙️ ${n}${n !== x.funcs.size ? "/" + x.funcs.size : ""} funzioni</span></div></button>`;
      }).join("") || `<div class="xnone">Nessun FRS corrisponde ai filtri.</div>`}</div></section>`;
  },
  fnCandidates(docs) {
    const d = this.data;
    if (this.sel.doc.length) {
      const groups = [];
      for (const doc of this.sel.doc) {
        const x = docs.find(y => y.doc === doc); if (!x) continue;
        groups.push({doc, fns: [...x.funcs].filter(f => this.fnPass(f, this.sel.cfg)).sort()});
      }
      return {groups, cfgs: this.sel.cfg};
    }
    if (this.anyFilter() && this.f.q) {   // ricerca senza selezione: tutte le funzioni che corrispondono
      const cfgs = this.sel.cfg.length ? this.sel.cfg : d.configs.filter(c => c.funcs).map(c => c.name);
      const fns = Object.keys(d.funcs).filter(f => this.fnPass(f, cfgs) && (!this.sel.cfg.length || cfgs.some(c => d.funcs[f].st[c])));
      return {groups: [{doc: `Risultati per «${this.f.q}»`, fns: fns.sort().slice(0, 300), search: true}], cfgs};
    }
    return null;
  },
  lvlFuncs({groups, cfgs}) {
    const d = this.data, tot = groups.reduce((n, g) => n + g.fns.length, 0);
    return `<section class="xlvl" id="xl-fn">${this.lvlHead("3", "Funzioni", `${tot} funzioni · clic per vedere Funzioni AI e Requisiti (selezione multipla)`,
      this.sel.fn.length ? `<button class="btn small" data-act="nofn">☐ Deseleziona</button>` : "")}
      ${groups.map(g => `<div class="fgroup"><div class="fg-h">${g.search ? "🔎" : "📘"} ${esc(g.doc)} <small>${g.fns.length}</small></div>
        <div class="xgrid fns">${g.fns.map(fid => {
          const F = d.funcs[fid], on = this.sel.fn.includes(fid);
          return `<button class="xtile fntile${on ? " on" : ""}" data-fn="${esc(fid)}" title="${esc(F.desc || "")}">
            <div class="t-top"><b>${esc(fid)}</b>${on ? `<span class="tick">✔</span>` : ""}</div>
            <div class="t-desc">${esc((F.desc || "").slice(0, 110))}${(F.desc || "").length > 110 ? "…" : ""}</div>
            <div class="t-pills">${cfgs.map(c => { const s = STATE_UI[F.st[c] || ""];
              return `<span class="pill ${s.cls}" style="--cc:${cfgColor(c)}" title="${esc(c)}: ${esc(s.label)}${F.sim[c] != null ? " (" + F.sim[c] + "%)" : ""}">${s.icon}</span>`; }).join("")}
              <span class="spacer"></span>${F.req ? `<span class="mini" title="Requisiti">📋 ${F.req}</span>` : ""}${F.rnm ? `<span class="mini warn" title="Righe in Reqs not matched">⚠️ ${F.rnm}</span>` : ""}</div></button>`;
        }).join("") || `<div class="xnone">Nessuna funzione corrisponde ai filtri.</div>`}</div></div>`).join("")}</section>`;
  },
  lvlDetail() {
    return `<section class="xlvl" id="xl-det">${this.lvlHead("4", "Dettaglio funzioni", "Funzioni AI, Requisiti, Reqs not matched e Index per ogni funzione selezionata")}
      <div class="dstack">${this.sel.fn.map(fid => `<article class="dpanel" id="dp-${cssId(fid)}" data-fid="${esc(fid)}"><div class="empty-grid"><span class="spin"></span> ${esc(fid)}…</div></article>`).join("")}</div></section>`;
  },
  crumbs() {
    const s = this.sel, parts = [`<button data-cr="top">🧭 Esplora</button>`];
    if (s.cfg.length) parts.push(`<button data-cr="cfg">🚆 ${s.cfg.map(esc).join(", ")}</button>`);
    if (s.doc.length) parts.push(`<button data-cr="doc">📘 ${s.doc.length > 2 ? s.doc.length + " FRS" : s.doc.map(x => esc(x.replace(/^FRS_/, ""))).join(", ")}</button>`);
    if (s.fn.length) parts.push(`<button data-cr="fn">⚙️ ${s.fn.length > 2 ? s.fn.length + " funzioni" : s.fn.map(esc).join(", ")}</button>`);
    $("#xCrumbs").innerHTML = parts.join(`<span class="sep">›</span>`) +
      (s.cfg.length || s.fn.length || this.f.q ? "" : `<span class="hint">Inizia scegliendo una configurazione, oppure cerca direttamente una funzione ↑</span>`);
  },

  /* ── pannello di dettaglio ── */
  async fillDetail(fid) {
    const box = $(`#dp-${cssId(fid)}`); if (!box) return;
    const o = this.dopt[fid] || (this.dopt[fid] = {all: !this.sel.cfg.length, tab: "ai", rf: "all", rq: ""});
    const cfgs = o.all ? [] : this.sel.cfg;
    const k = fid + "|" + cfgs.join(",");
    let d = this.details[k];
    if (!d) {
      try { d = this.details[k] = await api(`/api/explorer/func?fid=${encodeURIComponent(fid)}&cfg=${encodeURIComponent(cfgs.join(","))}`); }
      catch (e) { box.innerHTML = `<div class="tx bad">${esc(fid)}: ${esc(e.message)}</div>`; return; }
    }
    if (!$(`#dp-${cssId(fid)}`)) return;
    const tabs = [["ai", "🧠 Funzioni AI", d.cards.length], ["req", "📋 Requisiti", d.reqs.length], ["rnm", "⚠️ Reqs not matched", d.rnm.length], ["idx", "🗂 Index", d.index.length]];
    box.innerHTML = `<header class="dp-h"><div><h4>⚙️ ${esc(fid)}</h4><p>${esc(d.desc || "")}</p></div>
      <div class="dp-acts">
        <div class="seg small" data-dact="scope"><button data-v="sel" class="${o.all ? "" : "on"}" ${this.sel.cfg.length ? "" : "disabled"} title="Solo le configurazioni selezionate al livello 1">Selezionate</button><button data-v="all" class="${o.all ? "on" : ""}" title="Tutte le configurazioni che trattano la funzione">Tutte</button></div>
        <button class="btn small" data-dact="ask" title="Fai una domanda su questa funzione">💬 Chiedi</button>
        <button class="btn small" data-dact="sheet" title="Apri la funzione nel foglio Funzioni">📊 Foglio</button>
        <button class="btn small icon" data-dact="close" title="Chiudi">✕</button></div></header>
      <nav class="dtabs">${tabs.map(([t, l, n]) => `<button data-tab="${t}" class="${o.tab === t ? "on" : ""}">${l} <span class="n">${n}</span></button>`).join("")}</nav>
      <div class="dbody">${this.tabBody(d, o)}</div>`;
  },
  tabBody(d, o) {
    if (o.tab === "ai") {
      if (!d.cards.length) return `<div class="xnone">Nessuna configurazione tratta questa funzione.</div>`;
      return `<div class="legend">${["b", "g", "o", "r", "l"].map(x => `<span class="stchip ${STATE_UI[x].cls}">${STATE_UI[x].icon} ${STATE_UI[x].label}</span>`).join("")}</div>
        <div class="ccgrid">${d.cards.map(k => cfgCardHTML(k, d.base)).join("")}</div>`;
    }
    if (o.tab === "req") return this.reqMatrix(d, o);
    if (o.tab === "rnm") {
      if (!d.rnm.length) return `<div class="tx ok">✔ Nessun requisito in «Reqs not matched» per questa funzione.</div>`;
      return `<div class="rnmlist">${d.rnm.map(r => {
        const kind = /mancanza link/i.test(r.note) ? ["nolink", "🔗"] : /simile/i.test(r.note) ? ["sim", "≈"] : ["miss", "⚠️"];
        return `<div class="rnm ${kind[0]}"><div class="r-ico">${kind[1]}</div><div><div class="r-id"><b>${esc(r.id)}</b> ${(r.present || []).map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}" title="presente in ${esc(c)}">${esc(c)}</span>`).join("")}</div>
          <div class="r-desc">${glossify(esc(r.desc || ""))}</div>${r.note ? `<div class="r-note">💬 ${glossify(esc(r.note))}</div>` : ""}</div></div>`;
      }).join("")}</div>`;
    }
    if (!d.index.length) return `<div class="xnone">Nessuna riga in «Index Funzioni».</div>`;
    const cf = d.configs;
    return `<div class="tblwrap"><table class="mtx"><thead><tr><th>Documento</th><th>Par.</th><th>Titolo</th>${cf.map(c => `<th><span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span></th>`).join("")}</tr></thead>
      <tbody>${d.index.map(r => `<tr><td>${esc(r.doc)}</td><td>${esc(r.par || "")}</td><td>${esc(r.title || "")}</td>${cf.map(c => { const v = (r.status || {})[c] || "";
        return `<td class="c ${/^MATCHED/i.test(v) ? "ok" : /NOT/i.test(v) ? "bad" : "na"}">${esc(v)}</td>`; }).join("")}</tr>`).join("")}</tbody></table></div>`;
  },
  reqMatrix(d, o) {
    if (!d.reqs.length) return `<div class="xnone">Nessun requisito nel foglio «Requisiti» per questa funzione.</div>`;
    const cf = d.configs;
    const KIND = {ref: ["★", "ref", "Riferimento (testo del requisito)"], eq: ["=", "eq", "Uguale alla base (MATCHED)"], diff: ["≠", "diff", "Testo diverso (FOUND DIFF)"],
                  only: ["➕", "only", "Presente solo qui (manca nella base)"], unk: ["?", "unk", "Valore non classificato"]};
    const isDiff = r => Object.values(r.cells).some(x => x.k === "diff" || x.k === "only");
    const q = (o.rq || "").toLowerCase();
    const rows = d.reqs.filter(r => (o.rf === "all" || (o.rf === "diff") === isDiff(r)) && (!q || (r.id + " " + r.desc).toLowerCase().includes(q)));
    const nd = d.reqs.filter(isDiff).length;
    return `<div class="rqbar"><div class="seg small" data-dact="rf">
        <button data-v="all" class="${o.rf === "all" ? "on" : ""}">Tutti <span class="n">${d.reqs.length}</span></button>
        <button data-v="diff" class="${o.rf === "diff" ? "on" : ""}">≠ Diversi <span class="n">${nd}</span></button>
        <button data-v="same" class="${o.rf === "same" ? "on" : ""}">= Uguali <span class="n">${d.reqs.length - nd}</span></button></div>
        <div class="search small"><span class="sicon">🔎</span><input data-dact="rq" type="search" placeholder="Filtra requisiti…" value="${esc(o.rq || "")}"></div>
        <span class="legend">${Object.values(KIND).slice(0, 4).map(k => `<span class="rk ${k[1]}">${k[0]}</span> ${k[2].split(" (")[0]}`).join(" · ")}</span></div>
      <div class="tblwrap"><table class="mtx"><thead><tr><th>Requisito</th>${cf.map(c => `<th><span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span></th>`).join("")}</tr></thead>
      <tbody>${rows.map(r => `<tr><td class="rq"><b>${esc(r.id)}</b><div>${glossify(esc(r.desc || ""))}</div></td>${cf.map(c => {
        const x = r.cells[c]; if (!x) return `<td class="c na" title="Non presente">–</td>`;
        const k = KIND[x.k] || KIND.unk;
        return `<td class="c"><button class="rk ${k[1]}" data-rc="${esc(r.id)}|${esc(c)}" title="${esc(k[2])} — clic per il testo">${k[0]}</button></td>`;
      }).join("")}</tr>`).join("") || `<tr><td colspan="${cf.length + 1}" class="xnone">Nessun requisito con questi filtri.</td></tr>`}</tbody></table></div>`;
  },
  detailEvent(e, panel) {
    const fid = panel.dataset.fid, o = this.dopt[fid], t = e.target;
    const cfgs = o.all ? [] : this.sel.cfg;
    const d = this.details[fid + "|" + cfgs.join(",")];
    const tab = t.closest("[data-tab]");
    if (tab) { o.tab = tab.dataset.tab; return this.fillDetail(fid); }
    const segb = t.closest(".seg button");
    if (segb) {
      const kind = segb.parentElement.dataset.dact;
      if (kind === "scope") o.all = segb.dataset.v === "all";
      if (kind === "rf") o.rf = segb.dataset.v;
      return this.fillDetail(fid);
    }
    const rc = t.closest("[data-rc]");
    if (rc && d) {
      const [id, c] = rc.dataset.rc.split("|");
      const r = d.reqs.find(x => x.id === id), x = r && r.cells[c];
      if (x) Popup.open(e.clientX, e.clientY, `<div class="popt"><b>${esc(id)}</b> · <span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span><pre>${esc(x.t || "")}</pre></div>`, 460);
      return;
    }
    const a = t.closest("[data-dact]");
    if (!a || a.tagName === "INPUT") return;
    const act = a.dataset.dact;
    if (act === "close") { this.sel.fn = this.sel.fn.filter(x => x !== fid); this.save(); this.render(); }
    else if (act === "ask") { showView("ask"); Ask.prefill(`Come funziona la funzione ${fid} per tutte le configurazioni del treno?`); }
    else if (act === "sheet") this.openSheet(fid);
  },
  async openSheet(fid) {
    showView("sheets");
    await Grid.load("Funzioni");
    const S = Grid.S; if (!S) return;
    S.filters = {}; S.quick = [];
    Grid.setFilter(0, {vals: new Set([fid]), text: ""});
    if (Grid.mode === "rows") setFilterMode("block");
  },
};

function cssId(s) { return String(s).replace(/[^\w-]/g, "_"); }

/* ── eventi ── */
(() => {
  const X = window.Explorer;
  $("#xWrap").addEventListener("click", e => {
    const t = e.target;
    const panel = t.closest(".dpanel");
    if (panel) {
      if (t.closest("[data-pdf],[data-pages]")) {
        const p = t.closest("[data-pdf]"); if (p) return Modal.pdf(p.dataset.pdf, +p.dataset.page, p.dataset.title);
        const g = t.closest("[data-pages]"); return Modal.pages(g.dataset.pages, +g.dataset.first, +g.dataset.last, g.dataset.title);
      }
      return X.detailEvent(e, panel);
    }
    const c = t.closest("[data-cfg]"); if (c) return X.toggle("cfg", c.dataset.cfg, !(e.altKey));
    const d = t.closest("[data-doc]"); if (d) return X.toggle("doc", d.dataset.doc);
    const f = t.closest("[data-fn]"); if (f) return X.toggle("fn", f.dataset.fn);
    const a = t.closest("[data-act]"); if (!a) return;
    const act = a.dataset.act;
    if (act === "allcfg") X.sel.cfg = X.data.configs.filter(x => x.funcs).map(x => x.name);
    if (act === "alldoc") X.sel.doc = X.docsFor().map(x => x.doc);
    if (act === "nodoc") X.sel.doc = [];
    if (act === "nofn") X.sel.fn = [];
    X.save(); X.render(act === "allcfg" ? "cfg" : act === "alldoc" ? "doc" : null);
  });
  let rqT = null;
  $("#xWrap").addEventListener("input", e => {
    const i = e.target.closest("[data-dact=rq]"); if (!i) return;
    const fid = i.closest(".dpanel").dataset.fid;
    X.dopt[fid].rq = i.value;
    clearTimeout(rqT);
    rqT = setTimeout(() => {
      const pos = i.selectionStart;
      X.fillDetail(fid).then(() => { const n = $(`#dp-${cssId(fid)} [data-dact=rq]`); if (n) { n.focus(); n.setSelectionRange(pos, pos); } });
    }, 200);
  });
  let qT = null;
  $("#xSearch").addEventListener("input", e => {
    clearTimeout(qT);
    qT = setTimeout(() => { X.f.q = e.target.value.trim(); X.save(); X.render(); }, 180);
  });
  $("#xStates").onclick = e => {
    const b = e.target.closest("[data-st]"); if (!b) return;
    const k = b.dataset.st;
    X.f.st = X.f.st.includes(k) ? X.f.st.filter(x => x !== k) : [...X.f.st, k];
    X.save(); X.drawFilters(); X.render();
  };
  $("#xReq").onclick = () => { X.f.req = !X.f.req; X.save(); X.drawFilters(); X.render(); };
  $("#xRnm").onclick = () => { X.f.rnm = !X.f.rnm; X.save(); X.drawFilters(); X.render(); };
  $("#xReset").onclick = () => { X.reset(); X.save(); };
  $("#xCrumbs").onclick = e => {
    const b = e.target.closest("[data-cr]"); if (!b) return;
    const k = b.dataset.cr;
    if (k === "top") { X.sel = {cfg: [], doc: [], fn: []}; X.save(); X.render(); $("#xScroll").scrollTo({top: 0, behavior: "smooth"}); return; }
    const el = $({cfg: "#xl-cfg", doc: "#xl-doc", fn: "#xl-fn"}[k] || "#xl-det");
    if (el) el.scrollIntoView({behavior: "smooth", block: "start"});
  };
})();
