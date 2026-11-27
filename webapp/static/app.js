/* AskTrainMind Web — interfaccia (JS puro, nessuna dipendenza esterna).
   Funziona in due modi:
   • OFFLINE (utente): User/AskTrainMind.html con i dati incorporati in window.ATM_STATIC,
     apribile con doppio click, senza Python né server;
   • SERVER (developer): anteprima live con python asktrainmind_web.py (API /api/...). */
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
const APP = {meta: null, key: "", colors: {}, view: "explore", functions: [], configs: [], gloss: [], know: null};

/* ── Sorgente dei dati: pagina offline (ATM_STATIC) oppure server del developer ── */
const STATIC = window.ATM_STATIC || null;
/* Pagina utente, da dove si mostrano i PDF (meta.pdf):
   "relative" → percorsi DOC_FLOTTE/<config>/CONFIG/<tipo>/<file> relativi alla pagina, che sta nella
                cartella SharePoint (sincronizzata con OneDrive) che contiene DOC_FLOTTE;
   "local"    → cartella «docs» accanto alla pagina (docs/_atm_docs.js imposta window.ATM_DOCS);
                senza la cartella restano i link SharePoint del file Excel in una nuova scheda
                (SharePoint non si lascia incorporare in una pagina aperta dal PC). */
const PDFSRC = STATIC && STATIC.meta ? (STATIC.meta.pdf || "local") : "";
if (PDFSRC === "local" && !window.ATM_DOCS) {
  for (const d of Object.values(STATIC.details || {}))
    for (const k of d.cards || []) for (const r of [k.ref, ...(k.links || [])]) if (r) { r.fid = ""; r.local = false; }
  for (const items of Object.values((STATIC.tree || {}).confdocs || {})) for (const x of items) { x.fid = ""; x.local = false; }
}
const DS = {
  static: !!STATIC,
  sharepoint: PDFSRC === "sharepoint" || (PDFSRC === "local" && !window.ATM_DOCS),
  nodocs: PDFSRC === "local" && !window.ATM_DOCS,
  relative: PDFSRC === "relative",
  docroot: (STATIC && STATIC.meta && STATIC.meta.docroot) || "DOC_FLOTTE",
  spUrl(fid, page) { const h = STATIC && fid ? (STATIC.spurls || {})[fid] : ""; return h ? spDirect(h) + (page ? "#page=" + page : "") : ""; },
  fileUrl(fid, page) {
    if (STATIC) {
      const h = (DS.nodocs ? (STATIC.spurls || {}) : (STATIC.files || {}))[fid];
      return h ? (/^https?:/i.test(h) ? spDirect(h) : h) + (page ? "#page=" + page : "") : "";
    }
    return `/api/file/${fid}` + (page ? `#page=${page}` : "");
  },
  async meta() { return STATIC ? STATIC.meta : api("/api/meta"); },
  async tree() { return STATIC ? STATIC.tree : api("/api/explorer"); },
  async func(fid) {
    if (STATIC) { const d = STATIC.details[fid]; if (!d) throw new Error("Funzione non trovata: " + fid); return d; }
    return api(`/api/explorer/func?fid=${encodeURIComponent(fid)}`);
  },
  async suggestions() { return STATIC ? STATIC.suggestions : api("/api/suggestions"); },
  async guide() { return STATIC ? STATIC.guide : (await fetch("/api/guide")).text(); },
  async knowledge() { return STATIC ? STATIC.knowledge : api("/api/knowledge"); },
  async ask(q, docs) { return STATIC ? Offline.ask(q) : api("/api/ask", {json: {q, docs}}); },
};
if (DS.static) document.documentElement.classList.add("static");

function cfgColor(c) { return APP.colors[c] || "#8a94a6"; }

/* ── Navigazione ───────────────────────────────────────────────────── */
function showView(v) {
  APP.view = v;
  $$("#mainTabs button").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  $$(".view").forEach(s => s.classList.toggle("active", s.id === "view-" + v));
  if (v === "ask") Ask.init();
  if (v === "explore" && window.Explorer) Explorer.open();
  if (v === "guide") Guide.open();
  // nelle anteprime web (SharePoint/OneDrive, allegati, iframe «about:srcdoc») la History API è bloccata
  if (!inPreview()) try { history.replaceState(null, "", "#" + v); } catch (e) { /* la navigazione funziona lo stesso */ }
}
$("#mainTabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b) showView(b.dataset.view); });
window.addEventListener("hashchange", () => {
  const v = location.hash.slice(1);
  if (v !== APP.view && $("#view-" + v) && !$(`#mainTabs [data-view="${v}"]`)?.hidden) showView(v);
});

/* ── Modal (PDF / immagini) ────────────────────────────────────────── */
const Modal = {
  pdf(fid, page, title) {
    const url = DS.fileUrl(fid, page || 1);
    if (!url) return toast("PDF non disponibile in questa copia", "bad");
    // SharePoint non si lascia incorporare in un riquadro: si apre in una nuova scheda
    if (/^https?:/i.test(url) && DS.static) { window.open(url, "_blank", "noopener"); return; }
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
    if (DS.static) return this.pdf(fid, first, title);
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
document.addEventListener("mousedown", e => { if (!Popup.el.hidden && !Popup.el.contains(e.target) && !e.target.closest("abbr.gl")) Popup.close(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") { Popup.close(); Modal.close(); } });


/* ════════════════════════════════════════════════════════════════════
   Componenti condivisi (Esplora + Chiedi)
   ════════════════════════════════════════════════════════════════════ */
const STATE_UI = {
  b: {icon: "★", cls: "st-b", label: "Riferimento (descrizione propria)"},
  g: {icon: "✔", cls: "st-g", label: "Simile alla base (verde, ≥ 80 %)"},
  o: {icon: "≈", cls: "st-o", label: "Differenze moderate (arancione, 50–80 %)"},
  r: {icon: "≠", cls: "st-r", label: "Differenze rilevanti (rosso, < 50 %)"},
  l: {icon: "○", cls: "st-l", label: "Collegata, non ancora analizzata"},
  x: {icon: "⚠", cls: "st-x", label: "Documento non disponibile (link da inserire o da verificare)"},
  "": {icon: "–", cls: "st-n", label: "Non trattata"},
};
const pagesTxt = r => r.first ? (r.last && r.last !== r.first ? `pagg. ${r.first}–${r.last}` : `pag. ${r.first}`) : (r.page ? `pag. ${r.page}` : "");

/* Un solo pulsante principale per documento (+ icone secondarie) */
/* Indirizzo del PDF per il riquadro: file locale (developer) oppure link SharePoint del file Excel,
   trasformato nel percorso diretto del file (il browser lo mostra alla pagina indicata) */
function spDirect(u) { return (u || "").split("#")[0].replace(/^(https?:\/\/[^/]+)\/:[a-z]:\/[rsg]\//i, "$1/"); }
function pdfSrc(r, page) {
  if (r.fid) return DS.fileUrl(r.fid, page);
  return r.url ? spDirect(r.url) + (page ? "#page=" + page : "") : "";
}

function refButtons(r, title) {
  if (!r) return "";
  const t = esc(title || `${r.doc} — ${(r.configs || [r.config]).join(", ")}`);
  const pg = r.first || r.page || 1;
  let h = "";
  if (r.fid) h += `<button class="btn primary small" data-pdf="${r.fid}" data-page="${pg}" data-title="${t}" title="Apri il PDF del computer alla pagina in cui è trattata la funzione">📄 Apri ${pagesTxt(r) ? "a " + pagesTxt(r) : ""}</button>`;
  else if (r.url) h += `<a class="btn primary small" href="${esc(r.url)}" target="_blank" rel="noopener" title="${DS.sharepoint ? "Apre il PDF su SharePoint (link del file Excel)" : "Il PDF non è sul computer: si apre SharePoint"}">🌐 Apri su SharePoint${DS.sharepoint && pagesTxt(r) ? " a " + pagesTxt(r) : ""}</a>`;
  if (r.fid && r.first && r.last && r.last > r.first && !DS.static) h += `<button class="btn icon small" data-pages="${r.fid}" data-first="${r.first}" data-last="${r.last}" data-title="${t} — ${pagesTxt(r)}" title="Sfoglia le pagine della funzione come immagini">🖼</button>`;
  if (r.fid && r.url) h += `<a class="btn icon small" href="${esc(r.url)}" target="_blank" rel="noopener" title="Apri su SharePoint">🌐</a>`;
  return h;
}

/* Elenco documenti compatto: configurazioni con lo stesso file/pagine raggruppate */
function docListHTML(items) {
  return `<div class="doclist">${items.map(d => `<div class="docrow">
    <div class="dl-ico">${d.local ? "📄" : "🌐"}</div>
    <div class="dl-main"><b>${esc(d.doc)}</b> <span class="code">${esc(d.code || "")}</span> <span class="pg">${pagesTxt(d)}</span>
      <div class="dl-cfgs">${(d.configs || [d.config]).map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`).join("")}${d.local || DS.sharepoint ? "" : `<span class="badge warn" title="PDF non trovato nelle cartelle del computer">solo SharePoint</span>`}</div></div>
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
    return t ? `${pre}<abbr class="gl${t.status === "proposto" ? " prop" : ""}" data-term="${esc(t.term)}" title="🧠 ${esc(t.term)}: ${esc(t.meaning)} (clic per la scheda)">${w}</abbr>` : m;
  })).join("");
}
async function loadGlossary() {
  try { const k = await DS.knowledge(); APP.know = k; APP.gloss = k.terms || []; APP.glossCats = k.categories || {}; } catch {}
}
const normTerm = t => String(t || "").trim().replace(/\s+/g, " ").toUpperCase();
function findTerm(w) {
  const n = normTerm(w);
  return (APP.gloss || []).find(t => normTerm(t.term) === n || (t.aliases || []).some(a => normTerm(a) === n));
}
/* Scheda di un concetto appreso (come knowledge.term_markdown) */
function termMD(t, withPassages = true) {
  const K = APP.know || {}, C = K.categories || {}, R = K.relations || {}, F = K.facts || {};
  const cat = C[t.category] || "";
  const out = [`**${t.term}**${cat ? ` — *${cat}*` : ""}${(t.aliases || []).length ? ` (anche: ${t.aliases.join(", ")})` : ""}`, "", t.meaning || ""];
  if (t.status === "proposto") out.push("> ⚠️ Significato ricavato dai documenti, non ancora confermato dal developer.");
  if (t.details) out.push("", t.details);
  const lines = [];
  for (const [k, lab] of Object.entries(F)) if ((t.facts || {})[k]) lines.push(`- **${lab}:** ${t.facts[k]}`);
  for (const [k, lab] of Object.entries(R)) if (((t.relations || {})[k] || []).length) lines.push(`- **${lab}:** ${t.relations[k].join(", ")}`);
  for (const [c, v] of Object.entries(t.configs || {})) if (v) lines.push(`- **${c}:** ${v}`);
  if (lines.length) out.push("", ...lines);
  if (t.notes) out.push("", `*Note:* ${t.notes}`);
  const ans = (t.answers || []).filter(a => a.a).slice(-4);
  if (ans.length) out.push("", "💬 Spiegazioni dell'esperto:", ...ans.map(a => `- *${a.q || ""}* — ${a.a.split(/\s+/).join(" ").slice(0, 500)}`));
  const ps = withPassages ? ((K.passages || {})[normTerm(t.term)] || []).slice(0, 3) : [];
  if (ps.length) out.push("", "Dai documenti tecnici:", ...ps.map(p => `> ${p.text.slice(0, 300)} — *${p.source}${p.page ? ", pag. " + p.page : ""}*`));
  return out.join("\n").trim();
}
function termPopup(term, ev) {
  const t = findTerm(term); if (!t) return;
  const fs = (t.funcs || []).slice(0, 8);
  Popup.open(ev.clientX, ev.clientY + 12, `<div class="popt md termpop">${md(termMD(t))}${fs.length ? `<div class="blk-title">Funzioni che ne parlano</div><div class="chips">${fs.map(f => `<button class="chip" data-xfn="${esc(f)}"><b>${esc(f)}</b></button>`).join("")}</div>` : ""}</div>`, 480);
}
document.addEventListener("click", e => {
  const a = e.target.closest("abbr.gl");
  if (a) { e.preventDefault(); e.stopPropagation(); return termPopup(a.dataset.term, e); }
  const x = e.target.closest("[data-xfn]");
  if (x) { e.preventDefault(); e.stopPropagation(); Popup.close(); window.Explorer && Explorer.focusFunction(x.dataset.xfn); }
}, true);

/* Blocco "configurazione" (usato in Esplora e nelle risposte "tutte le configurazioni") */
function cfgCardHTML(k, base, opt = {}) {
  const st = STATE_UI[k.state || ""] || STATE_UI[""];
  const sim = k.sim != null ? Math.round(k.sim * 10) / 10 : null;
  let body;
  if (k.linkIssue) {
    body = `<div class="cc-linkissue" title="${k.linkIssue === "missing" ? "Nessun link al documento nel foglio Funzioni per questa configurazione" : "Il link c'è ma non porta a nessun documento: verificalo nel foglio Funzioni"}">${esc(k.linkMsg || (k.linkIssue === "missing" ? "LINK DOCUMENTALE NON INSERITO" : "RICHIESTO CHECK LINK, DOCUMENTO NON TROVATO"))}</div>
      <div class="ref-note muted">Configurazione esclusa dal confronto con le altre.</div>`;
  } else if (k.reference) {
    body = `<div class="ref-note">Variante di <b>${esc(base)}</b>${sim != null ? ` — similarità funzionale <b>${sim}%</b>` : ""}.
      ${k.diffs && k.diffs.length ? "" : k.extra && k.extra.length ? "Le differenze sono descritte qui sotto." : "Il funzionamento è quello della configurazione di riferimento."}</div>`
      + (k.diffs && k.diffs.length ? `<div class="cc-majordiff"><b>Differenze rilevanti rispetto a ${esc(base)}</b><ul>${k.diffs.map(d => `<li>${glossify(esc(d))}</li>`).join("")}</ul></div>` : "");
  } else if (k.text) body = `<div class="cc-text">${glossify(md(k.text))}</div>`;
  else body = `<div class="ref-note muted">Nessuna sintesi «Funzioni AI» per questa configurazione.</div>`;
  // Blocchi nell'ordine del foglio Funzioni: ogni link (pulsante) è seguito dai campi che gli stanno sotto
  // (Funzioni AI, «Approfondimenti…», «Componenti circuito…» ecc.)
  const extraHTML = xs => xs.map(x => `<details class="cc-extra"${opt.openExtra ? " open" : ""}><summary>${/approf/i.test(x.label) ? "📝" : /component/i.test(x.label) ? "🔌" : /descriz/i.test(x.label) ? "📐" : "🗒"} ${esc(x.label)} <small>${esc(x.doc)}</small></summary><div class="md">${glossify(md(x.text))}</div></details>`).join("");
  const byDoc = new Map();
  for (const x of k.extra || []) { if (!byDoc.has(x.doc)) byDoc.set(x.doc, []); byDoc.get(x.doc).push(x); }
  const links = new Map((k.links || []).map(r => [r.doc, r]));
  const mainDoc = k.doc || (k.ref && k.ref.doc) || "";
  const idx = k.index ? ` · <span class="badge ${/^MATCHED/i.test(k.index) ? "ok" : /NOT/i.test(k.index) ? "bad" : ""}" title="Esito in Index Funzioni">${esc(k.index)}</span>` : "";
  const mainHTML = () => (k.linkIssue && !k.ref ? "" : `<div class="cc-doc">${k.ref ? `<span>📄 <b>${esc(k.ref.doc)}</b> <span class="code">${esc(k.ref.code || "")}</span> ${pagesTxt(k.ref)}${idx}</span><span class="spacer"></span>${refButtons(k.ref, `${k.ref.doc} — ${k.config}`)}` : k.linkIssue ? "" : `<span class="muted">Nessun documento collegato</span>${idx}`}</div>`)
    + same + body + extraHTML(byDoc.get(mainDoc) || []);
  const linkHTML = r => `<div class="cc-link">📎 <b>${esc(r.doc)}</b> <span class="code">${esc(r.code || "")}</span> ${pagesTxt(r)} <span class="spacer"></span>${refButtons(r, `${r.doc} — ${k.config}`)}</div>`;
  const invalidHTML = doc => `<div class="cc-invalid" title="Documento aggiornato nel foglio CONFIG: il riferimento di pagina va reinserito nel foglio Funzioni (cella con la X rossa)">✖ <b>${esc(doc)}</b>: documento aggiornato, riferimento di pagina da verificare — PDF non mostrato</div>`;
  const trains = k.trains && k.trains.length ? `<details class="cc-trains"><summary title="Treni (veicoli) con questa configurazione, dal foglio Flotte">🚆 ${k.trains.length} treni${k.fleet ? " · " + esc(k.fleet) : ""}</summary><div>${k.trains.map(t => `<span class="tn">${esc(t)}</span>`).join("")}</div></details>` : "";
  const same = k.sameDoc && k.sameDoc.length ? `<div class="cc-same" title="Configurazioni che usano lo stesso documento e le stesse pagine">🔗 stesso documento di ${k.sameDoc.map(c => `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`).join(" ")}</div>` : "";
  const gauge = sim != null ? `<div class="gauge" title="Similarità con ${esc(base)}: ${sim}%"><i style="width:${Math.max(3, Math.min(100, sim))}%"></i></div>` : "";
  const done = new Set();
  let blocks = "";
  const block = doc => {
    if (done.has(doc)) return;
    done.add(doc);
    if (doc === mainDoc) blocks += mainHTML();
    else if (links.has(doc)) blocks += linkHTML(links.get(doc)) + extraHTML(byDoc.get(doc) || []);
    else if ((k.invalid || []).includes(doc)) blocks += invalidHTML(doc);
    else blocks += extraHTML(byDoc.get(doc) || []);
  };
  if (!(k.order || []).includes(mainDoc)) block(mainDoc);
  for (const doc of k.order || []) block(doc);
  for (const doc of [...links.keys(), ...(k.invalid || []), ...byDoc.keys()]) block(doc);
  return `<div class="ccard ${st.cls}${k.base ? " isbase" : ""}" style="--cc:${cfgColor(k.config)}">
    <div class="cc-head"><span class="cfgb" style="--cc:${cfgColor(k.config)}">${esc(k.config)}</span>
      <span class="stchip ${st.cls}" title="${esc(st.label)}">${st.icon} ${k.base ? "Riferimento" : sim != null ? sim + "%" : esc(st.label.split(" (")[0])}</span></div>
    ${gauge}
    ${blocks}
    ${trains ? `<div class="cc-foot">${trains}</div>` : ""}</div>`;
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
      const s = await DS.suggestions();
      if (!s.items.length && !s.functions.length) return;
      this.ready = true;
      APP.functions = s.functions; APP.configs = s.configs; Object.assign(APP.colors, s.colors || {});
      $("#sugList").innerHTML = s.items.map(q => `<button>${esc(q)}</button>`).join("");
    } catch (e) { toast(e.message, "bad"); }
    this.drawHist();
    this.syncAi();
  },
  syncAi() {
    if (DS.static) return;
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
      const res = await DS.ask(q, !DS.static && $("#optDocs").checked);
      this.renderAnswer(box, res, q);
      if (res.ai && res.aiAvailable && $("#optAi").checked) this.streamAi(box, res.id);
    } catch (e) {
      box.innerHTML = `<div class="tx bad">${esc(e.message)}</div>`;
    } finally { this.busy = false; }
  },
  renderAnswer(box, res, q) {
    let h = `<div class="meta"><span class="badge info">${esc({values: "Valori", define: "Definizione", when: "Condizioni", generic: "Domanda", concept: "Concetto", search: "Ricerca", differences: "Differenze", explain: "Funzionamento", components: "Componenti", documents: "Documenti", figures: "Figure e tabelle", requirements: "Requisiti", overview: "Panoramica"}[res.ask || res.intent] || res.ask || res.intent)}</span>`;
    (res.docs || []).forEach(d => h += `<span class="badge" title="Documento indicato nella domanda">📄 ${esc(d)}</span>`);
    if (res.allConfigs) h += `<span class="badge ok" title="La domanda chiede tutte le configurazioni">🚆 tutte le configurazioni</span>`;
    (res.configs || []).forEach(c => h += `<span class="cfgb" style="--cc:${cfgColor(c)}">${esc(c)}</span>`);
    h += `<span class="spacer"></span><span title="Tempo di risposta">⚡ ${res.cached ? "dalla cache" : (res.ms || 0) + " ms"}</span></div>`;
    if (res.notes && res.notes.length) h += `<div class="notes">Interpretazione: ${res.notes.map(esc).join(" · ")}</div>`;
    if (res.sections && res.sections.length) {
      h += res.sections.map(s => `<section class="ans-sec sec-${esc(s.id)}"><div class="sec-h"><b>${esc(s.title)}</b>${s.sub ? `<small>${esc(s.sub)}</small>` : ""}</div>
        <div class="sec-b">${(s.blocks || []).map(b => this.block(b, q)).join("") || `<div class="tx info">Nessun contenuto.</div>`}</div></section>`).join("");
    } else h += (res.blocks || []).map(b => this.block(b, q)).join("");
    if (res.followups && res.followups.length) h += `<div class="follow"><span>💡 Potresti chiedere anche:</span>${[...new Set(res.followups)].slice(0, 4).map(f => `<button class="chip" data-q="${esc(f)}">${esc(f)}</button>`).join("")}</div>`;
    if (res.ai && !DS.static) {
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
      case "chips": return `<div>${T}<div class="chips">${b.items.map(c => `<button class="chip" ${b.explore ? `data-xfn="${esc(c.fid)}" title="Apri in Esplora"` : `data-q="${esc(q + " (" + c.fid + ")")}"`}><b>${esc(c.label)}</b>${c.desc ? `<small>${esc(c.desc)}</small>` : ""}</button>`).join("")}</div></div>`;
      case "explore": return `<div class="xlinks">${b.items.map(f => `<button class="btn small" data-xfn="${esc(f)}">🧭 Apri ${esc(f)} in Esplora (PDF affiancati e requisiti)</button>`).join("")}</div>`;
      case "unknown": return `<div class="tx info unknown">🤔 Non conosco ancora: ${b.words.map(w => `<b>${esc(w)}</b>`).join(", ")}.
        ${DS.static ? `L'AI di questa copia è aggiornata al <b>${esc((STATIC.meta.exported || ""))}</b>: segnala la domanda al developer per farglielo insegnare.
        <button class="btn small" data-copy="${esc(q)}">⧉ Copia la domanda</button>` : esc(b.note || "")}</div>`;
      case "table": return this.table(b);
      case "cards": return `<div>${T}<div class="cards">${b.items.map(c => this.card(c)).join("")}</div></div>`;
      case "figures": return `<div>${T}<div class="figs">${b.items.map(f => this.fig(f)).join("")}</div></div>`;
      case "docs": return `<div>${T}${docListHTML(b.items)}</div>`;
      case "search": return `<div>${T}${searchHTML(b.groups)}</div>`;
      case "cfgblocks": {
        const tr = b.items.reduce((n, k) => n + (k.trains || []).length, 0);
        return `<div class="cfgblocks"><div class="blk-title">🚆 Configurazioni coinvolte: ${b.items.length}${tr ? ` · ${tr} treni` : ""}
          <span class="legend">${["b", "g", "o", "r", "x"].map(x => `<span class="stchip ${STATE_UI[x].cls}">${STATE_UI[x].icon} ${STATE_UI[x].label}</span>`).join("")}</span></div>
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
  const cp = t.closest("[data-copy]"); if (cp) return copyText(cp.dataset.copy);
  const chip = t.closest(".chip[data-q]"); if (chip) return Ask.send(chip.dataset.q);
  const ai = t.closest("[data-ai]"); if (ai) return Ask.streamAi(ai.closest(".ans"), ai.dataset.ai);
});


/* ════════════════════════════════════════════════════════════════════
   GUIDA
   ════════════════════════════════════════════════════════════════════ */
const Guide = {
  done: false,
  async open() {
    if (this.done) return;
    let text = "";
    try { text = await DS.guide(); } catch (e) { text = "# Guida\n\nGuida non disponibile: " + e.message; }
    const el = $("#guide");
    el.innerHTML = md(text);
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
   Stato dei dati / aggiornamento automatico (solo modalità server)
   ════════════════════════════════════════════════════════════════════ */
function applyMeta(m) {
  APP.meta = m;
  if (m.meta) {
    Object.assign(APP.colors, m.meta.colors || {});
    $("#fileName").textContent = `${m.meta.name} · ${m.meta.mtime}`;
    $("#fileName").title = m.meta.file || "";
  }
}
async function refreshMeta() {
  let m;
  try { m = await api("/api/meta"); }
  catch { setStatus("err", "Anteprima developer non raggiungibile: riavviare python asktrainmind_web.py"); return setTimeout(refreshMeta, 5000); }
  const first = !APP.meta;
  applyMeta(m);
  if (m.error) setStatus("err", m.error);
  else if (!m.ready || m.loading) setStatus("", m.ready ? "Aggiornamento del file in corso…" : "Lettura del file Excel…");
  else setStatus("ok", `Anteprima developer · file del ${m.meta.mtime} · AI: ${m.ai.ok ? "attiva" : "non disponibile"}`);
  if (m.ready && m.key !== APP.key) {
    const changed = !!APP.key;
    APP.key = m.key;
    if (changed) {
      Ask.ready = false;
      toast("Il file Excel è stato aggiornato: dati ricaricati", "ok", 6000);
      if (window.Explorer) Explorer.reset(true);
    }
  }
  setTimeout(refreshMeta, first || !m.ready || m.loading ? 1500 : 5000);
}
function setStatus(kind, text) { $("#status").className = "status " + kind; $("#statusText").textContent = text; $("#status").title = text; }

/* pagina aperta DENTRO un'anteprima web (SharePoint/OneDrive/Teams/Outlook, iframe «about:srcdoc» o blob:) */
function inPreview() {
  const p = location.protocol;
  return p === "blob:" || p === "about:" || p === "data:" || (location.origin === "null" && p !== "file:");
}
function previewWarning() {
  let embedded = false;
  try { embedded = window.top !== window.self; } catch (e) { embedded = true; }
  const p = location.protocol;
  if (!DS.static || !(inPreview() || (embedded && p !== "file:"))) return;
  const d = document.createElement("div");
  d.id = "previewWarn";
  d.innerHTML = `⚠️ <b>Stai vedendo AskTrainMind in un'anteprima web</b> (SharePoint / OneDrive / Teams / Outlook): la pagina funziona, ma l'anteprima può bloccare l'apertura dei link.
    Per usarla al meglio <b>scarica solo il file AskTrainMind.html</b> (su SharePoint: <b>Scarica</b>) e aprilo con <b>doppio clic</b> (Edge o Chrome).
    Non serve la cartella <b>docs</b>: i PDF si aprono da SharePoint con i link del file Excel.`;
  document.body.prepend(d);
}

async function boot() {
  try { previewWarning(); } catch (e) { /* solo un avviso */ }
  const start = (location.hash || "#explore").slice(1);
  if (DS.static) {
    applyMeta(STATIC.meta);
    APP.key = STATIC.meta.key;
    const k = STATIC.knowledge || {};
    setStatus("ok", `Dati del ${STATIC.meta.meta.mtime} · aggiornati il ${STATIC.meta.exported}${(k.terms || []).length ? ` · AI: ${k.terms.length} concetti` : ""}`);
  } else await refreshMeta();
  await loadGlossary();
  showView(["explore", "ask", "guide"].includes(start) ? start : "explore");
}
// errori di avvio (es. API del browser bloccate da un'anteprima web) non devono fermare la pagina
const safeBoot = () => boot().catch(e => { console.warn("AskTrainMind:", e); try { showView("explore"); } catch (e2) { /* ignorato */ } });
// i dati offline sono già incorporati: attendere anche explore.js/offline.js
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", safeBoot); else safeBoot();
window.showView = showView;
