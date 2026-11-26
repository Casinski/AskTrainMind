/* AskTrainMind – vista «Esplora» a blocchi verticali:
   ① Configurazioni treno → ② FRS / DOC ID → ③ Funzioni → ④ Dettaglio funzioni
   (Funzioni AI · PDF affiancati delle configurazioni scelte · Requisiti con testi a confronto) */
"use strict";

window.Explorer = {
  data: null, key: null, loading: null,
  sel: {cfg: [], doc: [], fn: []},
  f: {q: "", st: [], req: false},
  details: {},          // fid -> dettaglio completo della funzione (tutte le configurazioni)
  dopt: {},             // fid -> {all, tab, rf, rq, open, hide, cols, pg}

  async open() {
    if (this.data && this.key === APP.key) return this.render();
    if (!this.loading) this.loading = this.load();
    await this.loading;
  },
  async load() {
    $("#xWrap").innerHTML = `<div class="empty-grid"><span class="spin"></span> Caricamento della struttura…</div>`;
    try {
      const [d] = await Promise.all([DS.tree(), APP.gloss.length ? null : loadGlossary()]);
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
    this.f = {q: "", st: [], req: false};
    $("#xSearch").value = "";
    this.drawFilters(); this.render();
  },
  save() { LS.set("xsel", {key: APP.key, sel: this.sel, f: this.f}); },

  /* ── filtri ── */
  drawFilters() {
    const d = this.data; if (!d) return;
    $("#xStates").innerHTML = `<span class="xlab">Esito:</span>` + ["g", "o", "r", "l", "x"].map(k =>
      `<button class="fchip ${STATE_UI[k].cls}${this.f.st.includes(k) ? " on" : ""}" data-st="${k}" title="${esc(STATE_UI[k].label)}">${STATE_UI[k].icon} ${esc(STATE_UI[k].label.split(" (")[0])}</button>`).join("");
    $("#xReq").classList.toggle("on", this.f.req);
    $("#xSearch").value = this.f.q;
  },
  fnPass(fid, cfgs) {
    const F = this.data.funcs[fid], f = this.f;
    if (!F) return false;
    if (f.req && !F.req) return false;
    if (f.st.length && !cfgs.some(c => f.st.includes(F.st[c] || ""))) return false;
    if (f.q) {
      const h = (fid + " " + (F.desc || "") + " " + F.docs.join(" ")).toLowerCase();
      if (!f.q.toLowerCase().split(/\s+/).every(w => h.includes(w))) return false;
    }
    return true;
  },
  anyFilter() { const f = this.f; return !!(f.q || f.st.length || f.req); },

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
    return `<div class="sbar">${["b", "g", "o", "r", "l", "x"].filter(k => states[k]).map(k =>
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
      }).join("") || `<div class="xnone">Nessun FRS corrisponde ai filtri.</div>`}</div>${this.confDocsList()}</section>`;
  },
  /* ── altri documenti del foglio CONFIG delle configurazioni scelte (FPD, FS, WT, EPL, GEN, ICD) ── */
  confDocsList() {
    const cd = this.data.confdocs || {}, q = this.f.q.toLowerCase(), cats = {};
    for (const c of this.sel.cfg) for (const x of cd[c] || []) {
      if (x.cat === "FRS") continue;
      if (q && !(x.doc + " " + x.desc + " " + x.code).toLowerCase().includes(q)) continue;
      ((cats[x.label] = cats[x.label] || {})[x.doc] = cats[x.label][x.doc] || []).push(Object.assign({c}, x));
    }
    const labs = Object.keys(cats);
    if (!labs.length) return "";
    const n = labs.reduce((a, l) => a + Object.keys(cats[l]).length, 0);
    const open = LS.get("xconf", "0") === "1";
    return `<details class="xconf"${open ? " open" : ""}><summary title="Documenti del foglio CONFIG presenti nelle cartelle della configurazione: aprili o affiancali nella scheda «PDF affiancati» di una funzione">📂 Altri documenti della configurazione <small>${n}</small></summary>
      ${labs.map(l => `<div class="xc-cat"><div class="fg-h">${esc(l)}</div><div class="xc-list">${Object.entries(cats[l]).map(([doc, xs]) => `<div class="xc-doc"><b>${esc(doc)}</b> <small>${esc(xs[0].desc || "")}</small>
        <span class="spacer"></span>${xs.map(x => x.fid ? `<button class="btn small" data-cpdf="${esc(x.fid)}" data-title="${esc(doc)} — ${esc(x.c)}" title="${esc(x.code)}${x.rev ? " rev " + esc(x.rev) : ""}"><span class="cfgb" style="--cc:${cfgColor(x.c)}">${esc(x.c)}</span> 📄</button>`
          : x.url ? `<a class="btn small" href="${esc(x.url)}" target="_blank" rel="noopener" title="${esc(x.code)}${x.rev ? " rev " + esc(x.rev) : ""} — apri su SharePoint"><span class="cfgb" style="--cc:${cfgColor(x.c)}">${esc(x.c)}</span> 🌐</a>` : "").join("")}</div>`).join("")}</div></div>`).join("")}</details>`;
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
    return `<section class="xlvl" id="xl-fn">${this.lvlHead("3", "Funzioni", `${tot} funzioni · clic per vedere Funzioni AI, PDF affiancati e Requisiti (selezione multipla)`,
      this.sel.fn.length ? `<button class="btn small" data-act="nofn">☐ Deseleziona</button>` : "")}
      ${groups.map(g => `<div class="fgroup"><div class="fg-h">${g.search ? "🔎" : "📘"} ${esc(g.doc)} <small>${g.fns.length}</small></div>
        <div class="xgrid fns">${g.fns.map(fid => {
          const F = d.funcs[fid], on = this.sel.fn.includes(fid);
          return `<button class="xtile fntile${on ? " on" : ""}" data-fn="${esc(fid)}" title="${esc(F.desc || "")}">
            <div class="t-top"><b>${esc(fid)}</b>${on ? `<span class="tick">✔</span>` : ""}</div>
            <div class="t-desc">${esc((F.desc || "").slice(0, 110))}${(F.desc || "").length > 110 ? "…" : ""}</div>
            <div class="t-pills">${cfgs.map(c => { const s = STATE_UI[F.st[c] || ""];
              return `<span class="pill ${s.cls}" style="--cc:${cfgColor(c)}" title="${esc(c)}: ${esc(s.label)}${F.sim[c] != null ? " (" + F.sim[c] + "%)" : ""}">${s.icon}</span>`; }).join("")}
              <span class="spacer"></span>${F.req ? `<span class="mini" title="Requisiti">📋 ${F.req}</span>` : ""}</div></button>`;
        }).join("") || `<div class="xnone">Nessuna funzione corrisponde ai filtri.</div>`}</div></div>`).join("")}</section>`;
  },
  lvlDetail() {
    return `<section class="xlvl" id="xl-det">${this.lvlHead("4", "Dettaglio funzioni", "Funzioni AI, PDF affiancati e Requisiti delle configurazioni scelte, per ogni funzione selezionata")}
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

  /* ── dettaglio: sottoinsieme per le configurazioni scelte ── */
  subset(full, cfgs) {
    const cs = cfgs && cfgs.length ? full.configs.filter(c => cfgs.includes(c)) : full.configs;
    const use = cs.length ? cs : full.configs, set = new Set(use);
    const cards = full.cards.filter(k => set.has(k.config)).map(k => Object.assign({}, k, {sameDoc: (k.sameDoc || []).filter(c => set.has(c))}));
    const reqs = [];
    for (const r of full.reqs) {
      const cells = {};
      for (const c of use) if (r.cells[c]) cells[c] = r.cells[c];
      if (Object.keys(cells).length) reqs.push({id: r.id, desc: r.desc, cells, full: r});
    }
    return {id: full.id, desc: full.desc, base: full.base, configs: use, cards, reqs};
  },
  focusFunction(fid) {
    if (!this.data || !this.data.funcs[fid]) { showView("explore"); return setTimeout(() => this.data && this.data.funcs[fid] && this.focusFunction(fid), 400); }
    if (!this.sel.fn.includes(fid)) this.sel.fn.push(fid);
    this.save();
    showView("explore");
    this.render();
    setTimeout(() => { const el = $(`#dp-${cssId(fid)}`); if (el) el.scrollIntoView({behavior: "smooth", block: "start"}); }, 60);
  },
  /* ── pannello di dettaglio ── */
  async fillDetail(fid) {
    const box = $(`#dp-${cssId(fid)}`); if (!box) return;
    const o = this.dopt[fid] || (this.dopt[fid] = {all: !this.sel.cfg.length, tab: LS.get("xtab", "ai"), rf: "all", rq: "", open: [], hide: [], cols: 0, pg: {}, add: []});
    let full = this.details[fid];
    if (!full) {
      try { full = this.details[fid] = await DS.func(fid); }
      catch (e) { box.innerHTML = `<div class="tx bad">${esc(fid)}: ${esc(e.message)}</div>`; return; }
    }
    if (!$(`#dp-${cssId(fid)}`)) return;
    const d = this.subset(full, o.all ? [] : this.sel.cfg);
    const groups = this.pdfGroups(d, o);
    const oldWrap = $(".tblwrap", box), keepTop = oldWrap ? oldWrap.scrollTop : 0;
    const tabs = [["ai", "🧠 Funzioni AI", d.cards.length], ["pdf", "📄 PDF affiancati", groups.filter(g => g.ref.fid || g.ref.url).length], ["req", "📋 Requisiti", d.reqs.length]];
    box.innerHTML = `<header class="dp-h"><div><h4>⚙️ ${esc(fid)}</h4><p>${glossify(esc(d.desc || ""))}</p></div>
      <div class="dp-acts">
        <div class="seg small" data-dact="scope"><button data-v="sel" class="${o.all ? "" : "on"}" ${this.sel.cfg.length ? "" : "disabled"} title="Solo le configurazioni selezionate al livello 1">Selezionate</button><button data-v="all" class="${o.all ? "on" : ""}" title="Tutte le configurazioni che trattano la funzione">Tutte</button></div>
        <button class="btn small" data-dact="ask" title="Fai una domanda su questa funzione">💬 Chiedi</button>
        <button class="btn small icon" data-dact="close" title="Chiudi">✕</button></div></header>
      <div class="dp-cfgs">${d.configs.map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`).join("")}</div>
      <nav class="dtabs">${tabs.map(([t, l, n]) => `<button data-tab="${t}" class="${o.tab === t ? "on" : ""}">${l} <span class="n">${n}</span></button>`).join("")}</nav>
      <div class="dbody">${this.tabBody(d, o, groups)}</div>`;
    const w = $(".tblwrap", box); if (w && keepTop) w.scrollTop = keepTop;   // ridisegno: la tabella resta dov'era
  },
  tabBody(d, o, groups) {
    if (o.tab === "pdf") return this.pdfPanel(d, o, groups);
    if (o.tab === "req") return this.reqMatrix(d, o);
    if (!d.cards.length) return `<div class="xnone">Nessuna configurazione tratta questa funzione.</div>`;
    return `<div class="legend">${["b", "g", "o", "r", "l", "x"].map(x => `<span class="stchip ${STATE_UI[x].cls}">${STATE_UI[x].icon} ${STATE_UI[x].label}</span>`).join("")}</div>
      <div class="ccgrid">${d.cards.map(k => cfgCardHTML(k, d.base)).join("")}</div>`;
  },

  /* ── PDF affiancati: una colonna per documento/pagina (configurazioni uguali raggruppate) ── */
  pdfGroups(d, o) {
    const m = new Map();
    const put = (r, c, extra) => {
      const key = (r.fid || r.url || r.doc + c) + "|" + (r.first || r.page || 1);
      if (!m.has(key)) m.set(key, {key, ref: r, configs: [], extra});
      if (!m.get(key).configs.includes(c)) m.get(key).configs.push(c);
    };
    for (const k of d.cards) if (k.ref) put(k.ref, k.config, "");
    // altri documenti collegati alla funzione nel foglio Funzioni (es. FS sotto l'FRS)
    for (const k of d.cards) for (const r of k.links || []) put(r, k.config, "link");
    // documenti del foglio CONFIG aggiunti dall'utente (FPD, FS, WT, EPL, GEN, ICD)
    for (const a of (o && o.add) || []) {
      const x = this.confDoc(a.cfg, a.doc); if (!x) continue;
      put(Object.assign({first: 1}, x, {added: a.cfg + "|" + a.doc}), a.cfg, "add");
    }
    return [...m.values()];
  },
  confDoc(c, doc) { return ((this.data.confdocs || {})[c] || []).find(x => x.doc === doc); },
  confDocsSelect(cfgs, o) {
    const cd = this.data.confdocs || {}, have = new Set(((o && o.add) || []).map(a => a.cfg + "|" + a.doc));
    const groups = [];
    for (const c of cfgs) {
      const byCat = {};
      for (const x of cd[c] || []) if (!have.has(c + "|" + x.doc)) (byCat[x.label] = byCat[x.label] || []).push(x);
      for (const [lab, xs] of Object.entries(byCat))
        groups.push(`<optgroup label="${esc(c)} — ${esc(lab)}">${xs.map(x => `<option value="${esc(c + "|" + x.doc)}">${esc(x.doc)} · ${esc(x.code)}${x.rev ? " rev " + esc(x.rev) : ""}</option>`).join("")}</optgroup>`);
    }
    if (!groups.length) return "";
    return `<select class="small" data-adddoc title="Affianca un altro documento della configurazione (schemi, wiring table, part list, ICD, documenti generali…)"><option value="">➕ Affianca documento CONFIG…</option>${groups.join("")}</select>`;
  },
  pdfPanel(d, o, groups) {
    if (!groups.length && !this.confDocsSelect(d.configs, o)) return `<div class="xnone">Nessun documento collegato alle configurazioni scelte.</div>`;
    const vis = groups.filter(g => !o.hide.includes(g.key));
    const cols = o.cols || Math.min(Math.max(vis.length, 1), 3);
    const missing = d.cards.filter(k => !k.ref && !(k.invalid || []).length).map(k => k.config);
    const invalid = d.cards.flatMap(k => (k.invalid || []).map(doc => ({doc, c: k.config})));
    const badge = cs => cs.map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`).join("");
    return `<div class="pdfwrap">
      <div class="pdfbar"><span class="xlab">Documenti:</span>${groups.map(g => `<button class="fchip${o.hide.includes(g.key) ? "" : " on"}" data-pgt="${esc(g.key)}" title="Mostra / nascondi la colonna">${badge(g.configs)} <small>${esc(g.ref.code || g.ref.doc)}</small></button>`).join("")}
        <span class="spacer"></span>${this.confDocsSelect(d.configs, o)}
        <div class="seg small" data-dact="cols" title="Colonne affiancate">${[0, 1, 2, 3, 4].map(n => `<button data-v="${n}" class="${o.cols === n ? "on" : ""}">${n || "Auto"}</button>`).join("")}</div>
        <button class="btn small" data-dact="pgreset" title="Riporta tutti i PDF alla pagina della funzione">⟲ Pagina funzione</button>
        <button class="btn small" data-dact="fs" title="Schermo intero (Esc per uscire)">⛶ Schermo intero</button></div>
      ${missing.length ? `<div class="tx info small">Senza documento collegato: ${badge(missing)}</div>` : ""}
      ${invalid.length ? `<div class="tx warn small">✖ Documenti aggiornati, riferimento di pagina da reinserire nel foglio Funzioni (PDF non mostrato): ${invalid.map(x => `${badge([x.c])} ${esc(x.doc)}`).join(" · ")}</div>` : ""}
      ${DS.sharepoint ? `<div class="tx info small">I PDF vengono caricati da SharePoint (link del file Excel): serve essere collegati con l'account aziendale. Se un riquadro chiede l'accesso o resta vuoto, accedi a SharePoint nel browser oppure usa ↗.</div>` : ""}
      ${vis.length ? (o.cols ? `<div class="pdfgrid" style="grid-template-columns:repeat(${cols},minmax(0,1fr))">${vis.map(g => this.pdfCol(g, o)).join("")}</div>` : this.pdfLayout(d, vis, o))
        : `<div class="xnone">Tutte le colonne sono nascoste: riattivale dai pulsanti qui sopra.</div>`}</div>`;
  },
  /* Disposizione come nel foglio Funzioni: una riga per documento (FRS, poi FS…, nell'ordine dei link),
     una colonna per configurazione; i PDF dello stesso tipo di documento stanno affiancati */
  pdfLayout(d, vis, o) {
    const order = [];
    for (const k of d.cards) for (const doc of k.order || []) if (!order.includes(doc)) order.push(doc);
    const rows = [];
    for (const g of vis) {
      const doc = g.ref.doc || "";
      let row = rows.find(r => r.doc === doc && r.extra === (g.extra === "add"));
      if (!row) rows.push(row = {doc, extra: g.extra === "add", gs: []});
      row.gs.push(g);
    }
    const pos = r => r.extra ? 1e6 + rows.indexOf(r) : (order.includes(r.doc) ? order.indexOf(r.doc) : 1e5 + rows.indexOf(r));
    rows.sort((a, b) => pos(a) - pos(b));
    const cfgs = d.configs.filter(c => vis.some(g => g.configs[0] === c));
    const n = Math.max(cfgs.length, 1);
    let html = "", line = 1;
    for (const r of rows) {
      const g0 = r.gs[0].ref;
      html += `<div class="pdfrowh" style="grid-row:${line}">${r.extra ? "➕" : "📄"} ${esc(r.doc)} <small>${esc(g0.cat || "")}</small></div>`;
      line++;
      // stessa configurazione con più documenti uguali (raro): righe successive
      const used = {};
      let extraLines = 0;
      for (const g of r.gs) {
        const ci = Math.max(cfgs.indexOf(g.configs[0]), 0);
        const k = used[ci] = (used[ci] || 0) + 1;
        extraLines = Math.max(extraLines, k);
        html += this.pdfCol(g, o, `grid-row:${line + k - 1};grid-column:${ci + 1}`);
      }
      line += extraLines;
    }
    return `<div class="pdfgrid" style="grid-template-columns:repeat(${n},minmax(0,1fr))">${html}</div>`;
  },
  pdfCol(g, o, style = "") {
    const r = g.ref, pg = o.pg[g.key] || r.first || r.page || 1;
    const url = pdfSrc(r, pg);
    const badge = g.configs.map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`).join("");
    const tag = g.extra === "add" ? `<span class="badge info" title="${esc(r.label || "")}">${esc(r.cat || "CONFIG")}</span>` : g.extra === "link" ? `<span class="badge" title="Altro documento collegato alla funzione nel foglio Funzioni">📎</span>` : "";
    const head = `<div class="pdfh">${badge}${tag}<span class="pdft" title="${esc(r.doc)} ${esc(r.code || "")}"><b>${esc(r.doc)}</b> <small>${esc(r.code || "")}${r.rev ? " rev " + esc(r.rev) : ""}</small></span>
      <span class="spacer"></span>${url ? `<span class="pnav"><button class="btn icon small" data-pnav="-1" title="Pagina precedente">◀</button><input type="number" min="1" value="${pg}" data-pgo title="Vai alla pagina"><button class="btn icon small" data-pnav="1" title="Pagina successiva">▶</button></span>
      <a class="btn icon small" href="${esc(url)}" target="_blank" rel="noopener" title="Apri in una nuova scheda">↗</a>` : ""}${r.added ? `<button class="btn icon small" data-rmdoc="${esc(r.added)}" title="Togli questo documento">✕</button>` : ""}</div>`;
    const body = url ? `<iframe src="${esc(url)}" title="${esc(r.doc)} — ${esc(g.configs.join(", "))}" loading="lazy"></iframe>`
      : `<div class="pdfnone">PDF non disponibile.</div>`;
    return `<div class="pdfcol" style="${style}" data-key="${esc(g.key)}" data-fid="${esc(r.fid || "")}" data-url="${esc(r.fid ? "" : r.url || "")}" data-first="${r.first || r.page || 1}">${head}<div class="pdfpg">${pagesTxt(r) ? "Funzione a " + pagesTxt(r) : ""}</div>${body}</div>`;
  },
  pdfGo(col, o, page) {
    page = Math.max(1, page | 0);
    o.pg[col.dataset.key] = page;
    const f = $("iframe", col); if (!f) return;
    const url = pdfSrc({fid: col.dataset.fid, url: col.dataset.url}, page);
    const n = document.createElement("iframe");
    n.title = f.title; n.src = url;
    f.replaceWith(n);
    $("[data-pgo]", col).value = page;
    const a = $("a[target]", col); if (a) a.href = url;
  },

  /* ── Requisiti: matrice con esito MATCHED / NOT MATCHED fra le configurazioni mostrate;
        la Description è sempre visibile; clic sulla riga = testi affiancati sotto la riga (i requisiti non si spostano) ── */
  reqStatus(r, cf, base) {
    const full = r.full || r, groups = full.groups || [full.desc || ""];
    const present = cf.filter(c => r.cells[c]), missing = cf.filter(c => !r.cells[c]);
    // riferimento: VZI_Base se c'è, altrimenti la prima configurazione mostrata che contiene il requisito
    const ref = present.includes(base) ? base : (present.find(c => r.cells[c].g >= 0) || present[0]);
    const letters = {};
    let n = 0;
    for (const c of [ref, ...present.filter(c => c !== ref)]) {
      const g = r.cells[c] ? r.cells[c].g : -1;
      if (g >= 0 && !(g in letters)) letters[g] = "ABCDEFGHIJ"[n++];
    }
    const variants = n, unk = present.filter(c => r.cells[c].g < 0);
    const byVar = {};
    present.forEach(c => { const L = r.cells[c].g >= 0 ? letters[r.cells[c].g] : "?"; (byVar[L] = byVar[L] || []).push(c); });
    let s;
    if (cf.length < 2) s = "single";
    else if (present.length === 1) s = "only";
    else if (missing.length) s = "partial";
    else if (variants > 1) s = "text";
    else if (unk.length) s = "check";
    else s = "match";
    const refG = r.cells[ref] ? r.cells[ref].g : -1;
    const text = (refG >= 0 ? groups[refG] : (r.cells[ref] && r.cells[ref].d)) || full.desc || "";
    return {s, present, missing, ref, refIsBase: ref === base, letters, variants, unk, byVar, groups, text};
  },
  reqWhy(st) {
    const L = cs => cs.map(esc).join(", ");
    const vars = () => Object.entries(st.byVar).filter(([k]) => k !== "?").map(([k, cs]) => `testo ${k}: ${L(cs)}`).join(" · ");
    switch (st.s) {
      case "match": return `stesso testo in tutte le ${st.present.length} configurazioni`;
      case "only": return `presente solo in <b>${esc(st.present[0])}</b>`;
      case "partial": return `presente in ${st.present.length} di ${st.present.length + st.missing.length} · manca in <b>${L(st.missing)}</b>` + (st.variants > 1 ? ` · testi diversi (${vars()})` : "");
      case "text": return `presente in tutte, ma con testo diverso: ${vars()}`;
      case "check": return `presente in tutte; testo non verificabile in ${L(st.unk)}`;
      default: return "una sola configurazione mostrata: scegline altre per il confronto";
    }
  },
  reqMatrix(d, o) {
    if (!d.reqs.length) return `<div class="xnone">Nessun requisito nel foglio «Requisiti» per questa funzione.</div>`;
    const cf = d.configs, base = d.base;
    const st = new Map(d.reqs.map(r => [r.id, this.reqStatus(r, cf, base)]));
    const cnt = {all: d.reqs.length, match: 0, nm: 0, only: 0, partial: 0, text: 0, check: 0, single: 0};
    for (const x of st.values()) { cnt[x.s]++; if (["only", "partial", "text"].includes(x.s)) cnt.nm++; }
    const rows = this.reqRows(d, o, st);
    const allOpen = rows.length && rows.every(r => o.open.includes(r.id));
    const baseIn = cf.includes(base);
    const cover = cf.map(c => {
      const pres = d.reqs.filter(r => r.cells[c]).length, alone = [...st.values()].filter(x => x.s === "only" && x.present[0] === c).length;
      return `<span class="cvg" style="--cc:${cfgColor(c)}" title="${esc(c)}: ${pres} requisiti su ${d.reqs.length}${alone ? `, ${alone} presenti solo qui` : ""}"><span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span> ${pres}${alone ? ` <small>(${alone} solo qui)</small>` : ""}</span>`;
    }).join("");
    const btn = (v, label, n, cls = "") => `<button data-v="${v}" class="${o.rf === v ? "on" : ""} ${cls}" ${n || v === "all" ? "" : "disabled"}>${label} <span class="n">${n}</span></button>`;
    return `<div class="rqsum">
        <div class="rqcover"><b>${cf.length > 1 ? `Confronto fra ${cf.length} configurazioni` : "Configurazione"}:</b> ${cover}</div>
        <div class="rqref">${baseIn ? `★ Riferimento: <b>${esc(base)}</b> (configurazione base). Se un requisito non è in ${esc(base)}, il riferimento è la prima configurazione che lo contiene (☆).`
          : `⚠️ <b>${esc(base)}</b> non è fra le configurazioni mostrate: per ogni requisito il riferimento (☆) è la prima configurazione che lo contiene, e l'esito vale comunque fra le configurazioni scelte.`}</div></div>
      <div class="rqbar"><div class="seg small" data-dact="rf">
        ${btn("all", "Tutti", cnt.all)}${cf.length > 1 ? btn("match", "✔ MATCHED", cnt.match, "okb") + btn("nm", "✖ NOT MATCHED", cnt.nm, "badb") : ""}</div>
        ${cf.length > 1 ? `<div class="seg small" data-dact="rf" title="Dettaglio dei NOT MATCHED">
          ${btn("only", "① solo in una", cnt.only)}${btn("partial", "◐ manca in alcune", cnt.partial)}${btn("text", "≠ testo diverso", cnt.text)}${cnt.check ? btn("check", "? da verificare", cnt.check) : ""}</div>` : ""}
        <div class="search small"><span class="sicon">🔎</span><input data-dact="rq" type="search" placeholder="Filtra requisiti (ID o testo)…" value="${esc(o.rq || "")}"></div>
        <button class="btn small" data-dact="openall">${allOpen ? "▴ Comprimi tutti" : "▾ Espandi tutti"}</button></div>
      <details class="rqlegend"${LS.get("rqleg", "1") === "1" ? " open" : ""}><summary>Come leggere la tabella</summary><div class="rqlg">
        <div><span class="rqs match">✔ MATCHED</span> il requisito c'è in <b>tutte</b> le configurazioni mostrate con lo <b>stesso testo</b>.</div>
        <div><span class="rqs only">✖ NOT MATCHED</span> <i>solo in una</i>: c'è in una sola configurazione.</div>
        <div><span class="rqs partial">✖ NOT MATCHED</span> <i>manca in alcune</i>: condiviso da una parte delle configurazioni (anche se è la maggioranza).</div>
        <div><span class="rqs text">✖ NOT MATCHED</span> <i>testo diverso</i>: c'è in tutte, ma alcune configurazioni hanno un testo diverso.</div>
        <div class="cells"><span class="rk ref">★</span> riferimento ${esc(base)} · <span class="rk ref alt">☆</span> riferimento sostitutivo (${esc(base)} assente) · <span class="rk eq">=</span> stesso testo del riferimento ·
          <span class="rk diff">≠B</span> testo diverso (le configurazioni con la stessa lettera A, B, C… hanno lo stesso testo) · <span class="rk miss">✖</span> requisito assente · <span class="rk unk">?</span> testo non verificabile</div></div></details>
      <div class="tx info small">👆 Clicca su un requisito per leggere affiancati i testi delle configurazioni (per i testi diversi, sotto il testo trovi spiegate in italiano le differenze di concetto rispetto al riferimento): il dettaglio si apre sotto la riga e i requisiti restano al loro posto. Clicca di nuovo per richiuderlo; puoi tenerne aperti più di uno.</div>
      <div class="tblwrap"><table class="mtx rqt"><thead><tr><th>Requisito e Description</th><th>Esito</th>${cf.map(c => `<th class="c"><span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span></th>`).join("")}</tr></thead>
      <tbody>${rows.map(r => this.reqRowHTML(r, d, o, st.get(r.id))).join("") || `<tr><td colspan="${cf.length + 2}" class="xnone">Nessun requisito con questi filtri.</td></tr>`}</tbody></table></div>`;
  },
  reqRows(d, o, st) {
    const q = (o.rq || "").toLowerCase();
    const want = s => o.rf === "all" || o.rf === s || (o.rf === "nm" && ["only", "partial", "text"].includes(s));
    return d.reqs.filter(r => want(st.get(r.id).s) && (!q || (r.id + " " + st.get(r.id).groups.join(" ")).toLowerCase().includes(q)));
  },
  reqRowHTML(r, d, o, st) {
    const cf = d.configs, open = o.open.includes(r.id);
    const lab = {match: ["✔ MATCHED", "match"], only: ["✖ NOT MATCHED", "only"], partial: ["✖ NOT MATCHED", "partial"], text: ["✖ NOT MATCHED", "text"],
                 check: ["? DA VERIFICARE", "check"], single: ["• PRESENTE", "single"]}[st.s];
    const sub = st.variants > 1 && st.ref ? `<span class="vtag">testo ${st.letters[r.cells[st.ref].g] || "A"} · ${esc(st.ref)}</span>` : "";
    return `<tr class="rqrow${open ? " open" : ""} s-${st.s}" data-rid="${esc(r.id)}"><td class="rq"><span class="caret">${open ? "▾" : "▸"}</span><b>${esc(r.id)}</b>
        <div class="rqd">${sub}${st.text ? glossify(esc(st.text)) : `<i class="muted">Description non disponibile nel file Excel: apri il requisito per le note.</i>`}</div></td>
      <td class="est"><span class="rqs ${lab[1]}">${lab[0]}</span><div class="why">${this.reqWhy(st)}</div></td>${cf.map(c => {
        const x = r.cells[c];
        if (!x) return `<td class="c miss" title="${esc(c)}: requisito assente"><span class="rk miss">✖</span></td>`;
        if (x.g < 0) return `<td class="c" title="${esc(c)}: presente, testo non verificabile"><span class="rk unk">?</span></td>`;
        const L = st.letters[x.g], same = st.ref && r.cells[st.ref] && r.cells[st.ref].g === x.g, multi = st.variants > 1;
        if (c === st.ref) return `<td class="c" title="${esc(c)}: ${st.refIsBase ? "riferimento (configurazione base)" : "riferimento sostitutivo: la configurazione base non lo contiene o non è mostrata"}"><span class="rk ref${st.refIsBase ? "" : " alt"}">${st.refIsBase ? "★" : "☆"}${multi ? L : ""}</span></td>`;
        return same ? `<td class="c" title="${esc(c)}: stesso testo del riferimento ${esc(st.ref)}"><span class="rk eq">=${multi ? L : ""}</span></td>`
          : `<td class="c" title="${esc(c)}: testo ${L} diverso dal riferimento ${esc(st.ref)}"><span class="rk diff">≠${L}</span></td>`;
      }).join("")}</tr>${open ? this.reqOpenHTML(r, d, st) : ""}`;
  },
  reqOpenHTML(r, d, st) {
    return `<tr class="rqx" data-for="${esc(r.id)}"><td colspan="${d.configs.length + 2}">${this.reqTexts(r, d, st)}</td></tr>`;
  },
  reqTexts(r, d, st) {
    st = st || this.reqStatus(r, d.configs, d.base);
    const refTxt = st.text;
    const cards = Object.entries(st.byVar).sort((a, b) => a[0].localeCompare(b[0])).map(([L, cs]) => {
      const x0 = r.cells[cs[0]];
      const txt = L === "?" ? (x0.d || "") : st.groups[x0.g] || "";
      const isRef = cs.includes(st.ref);
      const main = !txt ? `<i class="muted">Testo del requisito non presente nel file Excel per ${esc(cs.join(", "))}.</i>` : glossify(esc(txt));
      // spiegazione A LIVELLO DI CONCETTO della differenza rispetto al riferimento (nessuna parola evidenziata)
      const refG = st.ref && r.cells[st.ref] ? r.cells[st.ref].g : null, g = x0.g, full = r.full || r, gd = full.gd || {};
      let why = !isRef && L !== "?" && refTxt && txt && refG != null && g != null && g !== refG
        ? gd[Math.min(refG, g) + "-" + Math.max(refG, g)] || "" : "";
      if (why && full.gn) {      // nella spiegazione solo le configurazioni mostrate
        const shown = k => Object.keys(r.cells).filter(c => r.cells[c].g === k).join(", ");
        const ph = [[full.gn[refG], shown(refG)], [full.gn[g], shown(g)]].filter(([a, b]) => a && b && a !== b).sort((p, q) => q[0].length - p[0].length);
        ph.forEach(([a], i) => { why = why.split(a).join("\u0000" + i + "\u0000"); });
        ph.forEach(([, b], i) => { why = why.split("\u0000" + i + "\u0000").join(b); });
      }
      const diffSec = why ? `<div class="rqdiff"><b>Differenze nel testo del requisito</b><div>${esc(why).replace(/\n/g, "<br>")}</div></div>` : "";
      const notes = cs.filter(c => r.cells[c].t).map(c => `<div class="rqsec"><b>${esc(c)}</b> — ${glossify(esc(r.cells[c].t)).replace(/\n/g, "<br>")}</div>`).join("");
      const head = L === "?" ? `<span class="rk unk">?</span> <small>testo non verificabile</small>`
        : `<span class="rk ${isRef ? "ref" + (st.refIsBase ? "" : " alt") : "diff"}">${isRef ? (st.refIsBase ? "★" : "☆") : "≠"}${st.variants > 1 ? L : ""}</span> <small>${isRef ? (st.variants > 1 ? `Testo ${L} — riferimento` : "Testo del requisito") : `Testo ${L} — diverso dal riferimento ${esc(st.ref)}`}</small>`;
      return `<div class="rqcard" style="--cc:${cfgColor(cs[0])}"><div class="rqh">${head}</div>
        <div class="rqcf">${cs.map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}${c === st.ref ? (st.refIsBase ? " ★" : " ☆") : ""}</span>`).join("")}</div>
        <div class="rqdesc">${main}</div>${diffSec}${notes}</div>`;
    });
    if (st.missing.length) cards.push(`<div class="rqcard miss"><div class="rqh"><span class="rk miss">✖</span> <small>Requisito assente</small></div>
      <div class="rqcf">${st.missing.map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`).join("")}</div>
      <div class="rqdesc muted">Nel foglio «Requisiti» queste configurazioni non hanno il requisito ${esc(r.id)} per la funzione.</div></div>`);
    return `<div class="rqtexts" style="grid-template-columns:repeat(${Math.min(cards.length, 3)},minmax(0,1fr))">${cards.join("")}</div>`;
  },
  /* apre / chiude il requisito SENZA ridisegnare il pannello e SENZA scorrere: i requisiti restano al loro posto */
  toggleReq(fid, row) {
    const o = this.dopt[fid], id = row.dataset.rid, wrap = row.closest(".tblwrap");
    const keepTop = wrap ? wrap.scrollTop : 0, keepX = window.scrollX, keepY = window.scrollY;
    const open = !o.open.includes(id);
    o.open = open ? [...o.open, id] : o.open.filter(x => x !== id);
    const nx = row.nextElementSibling;
    if (nx && nx.classList.contains("rqx")) nx.remove();
    row.classList.toggle("open", open);
    const caret = $(".caret", row); if (caret) caret.textContent = open ? "▾" : "▸";
    if (open) {
      const d = this.subset(this.details[fid], o.all ? [] : this.sel.cfg);
      const r = d.reqs.find(x => x.id === id);
      if (r) row.insertAdjacentHTML("afterend", this.reqOpenHTML(r, d, this.reqStatus(r, d.configs, d.base)));
    }
    // nessuno scorrimento: la riga cliccata resta esattamente dov'era
    if (wrap) wrap.scrollTop = keepTop;
    window.scrollTo(keepX, keepY);
  },

  detailEvent(e, panel) {
    const fid = panel.dataset.fid, o = this.dopt[fid], t = e.target;
    const tab = t.closest("[data-tab]");
    if (tab) { o.tab = tab.dataset.tab; LS.set("xtab", o.tab); return this.fillDetail(fid); }
    const segb = t.closest(".seg button");
    if (segb) {
      const kind = segb.parentElement.dataset.dact;
      if (kind === "scope") o.all = segb.dataset.v === "all";
      if (kind === "rf") o.rf = segb.dataset.v;
      if (kind === "cols") o.cols = +segb.dataset.v;
      return this.fillDetail(fid);
    }
    const rm = t.closest("[data-rmdoc]");
    if (rm) { o.add = (o.add || []).filter(a => a.cfg + "|" + a.doc !== rm.dataset.rmdoc); return this.fillDetail(fid); }
    const pgt = t.closest("[data-pgt]");
    if (pgt) { const k = pgt.dataset.pgt; o.hide = o.hide.includes(k) ? o.hide.filter(x => x !== k) : [...o.hide, k]; return this.fillDetail(fid); }
    const pn = t.closest("[data-pnav]");
    if (pn) { const col = pn.closest(".pdfcol"); return this.pdfGo(col, o, (o.pg[col.dataset.key] || +col.dataset.first) + +pn.dataset.pnav); }
    const row = t.closest(".rqrow");
    if (row) return this.toggleReq(fid, row);
    if (t.closest(".rqlegend summary")) { setTimeout(() => { const dl = t.closest(".rqlegend"); LS.set("rqleg", dl && dl.open ? "1" : "0"); }, 0); return; }
    const a = t.closest("[data-dact]");
    if (!a || a.tagName === "INPUT") return;
    const act = a.dataset.dact;
    if (act === "close") { this.sel.fn = this.sel.fn.filter(x => x !== fid); this.save(); this.render(); }
    else if (act === "ask") { showView("ask"); Ask.prefill(`Come funziona la funzione ${fid} per tutte le configurazioni del treno?`); }
    else if (act === "fs") { const w = $(".pdfwrap", panel); if (document.fullscreenElement) document.exitFullscreen(); else if (w && w.requestFullscreen) w.requestFullscreen(); }
    else if (act === "pgreset") { o.pg = {}; this.fillDetail(fid); }
    else if (act === "openall") {
      const full = this.details[fid], d = this.subset(full, o.all ? [] : this.sel.cfg);
      const st = new Map(d.reqs.map(r => [r.id, this.reqStatus(r, d.configs, d.base)]));
      const ids = this.reqRows(d, o, st).map(r => r.id);
      o.open = ids.every(i => o.open.includes(i)) ? [] : ids;
      this.fillDetail(fid);
    }
  },
};

const RKIND = {ref: ["★", "ref", "Riferimento (testo del requisito)"], eq: ["=", "eq", "Uguale alla base (MATCHED)"], diff: ["≠", "diff", "Testo diverso (FOUND DIFF)"],
               only: ["➕", "only", "Presente solo qui (manca nella base)"], unk: ["?", "unk", "Valore non classificato"],
               miss: ["✖", "miss", "Requisito assente"]};
const reqDesc = t => String(t || "").replace(/\r/g, "").split(/\n?—{5,}\n?/)[0].replace(/^[\s\S]*?Description\s*:\s*/i, "").trim();

function cssId(s) { return String(s).replace(/[^\w-]/g, "_"); }

/* ── eventi ── */
(() => {
  const X = window.Explorer;
  $("#xWrap").addEventListener("click", e => {
    const t = e.target;
    const panel = t.closest(".dpanel");
    if (panel) {
      if (t.closest("a[href]") && !t.closest("[data-pdf],[data-pages]")) return;
      if (t.closest("[data-pdf],[data-pages]")) {
        const p = t.closest("[data-pdf]"); if (p) return Modal.pdf(p.dataset.pdf, +p.dataset.page, p.dataset.title);
        const g = t.closest("[data-pages]"); return Modal.pages(g.dataset.pages, +g.dataset.first, +g.dataset.last, g.dataset.title);
      }
      return X.detailEvent(e, panel);
    }
    const cp = t.closest("[data-cpdf]"); if (cp) return Modal.pdf(cp.dataset.cpdf, 1, cp.dataset.title);
    const xs = t.closest(".xconf > summary"); if (xs) { setTimeout(() => LS.set("xconf", xs.parentElement.open ? "1" : "0"), 0); return; }
    if (t.closest(".xconf")) return;
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
  $("#xWrap").addEventListener("change", e => {
    const sel = e.target.closest("[data-adddoc]");
    if (sel) {
      const fid = sel.closest(".dpanel").dataset.fid, o = X.dopt[fid], v = sel.value;
      if (!v) return;
      const i = v.indexOf("|");
      (o.add = o.add || []).push({cfg: v.slice(0, i), doc: v.slice(i + 1)});
      o.tab = "pdf";
      return X.fillDetail(fid);
    }
    const i = e.target.closest("[data-pgo]"); if (!i) return;
    const col = i.closest(".pdfcol"), fid = i.closest(".dpanel").dataset.fid;
    X.pdfGo(col, X.dopt[fid], +i.value);
  });
  $("#xWrap").addEventListener("input", e => {
    const i = e.target.closest("[data-dact=rq]"); if (!i) return;
    const fid = i.closest(".dpanel").dataset.fid;
    X.dopt[fid].rq = i.value;
    X.dopt[fid].open = [];
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
  $("#xReset").onclick = () => { X.reset(); X.save(); };
  $("#xCrumbs").onclick = e => {
    const b = e.target.closest("[data-cr]"); if (!b) return;
    const k = b.dataset.cr;
    if (k === "top") { X.sel = {cfg: [], doc: [], fn: []}; X.save(); X.render(); $("#xScroll").scrollTo({top: 0, behavior: "smooth"}); return; }
    const el = $({cfg: "#xl-cfg", doc: "#xl-doc", fn: "#xl-fn"}[k] || "#xl-det");
    if (el) el.scrollIntoView({behavior: "smooth", block: "start"});
  };
})();
