/* AskTrainMind – motore «Chiedi» della pagina OFFLINE (User/AskTrainMind.html).
   Replica in JavaScript la logica deterministica di webapp/qa.py sui dati incorporati
   (window.ATM_STATIC): riconosce funzioni, configurazioni, intento della domanda e i
   concetti appresi dall'AI (glossario addestrato dal developer). Nessun server. */
"use strict";

window.Offline = (() => {
  const STOP = new Set(`il lo la i gli le un uno una di a da in con su per tra fra e o ma che chi cui non come dove
    quando quale quali quanto quanti del dello della dei degli delle al allo alla ai agli alle dal dallo dalla dai dagli
    dalle nel nello nella nei negli nelle sul sullo sulla sui sugli sulle mi ti ci vi si puoi potresti mostrami dimmi
    elenca trova tutte tutti tutto varie vari funzione funzioni configurazione configurazioni relativi relativa relativo
    sono sia anche questo questa quello quella modo semplice livello tecnico tecnica eventuali presenti presente cosa
    cos funziona funzionamento spiega spiegami differenze differenza treno treni base requisiti requisito documenti
    documento pagina pagine loro rispetto`.split(/\s+/));
  const STOP_IT = new Set(`il lo la i gli le un uno una di a da in con su per tra fra del dello della dei degli delle
    al allo alla ai agli alle dal dallo dalla dai dagli dalle nel nello nella nei negli nelle sul sullo sulla sui sugli
    sulle col e ed o od ma se che chi cui non come dove quando quanto quanti quante quale quali cosa cos cose è e' sono
    sia siano era erano essere ha hanno ho hai avere fa fanno fare può possono puo deve devono questo questa questi
    queste quello quella quelli quelle mi ti ci vi si ne lo anche più piu meno molto poco tutto tutti tutte ogni altro
    altri altre stesso stessa già gia ancora poi però pero quindi funziona funzionano funzionamento funzione funzioni
    spiega spiegami spiegare descrivi descrivere dimmi mostra mostrami treno treni configurazione configurazioni base
    differenza differenze differenti diverso diversi uguale uguali requisito requisiti documento documenti pagina
    pagine sistema sistemi elemento elementi coinvolti coinvolto gestisce gestiscono valori valore tipo modo parte
    sul sulla nelle volte costruito costruita costruttore viaggiano viaggia quali sapere vorrei voglio puoi potresti
    dove rispetto tra loro esempio caso casi eventi evento ci sono hanno`.split(/\s+/));
  const ACR_STOP = new Set(`ID AND OR NOT IF THE TBD NA FRS TRS PDF OK ON OFF II III IV VI VII VIII IX XI XII YES NO
    FOR TO OF IN BY AT AS IS BE IT AN ALL ANY SHALL MUST WITH FROM THIS THAT ARE NOTE TABLE FIGURE REV REF DOC PAGE
    MAX MIN NR VZ VZI DE EN IT FR ES DA DI DEL CON PER IL LA LE UN UNA`.split(/\s+/));
  const ASKED = /(?:cos['’]?\s*[eè]|cosa\s+[eè]|che\s+cos['’]?\s*[eè]|cosa\s+significa|cosa\s+vuol\s+dire|significato\s+di|cosa\s+sono|chi\s+[eè]|definizione\s+di|parlami\s+d[ie]l?l?[oa]?)\s+(?:(?:il|lo|la|i|gli|le|un|uno|una|l['’])\s*)?([\w\-/]+(?:\s+[\w\-/]+)?)/gi;
  const ACR = /(?<![\w\-])([A-Z][A-Z0-9]{1,9}(?:[-_/][A-Z0-9]{1,8}){0,2})(?![\w\-])/g;
  const INTENTS = [
    ["documents", /\bdocument|\bpdf\b|\bpagin[ae]\b|\bapri\b|dove .*(trattat|descritt)|\bfigur|\btabell/],
    ["components", /\bcomponent|\bdispositiv|\bapparecchi|\brel[eè]\b|\bsensor|\bhardware|\bhw\b/],
    ["requirements", /requisit/],
    ["differences", /differen|differisc|confront|cambia|variazion|rispetto|diverso|diversi|uguali/],
    ["explain", /come funziona|funzionamento|descriv|spieg|cosa fa|a cosa serve|semplic|tecnic|cos'?\s*[eè]/],
  ];
  const norm = s => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const words = s => (String(s || "").toLowerCase().match(/[a-zà-ù0-9]+/g) || []);

  function ratio(a, b) {           // similarità (come difflib, approssimata con Levenshtein)
    if (a === b) return 1;
    const m = a.length, n = b.length;
    if (!m || !n) return 0;
    let prev = Array.from({length: n + 1}, (_, j) => j);
    for (let i = 1; i <= m; i++) {
      const cur = [i];
      for (let j = 1; j <= n; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      prev = cur;
    }
    return 1 - prev[n] / Math.max(m, n);
  }
  function closest(n, keys, cutoff) {
    let best = null, bs = cutoff;
    for (const k of keys) { if (Math.abs(k.length - n.length) > 6) continue; const r = ratio(n, k); if (r >= bs) { bs = r; best = k; } }
    return best;
  }

  let IDX = null;
  function index() {
    if (IDX) return IDX;
    const S = window.ATM_STATIC, fns = S.tree.funcs;
    const byNorm = {}, fw = {}, df = new Map();
    for (const fid of Object.keys(fns)) {
      byNorm[norm(fid)] = fid;
      const ws = new Set(fid.toLowerCase().split(/[_\W]+/).filter(w => w.length > 2));
      for (const w of words(fns[fid].desc)) if (w.length > 4 && !STOP.has(w) && !["funzio", "garant", "gestir"].includes(w.slice(0, 6))) ws.add(w.slice(0, 6));
      fw[fid] = ws;
      ws.forEach(w => df.set(w, (df.get(w) || 0) + 1));
    }
    const configs = S.tree.configs.map(c => c.name);
    IDX = {byNorm, fw, df, configs, base: S.tree.base, vocab: new Set(S.vocab || [])};
    return IDX;
  }

  function functionsIn(q) {
    const X = index(), found = [], notes = [];
    for (const tok of q.match(/[A-Za-z0-9][A-Za-z0-9_.\-/]{3,}/g) || []) {
      if (!tok.includes("_") && !/[a-z][A-Z]/.test(tok)) continue;
      const n = norm(tok);
      let f = X.byNorm[n];
      if (!f) {
        if (X.configs.some(c => norm(c) === n)) continue;
        const m = closest(n, Object.keys(X.byNorm), 0.82);
        if (!m) continue;
        f = X.byNorm[m];
        notes.push(`«${tok}» interpretato come ${f}`);
      }
      if (!found.includes(f)) found.push(f);
    }
    if (found.length) return {found, notes, ambiguous: []};
    const qw = words(q).filter(w => w.length > 3 && !STOP.has(w));
    if (!qw.length) return {found: [], notes: [], ambiguous: []};
    const scores = {};
    for (const [fid, ws] of Object.entries(X.fw)) {
      let s = 0;
      for (const w of qw) for (const f of ws) {
        if (w === f || (w.length > 4 && (f.startsWith(w.slice(0, -1)) || w.startsWith(f) || w.slice(0, 6) === f))) { s += 1 / (1 + X.df.get(f)); break; }
      }
      if (s) scores[fid] = s;
    }
    const ranked = Object.keys(scores).sort((a, b) => scores[b] - scores[a]);
    if (!ranked.length) return {found: [], notes: [], ambiguous: []};
    const best = scores[ranked[0]], top = ranked.filter(f => scores[f] >= best * 0.999).slice(0, 6);
    if (top.length === 1) return {found: top, notes: [`Funzione individuata dalla descrizione: ${top[0]}`], ambiguous: ranked.slice(1, 6)};
    return {found: [], notes: [], ambiguous: ranked.slice(0, 8)};
  }

  function configsIn(q) {
    const X = index(), out = [], notes = [];
    const normc = Object.fromEntries(X.configs.map(c => [norm(c), c]));
    for (const tok of q.match(/\bV[A-Z]{1,2}[\w\-]*/gi) || []) {
      const n = norm(tok);
      let c = normc[n];
      if (!c) {
        const m = closest(n, Object.keys(normc), 0.7);
        if (!m) continue;
        c = normc[m]; notes.push(`«${tok}» interpretato come ${c}`);
      }
      if (!out.includes(c)) out.push(c);
    }
    const suff = {};
    for (const c of X.configs) {
      const sx = c.replace(/^[^_\-]+[_\-]/, "");
      if (sx !== c && sx.toLowerCase() !== "base") (suff[sx] = suff[sx] || []).push(c);
    }
    for (const [sx, cs] of Object.entries(suff)) {
      if (cs.length !== 1 || out.includes(cs[0])) continue;
      const rx = new RegExp(`(?<![\\w\\-])${sx.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w\\-])`, sx.length <= 3 ? "" : "i");
      if (rx.test(q)) out.push(cs[0]);
    }
    if (/configurazione\s+base|\bbase\b/i.test(q) && !out.includes(X.base) && !out.some(c => /base/i.test(c))) out.unshift(X.base);
    return {cfgs: X.configs.filter(c => out.includes(c)), notes};
  }

  function termsIn(q) {
    const g = APP.gloss || [];
    if (!g.length) return [];
    const cnt = new Map();
    for (const t of g) for (const k of [t.term, ...(t.aliases || [])]) {
      if (!k || k.length < 2) continue;
      const rx = new RegExp(`(?<![\\w\\-])${k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w\\-])`, "gi");
      const n = (q.match(rx) || []).length;
      if (n) cnt.set(t, (cnt.get(t) || 0) + n * 10 + k.length);
    }
    // le configurazioni sono il contesto della domanda: in coda, e solo se non c'è altro
    const isCfg = t => t.category === "configurazione";
    const all = [...cnt.entries()].sort((a, b) => isCfg(a[0]) - isCfg(b[0]) || b[1] - a[1]).map(x => x[0]);
    const main = all.filter(t => !isCfg(t));
    return (main.length ? main : all).slice(0, 4);
  }

  function unknownWords(q, exclude) {
    const X = index(), out = [];
    const excl = new Set(exclude.map(norm));
    const add = w => {
      w = w.replace(/^[\s?.,;:!'"«»()]+|[\s?.,;:!'"«»()]+$/g, "");
      if (w.length < 2 || findTerm(w) || excl.has(norm(w)) || STOP_IT.has(w.toLowerCase())) return;
      if (out.some(x => norm(x) === norm(w))) return;
      out.push(w);
    };
    for (const m of q.matchAll(ASKED)) { const first = m[1].split(/\s+/)[0]; add(STOP_IT.has(first.toLowerCase()) ? m[1] : first); }
    for (const m of q.matchAll(ACR)) if (/[A-Z]{2}/.test(m[1]) && !ACR_STOP.has(m[1])) add(m[1]);
    for (const w of q.match(/[A-Za-zÀ-ù][\w\-]{2,}/g) || []) if (X.vocab.has(w.toLowerCase()) && !/[_\d]/.test(w)) add(w.toLowerCase());
    return out;
  }

  /* ── costruzione della risposta ── */
  const KIND = {ref: "★", eq: "=", diff: "≠", only: "➕", unk: "?"};
  const desc = t => String(t || "").replace(/\r/g, "").split(/\n?—{5,}\n?/)[0].replace(/^Description:\s*/i, "").trim();

  function answerFunction(res, fid, cs, intent) {
    const full = window.ATM_STATIC.details[fid];
    const d = Explorer.subset(full, cs);
    const B = res.blocks;
    B.push({type: "title", text: fid, sub: d.desc || ""});
    B.push({type: "explore", items: [fid]});
    if (intent === "differences") {
      const st = {g: 0, o: 0, r: 0};
      d.cards.forEach(k => { if (st[k.state] !== undefined) st[k.state]++; });
      const nd = d.reqs.filter(r => Object.values(r.cells).some(x => x.k === "diff" || x.k === "only")).length;
      B.push({type: "stats", items: [
        {value: d.cards.length, label: "configurazioni"}, {value: st.g, label: "simili alla base", tone: "ok"},
        {value: st.o + st.r, label: "con differenze", tone: st.o + st.r ? "warn" : ""}, {value: nd, label: "requisiti diversi", tone: nd ? "bad" : "ok"}]});
      B.push({type: "table", title: "Confronto con la configurazione base " + d.base, colors: {0: "config"},
        columns: ["Configurazione", "Esito", "Similarità", "Documento", "Pagine"],
        rows: d.cards.map(k => [k.config, (STATE_UI[k.state || ""] || STATE_UI[""]).label, k.base ? "riferimento" : k.sim != null ? k.sim + " %" : "–",
          k.ref ? `${k.ref.doc} ${k.ref.code || ""}` : "–", k.ref ? pagesTxt(k.ref) : ""])});
      const diffs = d.reqs.filter(r => Object.values(r.cells).some(x => x.k === "diff" || x.k === "only"));
      if (diffs.length) B.push({type: "table", title: "Requisiti diversi fra le configurazioni", collapsed: diffs.length > 12, maxRows: 30,
        columns: ["Requisito", "Descrizione", ...d.configs], rows: diffs.map(r => [r.id, r.desc, ...d.configs.map(c => r.cells[c] ? KIND[r.cells[c].k] || "?" : "–")])});
      B.push({type: "cfgblocks", base: d.base, items: d.cards.filter(k => !k.reference || (k.extra || []).length)});
    } else if (intent === "requirements") {
      if (!d.reqs.length) B.push({type: "text", tone: "info", md: "Nessun requisito nel foglio «Requisiti» per questa funzione."});
      else B.push({type: "table", title: `Requisiti (${d.reqs.length}) — ★ riferimento · = uguale · ≠ diverso · ➕ solo qui`, maxRows: 40,
        columns: ["Requisito", "Descrizione", ...d.configs], rows: d.reqs.map(r => [r.id, r.desc, ...d.configs.map(c => r.cells[c] ? KIND[r.cells[c].k] || "?" : "–")])});
      B.push({type: "text", tone: "info", md: "Per leggere il testo completo di un requisito nelle configurazioni scelte usa **Esplora → 📋 Requisiti** e clicca sulla riga."});
    } else if (intent === "documents") {
      const g = new Map();
      d.cards.forEach(k => {
        if (!k.ref) return;
        const key = (k.ref.fid || k.ref.code || k.ref.doc) + "|" + (k.ref.first || k.ref.page || 0);
        if (!g.has(key)) g.set(key, Object.assign({}, k.ref, {configs: []}));
        g.get(key).configs.push(k.config);
      });
      B.push({type: "docs", title: "Documenti in cui è descritta la funzione", items: [...g.values()]});
    } else if (intent === "components") {
      const parts = [];
      d.cards.forEach(k => (k.extra || []).filter(x => /component/i.test(x.label)).forEach(x => parts.push(`**${k.config}** — *${x.label}*\n\n${x.text}`)));
      if (parts.length) B.push({type: "text", md: parts.join("\n\n---\n\n")});
      else B.push({type: "text", tone: "info", md: "Nel file non ci sono campi «Componenti» per questa funzione: ecco la descrizione per configurazione."});
      B.push({type: "cfgblocks", base: d.base, items: d.cards});
    } else {
      B.push({type: "cfgblocks", base: d.base, items: d.cards});
    }
    res.followups.push(`Quali sono le differenze di ${fid} tra le configurazioni?`, `Quali requisiti di ${fid} sono diversi?`, `In quali documenti è descritta ${fid}?`);
  }

  function ask(q) {
    const t0 = performance.now();
    q = String(q || "").trim();
    const ql = q.toLowerCase();
    const {found, notes: fn, ambiguous} = functionsIn(q);
    const {cfgs, notes: cn} = configsIn(q);
    const terms = termsIn(q).filter(t => !found.some(f => norm(f) === norm(t.term)));
    let intent = "overview";
    for (const [name, rx] of INTENTS) if (rx.test(ql)) { intent = name; break; }
    if (!found.length && terms.length) intent = "concept";
    const res = {question: q, intent, functions: found, configs: cfgs, allConfigs: /\btutt[ei]\b/i.test(q) && !cfgs.length,
                 notes: [...fn, ...cn], blocks: [], followups: [], ai: false};
    const kb = [];
    for (const t of terms) {
      kb.push({type: "text", tone: "know", md: `### 🧠 Cosa so di «${t.term}»\n\n${termMD(t)}`});
      const rel = (t.funcs || []).filter(f => !found.includes(f)).slice(0, 8);
      if (rel.length) kb.push({type: "chips", explore: true, title: `Funzioni che citano ${t.term} (clic = apri in Esplora)`,
        items: rel.map(f => ({label: f, desc: (window.ATM_STATIC.tree.funcs[f] || {}).desc || "", fid: f}))});
    }
    if (found.length) {
      for (const fid of found.slice(0, 3)) answerFunction(res, fid, cfgs, intent);
      const at = res.blocks[0] && res.blocks[0].type === "title" ? 1 : 0;
      res.blocks.splice(at, 0, ...kb);
    } else {
      res.blocks.push(...kb);
      if (ambiguous.length) {
        res.blocks.push({type: "text", tone: "info", md: terms.length ? "Funzioni che potrebbero riguardare la domanda:" : "Non ho individuato con certezza la funzione. Forse intendevi una di queste?"});
        res.blocks.push({type: "chips", items: ambiguous.map(f => ({label: f, desc: (window.ATM_STATIC.tree.funcs[f] || {}).desc || "", fid: f}))});
      } else if (!terms.length) {
        res.blocks.push({type: "text", tone: "warn", md: "Non ho trovato una funzione nella domanda. Indica il FUNC ID (es. *BOG_Hotbox_Detection*) oppure alcune parole del nome della funzione."});
      }
    }
    const unk = unknownWords(q, [...found, ...cfgs, ...found.flatMap(f => f.split(/[_\W]+/))]);
    if (unk.length) res.blocks.push({type: "unknown", words: unk});
    res.ms = Math.round(performance.now() - t0);
    return res;
  }

  return {ask, functionsIn, configsIn, termsIn, unknownWords};
})();
