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

  /* sigle brevi o uguali a parole italiane («DAI», «ERA», «DO», «MR») solo se scritte in MAIUSCOLO */
  const caseSensitive = k => k === k.toUpperCase() && /[A-Z]/.test(k) && (k.length <= 3 || STOP_IT.has(k.toLowerCase()) || STOP.has(k.toLowerCase()));
  function termsIn(q) {
    const g = APP.gloss || [];
    if (!g.length) return [];
    const cnt = new Map();
    for (const t of g) for (const k of [t.term, ...(t.aliases || [])]) {
      if (!k || k.length < 2) continue;
      const rx = new RegExp(`(?<![\\w\\-])${k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w\\-])`, caseSensitive(k) ? "g" : "gi");
      const n = (q.match(rx) || []).length;
      if (n) cnt.set(t, (cnt.get(t) || 0) + n * 10 + k.length);
    }
    // le configurazioni sono il contesto della domanda: in coda, e solo se non c'è altro
    const isCfg = t => t.category === "configurazione";
    const all = [...cnt.entries()].sort((a, b) => isCfg(a[0]) - isCfg(b[0]) || b[1] - a[1]).map(x => x[0]);
    const main = all.filter(t => !isCfg(t));
    return (main.length ? main : all).slice(0, 4);
  }

  /* domanda discorsiva senza sigle note: concetti le cui spiegazioni (anche le risposte
     dell'esperto al questionAI) contengono le parole della domanda — come knowledge.search_answers */
  function termsByAnswers(q, exclude, limit = 2) {
    const words = s => new Set((String(s || "").match(/[A-Za-zÀ-ù0-9][\w\-]{2,}/g) || []).map(w => w.toLowerCase()).filter(w => w.length >= 4 && !STOP_IT.has(w)));
    const qw = words(q);
    if (!qw.size) return [];
    const ex = new Set(exclude.map(norm));
    const out = [];
    for (const t of APP.gloss || []) {
      if (ex.has(norm(t.term)) || t.category === "configurazione") continue;
      const blob = words([t.meaning, t.details, ...(t.answers || []).map(a => (a.q || "") + " " + (a.a || ""))].join(" "));
      const hit = [...qw].filter(w => blob.has(w)).length;
      if (hit >= Math.min(2, qw.size)) out.push([hit + ((t.answers || []).length ? 1 : 0), t]);
    }
    return out.sort((a, b) => b[0] - a[0]).slice(0, limit).map(x => x[1]);
  }

  const ELIDED = new Set("all dall dell nell sull coll quell quest bell sant tutt".split(" "));
  function unknownWords(q, exclude) {
    const X = index(), out = [];
    const excl = new Set(exclude.map(norm));
    const add = w => {
      w = w.replace(/^[\s?.,;:!'"«»()]+|[\s?.,;:!'"«»()]+$/g, "");
      if (w.length < 2 || findTerm(w) || excl.has(norm(w)) || STOP_IT.has(w.toLowerCase()) || ELIDED.has(w.toLowerCase())) return;
      if (out.some(x => norm(x) === norm(w))) return;
      out.push(w);
    };
    for (const m of q.matchAll(ASKED)) { const first = m[1].split(/\s+/)[0]; add(STOP_IT.has(first.toLowerCase()) ? m[1] : first); }
    for (const m of q.matchAll(ACR)) if (/[A-Z]{2}/.test(m[1]) && !ACR_STOP.has(m[1])) add(m[1]);
    for (const w of q.match(/[A-Za-zÀ-ù][\w\-]{2,}/g) || []) if (X.vocab.has(w.toLowerCase()) && !/[_\d]/.test(w)) add(w.toLowerCase());
    return out;
  }

  /* ── costruzione della risposta ── */
  const desc = t => String(t || "").replace(/\r/g, "").split(/\n?—{5,}\n?/)[0].replace(/^Description:\s*/i, "").trim();

  /* riga di tabella: esito MATCHED / NOT MATCHED e simbolo per configurazione (come Esplora) */
  function reqRow(r, d) {
    const st = Explorer.reqStatus(r, d.configs, d.base);
    const why = Explorer.reqWhy(st).replace(/<[^>]+>/g, "");
    const esito = {match: "✔ MATCHED", check: "? da verificare", single: "presente"}[st.s] || "✖ NOT MATCHED";
    return [r.id, st.text || r.desc, `${esito} — ${why}`, ...d.configs.map(c => {
      const x = r.cells[c];
      if (!x) return "✖";
      if (x.g < 0) return "?";
      const L = st.variants > 1 ? st.letters[x.g] : "";
      if (c === st.ref) return (st.refIsBase ? "★" : "☆") + L;
      return (r.cells[st.ref] && r.cells[st.ref].g === x.g ? "=" : "≠") + L;
    })];
  }

  /* ── lettura dei documenti: replica di docsearch.py (BM25 sul testo di requisiti e paragrafi dei PDF) ── */
  const DocSearch = (() => {
    const WORD = /[a-zà-ù0-9]+(?:[.,/][0-9]+)*/gi;
    const NUMERIC_Q = /\b(valor[ei]|quant[oaie]|soglia|soglie|limite|limiti|pression[ei]|temp[oi]|temperatur|velocit|tension[ei]|corrent[ei]|ritard|durat|frequenz|percentual|kpa|bar|km\/h|second)/i;
    const UNIT = /\d[\d.,]*\s*(?:kpa|bar|mbar|psi|km\/h|kmh|m\/s|v\b|kv|vac|vdc|a\b|ka|ma|ms|s\b|sec|seconds?|min|minutes?|h\b|hours?|°c|°|%|hz|khz|kw|w\b|mm|cm|m\b|km|kg|t\b|l\b)/i;
    let S = null;
    const stem = w => {
      w = w.toLowerCase();
      if (/^\d+$/.test(w) || w.length <= 4) return w;
      for (const suf of ["ing", "ed", "es", "s"]) if (w.endsWith(suf) && w.length - suf.length >= 4) { w = w.slice(0, -suf.length); break; }
      return w.slice(0, 6);
    };
    const tokens = t => (String(t || "").toLowerCase().match(WORD) || []).filter(w => w.length >= 2).map(stem);
    function init() {
      const ix = window.ATM_STATIC.dx;
      if (!ix || !ix.items) return null;
      const stop = new Set(ix.stop || []), syn = ix.syn || {}, synKeys = Object.keys(syn);
      const toks = ix.items.map(it => { const m = new Map(); for (const t of tokens(it[6] + " " + it[2])) m.set(t, (m.get(t) || 0) + 1); return m; });
      const len = toks.map(m => { let n = 0; for (const v of m.values()) n += v; return n; });
      const avg = len.reduce((a, b) => a + b, 0) / (len.length || 1) || 1;
      const df = new Map();
      for (const m of toks) for (const k of m.keys()) df.set(k, (df.get(k) || 0) + 1);
      const fdesc = Object.entries(ix.funcs || {}).map(([f, d]) => [f, new Set(tokens(f.replace(/_/g, " ") + " " + d))]);
      const ddesc = ix.docs.map(d => new Set(tokens(d[0].replace(/_/g, " ") + " " + d[1])));
      const cfgs = [...new Set(ix.items.flatMap(it => it[3]))].sort((a, b) => b.length - a.length);
      return {ix, stop, syn, synKeys, toks, len, avg, df, N: toks.length, fdesc, ddesc, cfgs};
    }
    function synFor(w) { let best = ""; for (const k of S.synKeys) if (w.startsWith(k) && k.length > best.length) best = k; return best ? S.syn[best] : []; }
    function queryTerms(q, extra) {
      const groups = [];
      for (const w of q.toLowerCase().match(WORD) || []) {
        if (w.length < 2 || S.stop.has(w)) continue;
        const alts = new Set([stem(w)]);
        for (const en of synFor(w)) en.split(/\s+/).forEach(x => alts.add(stem(x)));
        const a = [...alts].filter(x => !S.stop.has(x) && x.length >= 2).sort();
        if (a.length && !groups.some(g => g.length === a.length && g.every((x, i) => x === a[i]))) groups.push(a);
      }
      for (const [term, aliases] of extra) {
        const st = stem(term);
        for (const g of groups) if (g.includes(st)) { for (const al of aliases) for (const t of tokens(al)) if (!S.stop.has(t) && !g.includes(t)) g.push(t); g.sort(); }
      }
      return groups;
    }
    const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    function search(q, configs = [], fids = [], extra = [], limit = 6) {
      if (S === null) S = init() || false;
      if (!S) return [];
      for (const c of S.cfgs) q = q.replace(new RegExp(`(?<![\\w\\-])${esc(c)}(?![\\w\\-])`, "gi"), " ");
      for (const f of fids) q = q.replace(new RegExp(esc(f), "gi"), " ");
      let groups = queryTerms(q, extra);
      if (!groups.length) return [];
      const qset = new Set(groups.flat());
      const inter = (set) => { let n = 0; for (const a of qset) if (set.has(a)) n++; return n; };
      const fscore = new Map(S.fdesc.map(([f, ws]) => [f, inter(ws)]));
      const fbest = Math.max(0, ...fscore.values());
      const dscore = S.ddesc.map(inter);
      const dbest = Math.max(0, ...dscore);
      const ctx = new Set();
      if (dbest >= 2) dscore.forEach((n, j) => { if (n === dbest) S.ddesc[j].forEach(a => ctx.add(a)); });
      const nameCtx = f => tokens(f.replace(/_/g, " ")).forEach(a => { if (qset.has(a)) ctx.add(a); });
      fids.forEach(nameCtx);
      if (fbest >= 2) for (const [f, n] of fscore) if (n === fbest) nameCtx(f);
      const content = groups.filter(g => !g.some(a => ctx.has(a)));
      let weak = [];
      if (content.length >= 2) { weak = groups.filter(g => g.some(a => ctx.has(a))); groups = content; }
      const numeric = NUMERIC_Q.test(q);
      const k1 = 1.2, b = 0.75, cset = new Set(configs), fset = new Set(fids);
      const idf = t => { const n = S.df.get(t) || 0; return Math.log(1 + (S.N - n + 0.5) / (n + 0.5)); };
      const out = [];
      for (let i = 0; i < S.toks.length; i++) {
        const tf = S.toks[i], normL = k1 * (1 - b + b * S.len[i] / S.avg);
        const val = a => { const f = tf.get(a); return f ? idf(a) * f * (k1 + 1) / (f + normL) : 0; };
        let hit = 0, s = 0;
        for (const g of groups) {
          const v = g.map(val).filter(x => x).sort((x, y) => y - x);
          if (v.length) { hit++; s += v[0] + 0.5 * v.slice(1).reduce((x, y) => x + y, 0); }
        }
        if (hit < Math.min(2, groups.length)) continue;
        for (const g of weak) s += 0.3 * Math.max(0, ...g.map(val));
        const it = S.ix.items[i], cover = hit / groups.length;
        s *= 0.5 + cover;
        if (fset.has(it[1])) s *= 1.8;
        else if (fbest >= 2 && (fscore.get(it[1]) || 0) >= fbest) s *= 1.5;
        if (it[4] >= 0 && dscore[it[4]] >= 2) s *= 1.3;
        if (configs.length) s *= it[3].some(c => cset.has(c)) ? 1.25 : 0.35;
        if (numeric && UNIT.test(it[6])) s *= 1.35;
        if (it[0] === "r") s *= 1.15;
        out.push([s, cover, i]);
      }
      out.sort((x, y) => y[0] - x[0] || y[1] - x[1] || y[2] - x[2]);
      const res = [], seen = new Set();
      for (const [s, cover, i] of out) {
        const key = S.ix.items[i][6].slice(0, 160);
        if (seen.has(key)) continue;
        seen.add(key);
        res.push(Object.assign(hitOf(i, cset), {score: Math.round(s * 100) / 100, cover: Math.round(cover * 100) / 100, terms: groups.flat()}));
        if (res.length >= limit) break;
      }
      return res;
    }
    /* passaggio i dell'indice nel formato dei risultati (con il PDF della configurazione chiesta) */
    function hitOf(i, cset) {
      const it = S.ix.items[i];
      let di = it[4], page = it[5];
      const alt = (it[7] || []).find(a => cset.has(a[0]));
      if (alt) [, di, page] = alt;      // il PDF della configurazione chiesta
      const d = di >= 0 ? S.ix.docs[di] : ["", "", ""];
      return {i, kind: it[0], fid: it[1], id: it[2], configs: it[3], doc: d[0], code: d[1], file: d[2], page, text: it[6], terms: []};
    }
    function ready() { if (S === null) S = init() || false; return S; }
    /* gruppi di radici (parola + traduzioni) di un testo italiano, come nella ricerca */
    function terms(q, extra = []) { return ready() ? queryTerms(q, extra) : []; }
    function itemTokens(i) { return ready() ? S.toks[i] : new Map(); }
    return {search, tokens, stem, terms, hitOf: (i, cset) => (ready() ? hitOf(i, cset) : null), itemTokens, index: () => (ready() ? S.ix : null)};
  })();

  /* risposta «📄 Dai documenti»: cita il passaggio migliore e offre gli altri con il link al PDF */
  function docBlocks(hits, cfgs, summary) {
    const h = hits[0];
    const where = `nel documento **${h.doc}**${h.code ? ` (${h.code})` : ""}${h.page ? `, pag. ${h.page}` : ""}`;
    const inCf = cfgs.length ? cfgs.filter(c => h.configs.includes(c)) : [];
    const cf = `configurazioni ${h.configs.join(", ")}`;
    const lead = summary ? `### 📄 Dai documenti\n\n${summary}` : h.kind === "r"
      ? `### 📄 Dai documenti\n\n${where[0].toUpperCase() + where.slice(1)} — funzione *${h.fid}*, ${cf} — il requisito **${h.id}** stabilisce che:\n\n> ${h.text}`
      : `### 📄 Dai documenti\n\n${where[0].toUpperCase() + where.slice(1)} — funzione *${h.fid}*, ${cf} — si legge:\n\n> ${h.text}`;
    const warn = cfgs.length && !inCf.length ? `\n\n⚠️ Il passaggio non risulta nelle configurazioni chieste (${cfgs.join(", ")}): verifica nel documento.` : "";
    const B = [{type: "text", tone: "know", md: lead + warn + "\n\n*Risposta ricavata dalla lettura del testo dei documenti: verifica sempre nel PDF (clic sui passaggi qui sotto).*"}];
    const terms = [...new Set(h.terms)].filter(t => t.length >= 3).sort();
    const rx = terms.length ? new RegExp(`\\b(${terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})[a-zà-ù]*`, "gi") : null;
    const mark = t => (rx ? t.replace(rx, "[[$&]]") : t);
    B.push({type: "hits", title: "Passaggi dei documenti più pertinenti (clic = apri il PDF alla pagina)",
      items: hits.filter(x => x.file).map(x => ({fid: x.file, page: x.page || 1,
        file: `${x.doc} ${x.code || ""} — ${x.fid}${x.id ? " · " + x.id : ""} — ${x.configs.join(", ")}`,
        snippet: mark(x.text.length > 420 ? x.text.slice(0, 420) + "…" : x.text)}))});
    return B;
  }

  /* ════════════════════════════════════════════════════════════════════
     COMPRENSIONE DELLA DOMANDA e «🎓 Risposta AI» (stessa logica di understand.py)
     La domanda è letta come la leggerebbe un ingegnere: COSA chiede (valori,
     definizione, funzionamento, condizioni…), QUALE grandezza (pressione,
     tempo…), DOVE cercare (documento FRS, funzione, configurazione) e di COSA
     parla (compressori, porte…). Le parole che indicano il «dove» non sono
     usate come parole da cercare e non sono «parole sconosciute».
     ════════════════════════════════════════════════════════════════════ */
  const U = (() => {
    const fold = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const escRx = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const NUM = "\\d+(?:[.,]\\d+)?";
    const QTY = [
      {key: "pressione", label: "pressione", q: /pression|pressur|\bkpa\b|\bbar\b|\bpsi\b/, units: "kpa|mbar|bar|psi"},
      {key: "temperatura", label: "temperatura", q: /temperatur|°\s*c\b|\bgradi\b/, units: "°\\s*c|°|deg(?:rees?)?\\s*c?"},
      {key: "velocita", label: "velocità", q: /velocit|km\/h|\bkmh\b/, units: "km\\/h|kmh|m\\/s"},
      {key: "tensione", label: "tensione", q: /tension|voltag|\bvolt\b|\bkv\b|\bvdc\b|\bvac\b/, units: "kv|vdc|vac|v"},
      {key: "corrente", label: "corrente", q: /corrent|amper/, units: "ka|ma|a"},
      {key: "tempo", label: "tempo", q: /\btemp[oi]\b|ritard|durat|timeout|\bsecond|\bminut|dopo quanto|entro quanto|\bore\b/, units: "ms|sec(?:onds?)?|s|min(?:utes?)?|hours?|h"},
      {key: "frequenza", label: "frequenza", q: /frequenz|\bhz\b/, units: "khz|hz"},
      {key: "potenza", label: "potenza", q: /potenz|\bkw\b/, units: "mw|kw|w"},
      {key: "percentuale", label: "percentuale", q: /percentual|%/, units: "%"},
    ];
    const ANY = {key: "valori", label: "valori numerici", units: QTY.map(x => x.units).join("|")};
    const unitRx = (qt, flags = "gi") => new RegExp(`(?<![\\w.])(${NUM})\\s*(${qt.units})(\\/(?:min|s|h))?(?![a-z0-9])`, flags);
    const ASK_LABEL = {values: "Valori", define: "Definizione", when: "Condizioni", explain: "Funzionamento", differences: "Differenze",
                       requirements: "Requisiti", documents: "Documenti", components: "Componenti", overview: "Panoramica", generic: "Domanda"};
    const VALUES_Q = /\bvalor[ei]\b|\bquant[oaie]\b|\bsogli[ae]\b|\blimit[ei]\b|\brange\b|\bintervall[oi] di\b|\ba che (?:pression|temperatur|velocit|tension|corrent|valor|frequenz|potenz)|\b(?:qual[ei]?|che) (?:e |sono )?(?:il |la |i |le )?(?:pression|temperatur|velocit|tension|corrent|frequenz|potenz|tarat)/;
    const WHEN_Q = /\bquando\b|in (?:quali|che) (?:condizion|cas)|\bperch[eé]\b|\bse\b.*\bcosa succede\b|cosa succede/;
    // parole che indicano DOVE cercare o la forma della domanda (non il contenuto)
    const FRAME_STOP = new Set(`interno interna interni interne dentro presente presenti contenuto contenuti contenute riportato riportati
      riportate indicato indicati indicate specificato specificati specificate definito definiti definite previsto previsti previste
      ci sono trovano trova trovare elenco elenca elencami lista tutti tutte tutto ogni vari varie diversi diverse sistema frs trs doc
      documento documenti valore valori quale quali quanto quanta quanti quante che cosa come dove sogli soglia soglie limite limiti
      parametro parametri numero numeri dato dati presenti esistono esiste riguardo riguardano riguarda relativi relative
      vengono viene sono e è hanno ha nel nella nei nelle per il lo la i gli le di da in con su tra fra del della dei delle al alla
      ai alle dal dalla un una uno all dall dell nell sull configurazione configurazioni treno treni base a si dopo entro
      quanto quanta quanti quante succede avviene accade massimo massima massimi massime minimo minima minimi minime
      raggiungere raggiunge raggiungono possono puo può deve devono essere avere`.split(/\s+/));

    let DOCS = null;            // nomi dei documenti → {core, idx:Set, fids:Set}
    function docsIndex() {
      if (DOCS) return DOCS;
      DOCS = new Map();
      const ix = DocSearch.index();
      if (!ix) return DOCS;
      ix.docs.forEach((d, j) => {
        if (!DOCS.has(d[0])) {
          const core = fold(d[0]).replace(/^(?:frs|trs|srs|sss)[\s_\-]+/, "").replace(/[_\-]+/g, " ").replace(/\s+/g, " ").trim();
          DOCS.set(d[0], {name: d[0], core, idx: new Set(), fids: new Set(), codes: new Set()});
        }
        DOCS.get(d[0]).idx.add(j);
        if (d[1]) DOCS.get(d[0]).codes.add(d[1]);
      });
      const byIdx = new Map();
      for (const v of DOCS.values()) v.idx.forEach(j => byIdx.set(j, v));
      for (const it of ix.items) {
        const v = byIdx.get(it[4]); if (v) v.fids.add(it[1]);
        for (const a of it[7] || []) { const w = byIdx.get(a[1]); if (w) w.fids.add(it[1]); }
      }
      return DOCS;
    }

    /* documenti nominati nella domanda: nome («FRS Air Supply», «air supply»), codice
       (3EST000225-7915) oppure, se si parla di «FRS/documento», nome tradotto («alimentazione aria») */
    function docsIn(q) {
      const D = docsIndex(), out = [];
      const qn = " " + fold(q).replace(/[_\-'’/]+/g, " ").replace(/\s+/g, " ") + " ";
      for (const v of D.values()) {
        if (v.core.length >= 3 && new RegExp(`[^a-z0-9]${escRx(v.core).replace(/ /g, "\\s+")}[^a-z0-9]`).test(qn)) out.push(v.name);
        else if ([...v.codes].some(c => q.toUpperCase().includes(c.toUpperCase()))) out.push(v.name);
      }
      if (!out.length && /\b(frs|documento|doc)\b/i.test(q)) {
        const qs = new Set(DocSearch.terms(q).flat());
        for (const v of D.values()) {
          const need = [...new Set(DocSearch.tokens(v.core))].filter(t => t.length >= 3 && !/^(and|the|of)$/.test(t));
          if (need.length && need.every(t => qs.has(t))) out.push(v.name);
        }
      }
      return out;
    }

    function askType(ql, intent, qty, defined) {
      if (defined) return "define";
      if (VALUES_Q.test(ql) || (qty && /\b(che|qual[ei]?|quant[oaie]|a che)\b/.test(ql))) return "values";
      if (WHEN_Q.test(ql) && !/come funziona/.test(ql)) return "when";
      if (intent && intent !== "overview" && intent !== "concept") return intent;
      return intent === "overview" ? "overview" : "generic";
    }

    /* parole di CONTENUTO della domanda (senza il «dove» e la forma della domanda) */
    function topicText(q, fr) {
      let t = " " + q.replace(/['’]/g, " ") + " ";
      const cut = s => { if (s) t = t.replace(new RegExp(`(?<![\\w\\-])${escRx(s).replace(/[\s_\-]+/g, "[\\s_\\-]+")}(?![\\w\\-])`, "gi"), " "); };
      fr.docs.forEach(d => { cut(d); cut(docsIndex().get(d).core); [...docsIndex().get(d).codes].forEach(cut); });
      fr.functions.forEach(cut);
      fr.configs.forEach(cut);
      return t.split(/\s+/).filter(w => w && !FRAME_STOP.has(fold(w).replace(/[^a-z0-9]/g, "")) && !STOP_IT.has(w.toLowerCase().replace(/[?!.,;:]/g, "")) && !(fr.qty && fr.qty.q && fr.qty.q.test(fold(w)))).join(" ");
    }

    function frame(q, base) {
      const ql = fold(q);
      const qty = QTY.find(x => x.q.test(ql)) || null;
      const docs = docsIn(q);
      const defined = /(?:cos['’]?\s*[eè]|cosa\s+[eè]|che\s+cos['’]?\s*[eè]|cosa\s+significa|cosa\s+vuol\s+dire|significato\s+di|cosa\s+sono|definizione\s+di|cosa\s+indica|per\s+cosa\s+sta)(?=[\s?.,!]|$)/i.test(q);
      const fr = Object.assign({q, qty, docs}, base);
      fr.ask = askType(ql, base.intent, qty, defined);
      if (fr.ask === "values" && !fr.qty) fr.qty = ANY;
      const ex = ql.match(/\b(massim|minim|piu alt|piu bass|mass\b|min\b)/);
      fr.extreme = !ex ? null : /^(minim|piu bass|min)/.test(ex[1]) ? "min" : "max";
      fr.topic = topicText(q, fr);
      fr.groups = DocSearch.terms(fr.topic);
      return fr;
    }

    /* ── estrazione dei valori con condizione dal testo (inglese) dei documenti ── */
    const CMP = [
      [/(>=|>\s*=|≥|=>)$/, "≥"], [/(<=|<\s*=|≤|=<)$/, "≤"], [/>$/, ">"], [/<$/, "<"], [/(\+\/-|±|\+-)$/, "±"],
      [/(at least|minimum|min\.?|not less than)$/, "≥"], [/(at most|maximum|max\.?|not more than|not exceed(?:ing)?)$/, "≤"],
      [/(less than|lower than|below|under|decrease[sd]?(?: down)?(?: to| below)?|falls?(?: down)? (?:below|under|to)|drops? (?:below|to))$/, "<"],
      [/(more than|greater than|higher than|above|exceed(?:s|ed|ing)?|over|rises? above)$/, ">"],
      [/(after|delay of|delayed by)$/, "dopo"], [/(within|in less than)$/, "entro"], [/(for(?: more than| at least)?|during)$/, "per"],
      [/(reach(?:ed|es)?|achieve[sd]?|increased?(?: up)? to|up to|at|of|=|equal to|is|set to)$/, "="],
    ];
    const OBJ = [
      [/\b(main reservoir pipe|mrp)\b/, "condotta serbatoio principale (MRP)"], [/\b(main reservoir|mr)\b/, "serbatoio principale (MR)"],
      [/\bmain pipe\b/, "condotta principale"], [/\bbrake pipe\b/, "condotta generale del freno"], [/\bbrake cylinder\b/, "cilindro freno"],
      [/\bpantograph\b/, "circuito pantografo"], [/\b(suspension|air bellows?|sensor ts)\b/, "sospensione pneumatica"],
      [/\bpressure decrease\b/, "calo di pressione"], [/\b(train speed|speed (?:is|>|<|above|below|exceeds?|higher|lower))\b/, "velocità del treno"],
      [/\b(line voltage|catenary)\b/, "tensione di linea"], [/\btemperature\b/, "temperatura"], [/\brun(?:ning)? time\b/, "tempo di funzionamento"],
    ];
    const SUBJ = [
      [/primary (?:main )?compressor/, "compressore principale primario"], [/secondary (?:main )?compressor/, "compressore principale secondario"],
      [/first compressor/, "primo compressore"], [/second(?:ary)? compressor/, "secondo compressore"], [/auxiliary compressor/, "compressori ausiliari"],
      [/main compressor/, "compressori principali"], [/compressor/, "compressori"], [/emergency brake/, "freno di emergenza"],
      [/brake test/, "prova freno"], [/parking brake/, "freno di stazionamento"], [/pressure switch|\bps[pc]\b|\bpcp\b/, "pressostato"],
      [/transducer|pressure sensor/, "trasduttori di pressione"], [/leakage/, "perdita d'aria"], [/tilt/, "sistema di assetto (tilt)"],
      [/suspension/, "sospensione"], [/pantograph/, "pantografo"], [/air dryer/, "essiccatore"], [/\bdoors?\b/, "porte"],
      [/heater|heating/, "riscaldamento"], [/hvac|air condition/, "climatizzazione"], [/traction/, "trazione"], [/battery/, "batteria"],
      [/\bbrake/, "freno"], [/sensor/, "sensori"], [/\bevent\b|fault message|alarm|warning/, "messaggio diagnostico"], [/driver/, "macchinista"],
    ];
    const ACT = [
      [/normal (?:operation|condition)|works? between|management/, "funzionamento normale"],
      [/\bblocked\b|inhibit/, "inibizione"], [/\bstop(?:s|ped)?\b|switch(?:ed)? off/, "arresto"],
      [/\bstart(?:s|ed)?\b|\brun(?:s|ning)?\b|switch(?:ed)? on|ordered to run/, "avvio"], [/disabled?|deactivat/, "disabilitazione"],
      [/enabled?|activat/, "abilitazione"], [/released?/, "rilascio"], [/applied|appl(?:y|ies)|request/, "intervento"],
      [/close[sd]? (?:its )?contacts?|\bclose[sd]?\b/, "chiusura"], [/\bopen(?:s|ed)?\b/, "apertura"], [/leakage/, "rilevamento perdita"],
      [/\bevent\b|alarm|warning|fault|message/, "segnalazione"], [/indicated|displayed|shown/, "visualizzazione"],
      [/toleran|deviat|differ/, "tolleranza"],
    ];
    const cap = s => s ? s[0].toUpperCase() + s.slice(1) : s;
    const fmtN = n => String(n).replace(",", ".");
    const sentenceAt = (text, at) => {
      const parts = text.split(/(?<=[.;:])\s+(?=[A-Z])|\s+[•]\s+/);
      let pos = 0;
      for (const p of parts) { const i = text.indexOf(p, pos); if (i <= at && at < i + p.length + 1) return p; pos = i + p.length; }
      return text;
    };
    /* significato in italiano: azione = verbo retto da «shall», soggetto = ciò che lo precede */
    function gloss(sent) {
      const s = sent.toLowerCase();
      const m = s.match(/\bshall\s+(?:not\s+)?(?:be\s+)?([a-z]+(?:\s+[a-z]+){0,3})/);
      let a = null, b = null;
      if (m) {
        const head = s.slice(0, m.index).split(/\bthen\b|,|\bkpa\b|\bif\b|\bwhen\b/).pop();
        m[1] = m[1].replace(/^(?:start|begin)s?\s+to\s+/, "");
        a = ACT.find(([rx]) => rx.test(m[1])) || ACT.find(([rx]) => rx.test(head));
        b = SUBJ.find(([rx]) => rx.test(head)) || SUBJ.find(([rx]) => rx.test(m[1]));
        if (/\bnot\b/.test(s.slice(m.index, m.index + 10)) && a) a = [a[0], "nessun " + a[1]];
      }
      a = a || ACT.find(([rx]) => rx.test(s));
      b = b || SUBJ.find(([rx]) => rx.test(s));
      const quoted = (sent.match(/["“«]([^"”»]{4,60})["”»]/) || [])[1];
      if (a && a[1] === "segnalazione" && quoted) return `Segnalazione «${quoted.trim()}»`;
      if (a && b) return cap(`${a[1]} ${b[1] === "messaggio diagnostico" && a[1] === "segnalazione" ? "diagnostica" : b[1]}`);
      return a ? cap(a[1]) : b ? cap(b[1]) : "";
    }
    function valuesIn(text, qt) {
      const out = [];
      const rx = unitRx(qt);
      let m;
      while ((m = rx.exec(text))) {
        let start = m.index, lo = null;
        const unit = m[2].replace(/\s+/g, "").replace(/^kpa$/i, "kPa").replace(/^°c$/i, "°C").replace(/^km\/h$/i, "km/h")
          .replace(/^(?:s|sec|seconds?)$/i, "s").replace(/^(?:min|minutes?)$/i, "min").replace(/^(?:h|hours?)$/i, "h").replace(/^ms$/i, "ms"), rate = m[3] || "";
        if (rate && qt !== ANY && qt.key !== "tempo") continue; // gradiente (°C/s, kPa/min…)
        let pre = text.slice(Math.max(0, start - 70), start);
        const r = pre.match(new RegExp(`(?:between\\s+)?(${NUM})\\s*(?:${qt.units})?\\s*(-|–|\\.{2,3}|\\/|and|to)\\s*$`, "i"));
        if (r && !/^\d+$/.test(r[1]) === false && !(r[2] === "to" && /increase|decrease|up to/i.test(pre.slice(0, pre.length - r[0].length)))) {
          lo = r[1]; pre = pre.slice(0, pre.length - r[0].length);
          if (out.length && out[out.length - 1].n === parseFloat(fmtN(lo)) && out[out.length - 1].end >= start - r[0].length - 12) out.pop();
        }
        const p = pre.toLowerCase().replace(/\(\s*$/, "").replace(/\s*(?:pressure\s+)?limit\s*\d+\s*(?:is\s*)?$/, " ").replace(/\s*(?:value|pressure)\s*$/, " ").trimEnd();
        let sym = lo ? (r[2] === "/" ? "/" : "–") : (CMP.find(([rx2]) => rx2.test(p)) || [, ""])[1];
        const win = text.slice(Math.max(0, start - 70), start).toLowerCase();
        let obj = "", best = -1;
        for (const [orx, lab] of OBJ) { const mm = [...win.matchAll(new RegExp(orx.source, "g"))].pop(); if (mm && mm.index > best) { best = mm.index; obj = lab; } }
        if (rate) obj = obj || "variazione";
        const n = parseFloat(fmtN(m[1]));
        const neg = qt.key === "temperatura" && text[start - 1] === "-" ? "-" : "";
        const v = lo ? `${fmtN(lo)}${sym === "/" ? "/" : "–"}${fmtN(m[1])} ${unit}${rate}` : `${neg}${fmtN(m[1])} ${unit}${rate}`;
        out.push({v, n: neg ? -n : n, unit: unit + rate, sym: lo ? "" : sym, obj, start, end: m.index + m[0].length,
                  sent: sentenceAt(text, m.index)});
      }
      return out;
    }

    /* tutti i passaggi del perimetro (documento/funzione/configurazione) che contengono la grandezza */
    function scopeHits(fr, limit = 400) {
      const ix = DocSearch.index();
      if (!ix) return [];
      const D = docsIndex(), dset = new Set(fr.docs.flatMap(d => [...D.get(d).idx]));
      const fset = new Set(fr.functions), cset = new Set(fr.configs);
      const rx = fr.qty ? unitRx(fr.qty, "i") : null;
      const raw = [];
      ix.items.forEach((it, i) => {
        if (dset.size && !(dset.has(it[4]) || (it[7] || []).some(a => dset.has(a[1])))) return;
        if (fset.size && !fset.has(it[1])) return;
        if (cset.size && !it[3].some(c => cset.has(c))) return;
        if (rx && !rx.test(it[6])) return;
        const tk = DocSearch.itemTokens(i);
        const hit = fr.groups.filter(g => g.some(a => tk.has(a))).length;
        raw.push([hit, it[0] === "r" ? 1 : 0, i]);
      });
      const best = Math.max(0, ...raw.map(x => x[0]));
      const keep = raw.filter(x => !fr.groups.length || !best || x[0] >= Math.max(1, Math.ceil(best * 0.5)));
      keep.sort((a, b) => b[0] - a[0] || b[1] - a[1] || a[2] - b[2]);
      const seen = new Set(), out = [];
      for (const [, , i] of keep) {
        const key = fold(ix.items[i][6]).replace(/[^a-z0-9]/g, "").slice(0, 200);
        if (seen.has(key)) continue;
        seen.add(key);
        const h = DocSearch.hitOf(i, cset);
        h.terms = fr.groups.flat();
        h.cover = 1;
        out.push(h);
        if (out.length >= limit) break;
      }
      return out;
    }

    /* fatti (valore + condizione + significato) dai passaggi */
    function facts(hits, qt) {
      const F = [], by = new Map();
      for (const h of hits) for (const x of valuesIn(h.text, qt)) {
        const g = gloss(x.sent);
        const key = [h.fid, x.v, x.sym, x.obj, g].join("|");
        const ref = {id: h.id, page: h.page, doc: h.doc, code: h.code, file: h.file, kind: h.kind};
        if (by.has(key)) { const f = by.get(key); if (h.id && !f.refs.some(r => r.id === h.id)) f.refs.push(ref); continue; }
        const f = Object.assign({}, x, {fid: h.fid, gloss: g, refs: [ref], text: h.text, configs: h.configs});
        by.set(key, f); F.push(f);
      }
      return F;
    }
    const shortId = id => (id ? id.split(".").slice(-2).join(".") : "");
    const refTxt = f => {
      const ids = f.refs.map(r => shortId(r.id)).filter(Boolean);
      const pg = [...new Set(f.refs.map(r => r.page).filter(Boolean))];
      return [ids.length ? ids.join(", ") : "paragrafo", pg.length ? `pag. ${pg.join(", ")}` : ""].filter(Boolean).join(" · ");
    };
    const cond = f => (/^[a-z]/.test(f.sym) ? `${f.obj ? f.obj + " " : ""}${f.sym} ${f.v}` : f.sym === "=" ? `${f.obj || "valore"} = ${f.v}` : f.sym === "±" ? `tolleranza ± ${f.v}` : `${f.obj ? f.obj + " " : ""}${f.sym ? f.sym + " " : ""}${f.v}`).trim();
    const shortDesc = d => { d = desc(d).replace(/^Funzione per\s+/i, ""); const c = d.search(/,\s*(garantendo|assicurando|evitando|in modo)/); return (c > 30 ? d.slice(0, c) : d).replace(/\.$/, ""); };
    const quote = t => { t = t.replace(/\s+/g, " ").trim(); return t.length > 170 ? t.slice(0, 167).replace(/\s\S*$/, "") + "…" : t; };

    /* sigle note (glossario) che compaiono nei passaggi citati */
    function acronyms(texts, skip) {
      const out = [], seen = new Set(skip.map(norm));
      const all = texts.join(" ");
      for (const t of APP.gloss || []) {
        if (t.category === "configurazione" || seen.has(norm(t.term)) || !/^[A-Z][A-Z0-9\-]{1,7}$/.test(t.term)) continue;
        if (new RegExp(`(?<![\\w\\-])${escRx(t.term)}(?![\\w\\-])`).test(all)) { out.push(t); seen.add(norm(t.term)); }
        if (out.length >= 8) break;
      }
      return out;
    }

    function understood(fr) {
      const p = [];
      p.push({values: fr.qty && fr.qty !== ANY ? `i valori e le soglie di **${fr.qty.label}**` : "i **valori numerici**", define: "il **significato**",
              when: "**quando / in quali condizioni** avviene", explain: "il **funzionamento**", differences: "le **differenze fra configurazioni**",
              requirements: "i **requisiti**", documents: "i **documenti**", components: "i **componenti**"}[fr.ask] || "una **risposta tecnica**");
      const topic = fr.topic.replace(/[?!.]/g, " ").replace(/\s+/g, " ").trim();
      if (topic && fr.ask !== "define") p.push(`argomento: *${topic}*`);
      if (fr.terms.length) p.push(`concetti: ${fr.terms.map(t => `**${t.term}**`).join(", ")}`);
      if (fr.docs.length) p.push(`documento ${fr.docs.map(d => `**${d}**`).join(", ")}`);
      if (fr.functions.length) p.push(`funzione ${fr.functions.map(f => `**${f}**`).join(", ")}`);
      p.push(fr.configs.length ? `configurazione ${fr.configs.map(c => `**${c}**`).join(", ")}` : "tutte le configurazioni");
      return `🔍 *Ho capito che chiedi:* ${p.join(" · ")}.`;
    }

    const FOOT = "\n\n*Risposta composta dall'AI di AskTrainMind incrociando la conoscenza ferroviaria appresa con il testo dei documenti: i valori sono citati dai requisiti — verifica sempre nella Sezione documentale e nel PDF.*";

    /* ── risposta da ingegnere: VALORI ── */
    function valuesAnswer(fr, hits, enumerate) {
      const qt = fr.qty || ANY;
      const F = facts(hits, qt);
      if (!F.length) return null;
      const funcs = window.ATM_STATIC.tree.funcs;
      const md = [understood(fr), ""];
      const where = fr.docs.length ? ` nel documento **${fr.docs.join(", ")}**${(() => { const c = [...new Set(hits.map(h => h.code).filter(Boolean))]; return c.length ? ` (${c.join(", ")})` : ""; })()}` : "";
      const cfg = fr.configs.length ? ` per la configurazione **${fr.configs.join(", ")}**` : "";
      const byF = new Map();
      F.forEach(f => { if (!byF.has(f.fid)) byF.set(f.fid, []); byF.get(f.fid).push(f); });
      if (enumerate) { const o = [...byF.entries()].sort((x, y) => y[1].length - x[1].length); byF.clear(); o.forEach(([k, v]) => byF.set(k, v)); }
      if (enumerate) {
        md.push(`${cap((where + cfg).trim()) || "Nei documenti"} ho trovato **${F.length} ${F.length === 1 ? "valore" : "valori"} di ${qt.label}** in **${byF.size} ${byF.size === 1 ? "funzione" : "funzioni"}**. Ecco cosa significano, funzione per funzione:`);
      } else {
        let f0 = F[0];
        if (fr.extreme) {
          const PLAUS = /out of (?:the )?range|invalid|not valid|plausib|declared? (?:as )?(?:faulty|excluded)|sensor (?:fault|failure)/i;
          let same = F.filter(f => f.fid === f0.fid);
          same = same.filter(f => !PLAUS.test(f.sent || "")).length ? same.filter(f => !PLAUS.test(f.sent || "")) : same;
          f0 = same.reduce((a, b) => (fr.extreme === "max" ? b.n > a.n : b.n < a.n) ? b : a, same[0] || f0);
        }
        md.push(`**Risposta: ${f0.v}** — ${f0.gloss ? f0.gloss.toLowerCase() + " " : ""}${/^[a-z]/.test(f0.sym) ? "" : "quando "}${cond(f0)}${where || ` nel documento **${f0.refs[0].doc}**`}${cfg} (funzione *${f0.fid}*, ${refTxt(f0)}).`, "",
                `> ${quote(f0.text)}`, "", byF.size > 1 || F.length > 1 ? "Valori collegati che un ingegnere considererebbe insieme:" : "");
      }
      let shown = 0;
      for (const [fid, list] of byF) {
        if (shown >= 8) break;
        shown++;
        md.push("", `**${fid}** — ${shortDesc((funcs[fid] || {}).desc || "")}`);
        const rows = list.slice().sort((a, b) => b.n - a.n).slice(0, 10);
        rows.forEach(f => md.push(`- **${f.v}** — ${f.gloss || "valore citato"} (${cond(f)}) · *${refTxt(f)}*`));
        if (list.length > rows.length) md.push(`- … altri ${list.length - rows.length} valori nella tabella qui sotto`);
      }
      const sig = acronyms(hits.map(h => h.text), fr.configs);
      if (sig.length) md.push("", "**Sigle:** " + sig.map(t => `**${t.term}** = ${t.meaning}`).join(" · "));
      const B = [{type: "text", tone: "ai", md: md.join("\n") + FOOT}];
      if (F.length > 6) B.push({type: "table", title: `Riepilogo dei valori di ${qt.label} (ordinabile: clic sull'intestazione)`, collapsed: F.length > 25, maxRows: 40,
        columns: ["Valore", "Condizione", "Cosa avviene", "Funzione", "Riferimento"],
        rows: F.map(f => [f.v, cond(f), f.gloss || "–", f.fid, refTxt(f)])});
      B.facts = F;
      return B;
    }

    /* ── risposta da ingegnere: passaggio migliore spiegato ── */
    function passageAnswer(fr, hits) {
      const h = hits[0];
      if (!h) return null;
      const funcs = window.ATM_STATIC.tree.funcs;
      const g = gloss(h.text);
      const md = [understood(fr), "",
        `Secondo ${h.kind === "r" ? `il requisito **${h.id}**` : "il testo"} del documento **${h.doc}**${h.code ? ` (${h.code})` : ""}${h.page ? `, pag. ${h.page}` : ""} — funzione *${h.fid}* (${shortDesc((funcs[h.fid] || {}).desc || "")}):`,
        "", `> ${quote(h.text)}`];
      if (g) md.push("", `*In sintesi:* ${g.toLowerCase()}${(() => { const v = valuesIn(h.text, ANY)[0]; return v ? ` (${cond(v)})` : ""; })()}.`);
      const more = hits.slice(1, 4).filter(x => x.fid !== h.fid || x.id !== h.id);
      if (more.length) md.push("", "Altri passaggi collegati:", ...more.map(x => `- ${x.id ? `**${shortId(x.id)}**` : "paragrafo"} (${x.fid}, pag. ${x.page}): ${quote(x.text)}`));
      const sig = acronyms(hits.slice(0, 4).map(x => x.text), fr.configs);
      if (sig.length) md.push("", "**Sigle:** " + sig.map(t => `**${t.term}** = ${t.meaning}`).join(" · "));
      return [{type: "text", tone: "ai", md: md.join("\n") + FOOT}];
    }

    /* ── risposta da ingegnere: concetto ── */
    function conceptAnswer(fr, t, hits) {
      const md = [understood(fr), "", `**${t.term}** significa **${t.meaning}**.`];
      const det = String(t.details || "").replace(/\s+/g, " ").trim();
      if (det) md.push("", det.length > 600 ? det.slice(0, 597).replace(/\s\S*$/, "") + "…" : det);
      const ans = (t.answers || []).filter(a => a.a).slice(-1)[0];
      if (ans && !det.includes(ans.a.slice(0, 60))) md.push("", `💬 *L'esperto ha spiegato:* ${ans.a.replace(/\s+/g, " ").slice(0, 400)}`);
      const fs = (t.funcs || []).slice(0, 6);
      if (fs.length) md.push("", `Sul treno compare nelle funzioni: ${fs.map(f => `*${f}*`).join(", ")}.`);
      const h = hits.find(x => new RegExp(`(?<![\\w\\-])${escRx(t.term)}(?![\\w\\-])`, caseSensitive(t.term) ? "" : "i").test(x.text));
      if (h) md.push("", `Nei documenti (${h.doc}${h.code ? " " + h.code : ""}, pag. ${h.page}): «${quote(h.text)}»`);
      if (t.status === "proposto") md.push("", "⚠️ Significato ricavato dai documenti, non ancora confermato dal developer.");
      return [{type: "text", tone: "ai", md: md.join("\n") + FOOT}];
    }

    /* ── risposta da ingegnere: funzione ── */
    function functionAnswer(fr, fid) {
      const full = window.ATM_STATIC.details[fid];
      if (!full) return null;
      const d = Explorer.subset(full, fr.configs);
      const md = [understood(fr), "", `**${fid}** — ${desc(d.desc || "")}`];
      const ref = d.cards.find(k => fr.configs.includes(k.config) && k.text && !/^RIFERIMENTO/i.test(k.text)) || d.cards.find(k => k.base && k.text);
      if (fr.ask === "differences") {
        const st = {g: 0, o: 0, r: 0, x: 0};
        d.cards.forEach(k => { if (st[k.state] !== undefined) st[k.state]++; });
        md.push("", `Rispetto alla configurazione base **${d.base}**: ${st.g} simili, ${st.o} con differenze moderate, ${st.r} con differenze rilevanti${st.x ? `, ${st.x} non ancora analizzate` : ""}.`);
        d.cards.filter(k => (k.diffs || []).length).slice(0, 5).forEach(k => md.push(`- **${k.config}**: ${k.diffs.slice(0, 3).join("; ")}`));
      } else if (fr.ask === "requirements") {
        const nm = d.reqs.filter(r => ["only", "partial", "text"].includes(Explorer.reqStatus(r, d.configs, d.base).s)).length;
        md.push("", `La funzione ha **${d.reqs.length} requisiti** nel foglio Requisiti; **${nm}** sono NOT MATCHED fra le configurazioni ${d.configs.join(", ")} (testo diverso o presenti solo in alcune).`);
      } else if (fr.ask === "documents") {
        const docs = [...new Set(d.cards.filter(k => k.ref).map(k => `**${k.ref.doc}** ${k.ref.code || ""} (${pagesTxt(k.ref)}) — ${k.config}`))];
        md.push("", "È descritta in:", ...docs.map(x => `- ${x}`));
      } else if (ref) {
        md.push("", `Come funziona${ref.config ? ` (${ref.config})` : ""}: ${ref.text.replace(/\s+/g, " ").trim()}`);
      }
      return [{type: "text", tone: "ai", md: md.join("\n") + FOOT}];
    }

    const docFunctions = docs => new Set(docs.flatMap(d => [...docsIndex().get(d).fids]));
    const isFrameWord = w => FRAME_STOP.has(fold(w)) || QTY.some(x => x.q.test(fold(w)));
    return {ANY, docFunctions, isFrameWord, frame, scopeHits, valuesAnswer, passageAnswer, conceptAnswer, functionAnswer, understood, ASK_LABEL, docsIn, facts, valuesIn, FOOT};
  })();

  function answerFunction(res, fid, cs, intent) {
    const full = window.ATM_STATIC.details[fid];
    const d = Explorer.subset(full, cs);
    const B = res.blocks;
    B.push({type: "title", text: fid, sub: d.desc || ""});
    B.push({type: "explore", items: [fid]});
    if (intent === "differences") {
      const st = {g: 0, o: 0, r: 0};
      d.cards.forEach(k => { if (st[k.state] !== undefined) st[k.state]++; });
      const rst = r => Explorer.reqStatus(r, d.configs, d.base);
      const nm = r => ["only", "partial", "text"].includes(rst(r).s);
      const nd = d.reqs.filter(nm).length;
      B.push({type: "stats", items: [
        {value: d.cards.length, label: "configurazioni"}, {value: st.g, label: "simili alla base", tone: "ok"},
        {value: st.o + st.r, label: "con differenze", tone: st.o + st.r ? "warn" : ""}, {value: nd, label: "requisiti diversi", tone: nd ? "bad" : "ok"}]});
      B.push({type: "table", title: "Confronto con la configurazione base " + d.base, colors: {0: "config"},
        columns: ["Configurazione", "Esito", "Similarità", "Documento", "Pagine"],
        rows: d.cards.map(k => [k.config, (STATE_UI[k.state || ""] || STATE_UI[""]).label, k.base ? "riferimento" : k.sim != null ? k.sim + " %" : "–",
          k.ref ? `${k.ref.doc} ${k.ref.code || ""}` : "–", k.ref ? pagesTxt(k.ref) : ""])});
      const diffs = d.reqs.filter(nm);
      if (diffs.length) B.push({type: "table", title: "Requisiti NOT MATCHED fra le configurazioni", collapsed: diffs.length > 12, maxRows: 30,
        columns: ["Requisito", "Descrizione", "Esito", ...d.configs], rows: diffs.map(r => reqRow(r, d))});
      B.push({type: "cfgblocks", base: d.base, items: d.cards.filter(k => !k.reference || (k.extra || []).length)});
    } else if (intent === "requirements") {
      if (!d.reqs.length) B.push({type: "text", tone: "info", md: "Nessun requisito nel foglio «Requisiti» per questa funzione."});
      else B.push({type: "table", title: `Requisiti (${d.reqs.length}) — ★ riferimento · = stesso testo · ≠ testo diverso · ✖ assente`, maxRows: 40,
        columns: ["Requisito", "Descrizione", "Esito", ...d.configs], rows: d.reqs.map(r => reqRow(r, d))});
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
    let {found, notes: fn, ambiguous} = functionsIn(q);
    const {cfgs, notes: cn} = configsIn(q);
    let intent = "overview";
    for (const [name, rx] of INTENTS) if (rx.test(ql)) { intent = name; break; }
    // 1) COMPRENSIONE: cosa chiede, quale grandezza, dove cercare, di cosa parla
    const docs = U.docsIn(q);
    const fromDesc = fn.some(n => n.startsWith("Funzione individuata dalla descrizione"));
    // funzione riconosciuta solo dalla descrizione: vale se appartiene al documento nominato
    if (docs.length && fromDesc && !found.every(f => U.docFunctions(docs).has(f))) { found = []; fn = fn.filter(n => !n.startsWith("Funzione individuata")); }
    if (docs.length) ambiguous = [];
    let terms = termsIn(q).filter(t => !found.some(f => norm(f) === norm(t.term)));
    let fr = U.frame(q, {intent, functions: found, configs: cfgs, terms: terms.filter(t => t.category !== "configurazione")});
    if (fromDesc && found.length && ["values", "when"].includes(fr.ask)) {     // la descrizione somiglia, ma la domanda chiede un dato: decide il testo dei documenti
      ambiguous = [...found, ...ambiguous]; found = []; fn = fn.filter(n => !n.startsWith("Funzione individuata"));
      fr = U.frame(q, {intent, functions: found, configs: cfgs, terms: terms.filter(t => t.category !== "configurazione")});
    }
    const scoped = docs.length > 0 || found.length > 0;
    if (!terms.some(t => t.category !== "configurazione") && !scoped && ["define", "explain", "generic", "overview"].includes(fr.ask))
      terms = terms.concat(termsByAnswers(q, terms.map(t => t.term)));
    const realTerms = terms.filter(t => t.category !== "configurazione" || fr.ask === "define" || !(scoped || fr.qty));
    fr.terms = realTerms.filter(t => t.category !== "configurazione");
    if (!found.length && realTerms.length && !scoped) intent = "concept";
    const res = {question: q, intent, ask: fr.ask, functions: found, configs: cfgs, docs, allConfigs: /\btutt[ei]\b/i.test(q) && !cfgs.length,
                 notes: [...fn, ...cn], blocks: [], followups: [], ai: false, sections: []};

    // 2) LETTURA DEI DOCUMENTI guidata dalla comprensione
    const extra = realTerms.map(t => [t.term, t.aliases || []]);
    let hits = [], enumerate = false;
    // «quali valori ci sono in…»: senza un argomento preciso si elencano TUTTI i valori del perimetro
    const listAll = /\b(tutt[ie]|elenc|lista|ci sono|presenti|quali (?:sono i |)valori|che valori)\b/i.test(q) || !fr.groups.length;
    if (fr.ask === "values" && (docs.length || found.length) && listAll) {
      hits = U.scopeHits(fr);
      enumerate = hits.length > 1;
    }
    if (!hits.length) {
      const tw = fr.topic.replace(/[?!.,;:]/g, " ").trim();
      const sq = tw && fr.ask !== "define" ? tw + (fr.qty && fr.qty !== U.ANY ? " " + fr.qty.label : "") : q;
      hits = DocSearch.search(sq, cfgs, found, extra, docs.length ? 80 : 12);
      if (found.length) { const F = new Set(found), h2 = hits.filter(h => F.has(h.fid)); if (h2.length) hits = h2; }
      if (docs.length) { const D = new Set(docs); const h2 = hits.filter(h => D.has(h.doc)); if (h2.length) hits = h2; hits = hits.slice(0, 12); }
      if (fr.ask === "values" && fr.qty) { const h2 = hits.filter(h => U.valuesIn(h.text, fr.qty).length); if (h2.length) hits = h2; }
      if (hits.length && !docs.length && !found.length) { const top = hits[0].cover; hits = hits.filter(h => h.cover >= top * 0.75); }
    }

    // 3) SEZIONE RISPOSTA AI: risposta da ingegnere (comprensione + conoscenza + documenti)
    let ai = null;
    const defined = realTerms.find(t => t.category !== "configurazione") || (fr.ask === "define" && realTerms[0]);
    if (fr.ask === "values" && hits.length) ai = U.valuesAnswer(fr, hits, enumerate);
    if (!ai && defined && (fr.ask === "define" || (!found.length && !docs.length))) ai = U.conceptAnswer(fr, defined, hits);
    if (!ai && found.length && !["values", "when"].includes(fr.ask)) ai = U.functionAnswer(fr, found[0]);
    if (!ai && hits.length && (hits[0].cover >= 0.5 || scoped)) ai = U.passageAnswer(fr, hits);
    if (!ai && found.length) ai = U.functionAnswer(fr, found[0]);
    if (!ai && defined) ai = U.conceptAnswer(fr, defined, hits);
    if (!ai) ai = [{type: "text", tone: "warn", md: U.understood(fr) + "\n\nNon ho trovato nei documenti e nella conoscenza appresa una risposta sicura. Prova a indicare la funzione (FUNC ID), il documento FRS o una sigla, oppure riformula la domanda con parole tecniche (es. *pressione*, *compressore*, *porte*)."}];

    // 4) SEZIONE DOCUMENTALE: cosa dicono i documenti, i requisiti e le schede
    const D = [];
    if (hits.length) {
      let summary = "";
      if (enumerate) {
        const fs = [...new Set(hits.map(h => h.fid))], ds = [...new Set(hits.map(h => `**${h.doc}**${h.code ? ` (${h.code})` : ""}`))];
        summary = `Nel documento ${ds.join(", ")}${cfgs.length ? ` — configurazione ${cfgs.join(", ")}` : ""} ci sono **${hits.length} passaggi** (requisiti e paragrafi) che riportano valori di ${(fr.qty || {}).label || "riferimento"}, in ${fs.length} funzioni: ${fs.map(f => `*${f}*`).join(", ")}. Sono elencati qui sotto nell'ordine del documento: clic su un passaggio per aprire il PDF alla pagina.`;
      }
      D.push(...docBlocks(enumerate ? hits.slice(0, 60) : hits.slice(0, 12), cfgs, summary));
      res.docHits = hits.length;
    }
    for (const t of realTerms) {
      D.push({type: "text", tone: "know", md: `### 🧠 Cosa so di «${t.term}»\n\n${termMD(t)}`});
      const rel = (t.funcs || []).filter(f => !found.includes(f)).slice(0, 8);
      if (rel.length) D.push({type: "chips", explore: true, title: `Funzioni che citano ${t.term} (clic = apri in Esplora)`,
        items: rel.map(f => ({label: f, desc: (window.ATM_STATIC.tree.funcs[f] || {}).desc || "", fid: f}))});
    }
    if (found.length) {
      const sub = {blocks: [], followups: res.followups};
      for (const fid of found.slice(0, 3)) answerFunction(sub, fid, cfgs, ["values", "when"].includes(fr.ask) ? "overview" : intent);
      D.push(...sub.blocks);
    } else if (!hits.length && !realTerms.length) {
      if (ambiguous.length) {
        D.push({type: "text", tone: "info", md: "Non ho individuato con certezza la funzione. Forse intendevi una di queste?"});
        D.push({type: "chips", items: ambiguous.map(f => ({label: f, desc: (window.ATM_STATIC.tree.funcs[f] || {}).desc || "", fid: f}))});
      } else D.push({type: "text", tone: "warn", md: "Non ho trovato una funzione nella domanda. Indica il FUNC ID (es. *BOG_Hotbox_Detection*) oppure alcune parole del nome della funzione."});
    }
    const fids = [...new Set(hits.map(h => h.fid))].filter(f => !found.includes(f)).slice(0, 10);
    if (fids.length && hits.length) D.push({type: "chips", explore: true, title: "Funzioni citate nei passaggi (clic = apri in Esplora)",
      items: fids.map(f => ({label: f, desc: (window.ATM_STATIC.tree.funcs[f] || {}).desc || "", fid: f}))});
    const docWords = docs.flatMap(d => d.split(/[_\W]+/));
    const understoodW = (q.match(/[A-Za-zÀ-ù]{3,}/g) || []).filter(w => DocSearch.terms(w).some(g => g.length > 1) || U.isFrameWord(w));
    const unk = unknownWords(q, [...found, ...cfgs, ...found.flatMap(f => f.split(/[_\W]+/)), ...docs, ...docWords, ...understoodW]);
    if (unk.length) D.push({type: "unknown", words: unk});
    if (!res.followups.length && fids.length) res.followups.push(`Come funziona ${fids[0]}?`, `Quali sono le differenze di ${fids[0]} tra le configurazioni?`);

    res.sections = [{id: "ai", title: "🎓 Risposta AI", sub: "come risponderebbe un ingegnere ferroviario che conosce le configurazioni del treno", blocks: ai},
                    {id: "doc", title: "📄 Sezione documentale", sub: "cosa dicono i documenti, i requisiti e le schede del file Excel", blocks: D}];
    res.blocks = [...ai, ...D];
    res.ms = Math.round(performance.now() - t0);
    return res;
  }

  return {ask, functionsIn, configsIn, termsIn, unknownWords, DocSearch, U};
})();
