/* AskTrainMind – «Conoscenza»: l'AI legge un documento, propone i termini che non conosce
   e chiede all'utente cosa significano. Il glossario viene usato in tutte le analisi. */
"use strict";

window.Learn = {
  k: null, docs: null, quiz: null, gq: "", gcat: "",

  async open() {
    await this.loadK();
    if (!this.docs) {
      this.drawStart(true);
      try { this.docs = await api("/api/knowledge/docs"); } catch (e) { this.docs = {items: [], functions: APP.functions, configs: APP.configs}; }
    }
    this.drawStart();
    this.drawQuiz();
  },
  async loadK() {
    this.k = await api("/api/knowledge");
    APP.gloss = this.k.terms; APP.glossCats = this.k.categories;
    this.drawGlossary();
  },
  catOpts(sel) {
    return Object.entries(this.k.categories).map(([k, v]) => `<option value="${k}"${k === sel ? " selected" : ""}>${esc(v)}</option>`).join("");
  },

  /* ── 1. scelta del documento ── */
  drawStart(loading) {
    const d = this.docs || {functions: APP.functions || [], configs: APP.configs || [], items: []};
    const nT = this.k ? this.k.terms.length : 0;
    $("#learnStart").innerHTML = `<div class="ls-head"><div class="ls-ico">🎓</div><div>
        <h2>Insegna all'AI il linguaggio del treno</h2>
        <p>Scegli un documento: l'AI lo legge, trova le <b>sigle e i componenti</b> che non conosce (sensori, centraline, relè, segnali…) e ti chiede cosa significano.
        Ogni risposta finisce nel <b>glossario</b> 📖 e viene usata in tutte le analisi successive (Funzioni AI, note dei requisiti, Chiedi).</p>
        <div class="ls-kpi"><span>📖 <b>${nT}</b> termini conosciuti</span><span>📚 <b>${this.k ? Object.keys(this.k.sources || {}).length : 0}</b> documenti studiati</span>
        <span class="${this.k && this.k.ai ? "ok" : "warn"}">${this.k && this.k.ai ? "✨ AI locale attiva: può proporre i significati" : "💤 AI locale non attiva: proposte dal documento"}</span></div></div></div>
      <div class="ls-src">
        <div class="seg" id="lsMode"><button data-m="func" class="${this.mode !== "pdf" ? "on" : ""}">⚙️ Da una funzione</button><button data-m="pdf" class="${this.mode === "pdf" ? "on" : ""}">📄 Da un PDF del computer</button></div>
        ${this.mode === "pdf" ? `
          <div class="search"><span class="sicon">🔎</span><input id="lsPdfQ" type="search" placeholder="Filtra i PDF per nome o codice…" value="${esc(this.pdfQ || "")}"></div>
          <div class="ls-pdfs" id="lsPdfs">${loading ? `<span class="spin"></span>` : this.pdfList(d.items)}</div>`
        : `<div class="ls-row"><label>Funzione<input type="text" id="lsFunc" list="lsFuncs" placeholder="es. BOG_Hotbox_Detection" value="${esc(this.func || "")}"></label>
             <datalist id="lsFuncs">${d.functions.map(f => `<option value="${esc(f)}">`).join("")}</datalist>
             <label>Configurazione<select id="lsCfg">${d.configs.map(c => `<option${c === this.cfg ? " selected" : ""}>${esc(c)}</option>`).join("")}</select></label></div>
           <small class="muted">Viene letto solo il capitolo del documento in cui è trattata la funzione.</small>`}
        <div class="ls-row"><label>Da pagina<input id="lsFirst" type="number" min="1" placeholder="auto"></label><label>A pagina<input id="lsLast" type="number" min="1" placeholder="auto"></label>
          <span class="spacer"></span><button class="btn primary" id="lsGo">🎓 Inizia la lezione</button></div>
        ${this.pdfSel ? `<div class="ls-chosen">📄 Selezionato: <b>${esc(this.pdfSel.file)}</b></div>` : ""}
      </div>`;
  },
  pdfList(items) {
    const q = (this.pdfQ || "").toLowerCase();
    const it = items.filter(x => !q || (x.file + " " + x.folder).toLowerCase().includes(q)).slice(0, 80);
    return it.map(x => `<button class="ls-pdf${this.pdfSel && this.pdfSel.fid === x.fid ? " on" : ""}" data-fid="${x.fid}" data-file="${esc(x.file)}" title="${esc(x.folder)}">
      📄 ${esc(x.file)} ${x.learned ? `<span class="badge ok" title="Studiato il ${esc(x.learned.date)}">✔ ${x.learned.terms}</span>` : ""}</button>`).join("")
      || `<div class="xnone">Nessun PDF trovato nelle cartelle documenti.</div>`;
  },
  async start() {
    const body = {first: +$("#lsFirst").value || 0, last: +$("#lsLast").value || 0};
    if (this.mode === "pdf") {
      if (!this.pdfSel) return toast("Scegli prima un PDF dall'elenco", "warn");
      body.fid = this.pdfSel.fid;
    } else {
      this.func = $("#lsFunc").value.trim(); this.cfg = $("#lsCfg").value;
      if (!this.func) return toast("Scrivi il nome di una funzione", "warn");
      body.func = this.func; body.cfg = this.cfg;
    }
    $("#learnQuiz").innerHTML = `<div class="card quiz"><span class="spin"></span> Sto leggendo il documento e cercando i termini da imparare…</div>`;
    try {
      const r = await api("/api/knowledge/learn", {json: body});
      this.quiz = {...r, i: 0, saved: 0, skipped: 0};
      if (!r.items.length) toast("Nessun termine nuovo: l'AI conosce già tutto quello che c'è in queste pagine 🎉", "ok");
    } catch (e) { this.quiz = null; $("#learnQuiz").innerHTML = `<div class="tx bad">${esc(e.message)}</div>`; return; }
    this.drawQuiz();
    $("#learnQuiz").scrollIntoView({behavior: "smooth", block: "start"});
  },

  /* ── 2. domande ── */
  drawQuiz() {
    const Q = this.quiz, box = $("#learnQuiz");
    if (!Q) { box.innerHTML = ""; return; }
    const n = Q.items.length;
    if (Q.i >= n) {
      box.innerHTML = `<div class="card quiz done"><h3>🎉 Lezione completata</h3>
        <p>Hai insegnato <b>${Q.saved}</b> termini${Q.skipped ? `, ${Q.skipped} saltati o ignorati` : ""}. Fonte: ${esc(Q.source)} (${Q.pages ? "pagine " + esc(String(Q.pages)) : ""}).</p>
        <p class="muted">I nuovi significati saranno usati dalla prossima analisi e già ora nelle risposte di «Chiedi» (i termini noti sono sottolineati: passa sopra col mouse).</p>
        <button class="btn" data-q="close">Chiudi</button></div>`;
      return;
    }
    const it = Q.items[Q.i];
    const ctx = esc(it.context || "").replace(new RegExp(`\\b(${it.term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})\\b`, "g"), "<mark>$1</mark>");
    box.innerHTML = `<div class="card quiz">
      <div class="qz-top"><span class="qz-n">Domanda ${Q.i + 1} di ${n}</span><div class="qz-prog"><i style="width:${(Q.i / n) * 100}%"></i></div>
        <span class="muted">✔ ${Q.saved} · ⏭ ${Q.skipped}</span></div>
      <div class="qz-q">🤖 ${esc(it.question || `Cosa significa «${it.term}»?`)}</div>
      <div class="qz-term"><b>${esc(it.term)}</b> <small>compare ${it.count} volt${it.count === 1 ? "a" : "e"}</small>
        ${Q.fid && it.page ? `<button class="btn small" data-q="page" title="Apri il documento alla pagina">📄 pag. ${it.page}</button>` : ""}</div>
      ${ctx ? `<blockquote class="qz-ctx">${ctx}</blockquote>` : ""}
      <label class="qz-f">Significato<textarea id="qzMean" rows="2" placeholder="Spiega con parole tue cosa è (es. «Sensore di temperatura della boccola dell'asse»)">${esc(it.proposal || "")}</textarea></label>
      ${it.proposal ? `<small class="muted">💡 Proposta ricavata dal documento: correggila se serve.</small>` : ""}
      <div class="ls-row"><label>Categoria<select id="qzCat">${this.catOpts(it.category || "sigla")}</select></label>
        <label class="grow">Note (facoltative)<input type="text" id="qzNotes" placeholder="es. si trova nel carrello, comunica con la centralina TCMS…"></label></div>
      <div class="qz-acts">
        <button class="btn primary" data-q="save">✔ Salva e continua</button>
        ${this.k.ai ? `<button class="btn" data-q="ai" title="Chiedi all'AI locale una proposta">✨ Proposta AI</button>` : ""}
        <span class="spacer"></span>
        <button class="btn" data-q="skip" title="Salta per ora (lo richiederà la prossima volta)">⏭ Salta</button>
        <button class="btn" data-q="ignore" title="Non è un termine tecnico: non chiederlo più">🚫 Ignora sempre</button></div></div>`;
    setTimeout(() => $("#qzMean") && $("#qzMean").focus(), 30);
  },
  async quizAct(a) {
    const Q = this.quiz; if (!Q) return;
    const it = Q.items[Q.i];
    if (a === "close") { this.quiz = null; return this.drawQuiz(); }
    if (a === "page") return Modal.pdf(Q.fid, it.page, `${it.term} — pag. ${it.page}`);
    if (a === "ai") {
      const b = $("[data-q=ai]"); b.disabled = true; b.innerHTML = `<span class="spin"></span> Sto pensando…`;
      try {
        const r = await api("/api/knowledge/suggest", {json: {term: it.term, context: it.context, proposal: it.proposal}});
        if (r.meaning) $("#qzMean").value = r.meaning;
        if (r.category && this.k.categories[r.category]) $("#qzCat").value = r.category;
        if (r.question) toast("🤖 " + r.question, "info");
      } catch (e) { toast(e.message, "bad"); }
      b.disabled = false; b.innerHTML = "✨ Proposta AI";
      return;
    }
    if (a === "save") {
      const meaning = $("#qzMean").value.trim();
      if (!meaning) { toast("Scrivi il significato (oppure usa Salta)", "warn"); return $("#qzMean").focus(); }
      try {
        await api("/api/knowledge/term", {json: {term: it.term, meaning, category: $("#qzCat").value, notes: $("#qzNotes").value.trim(), source: Q.source}});
        Q.saved++;
      } catch (e) { return toast(e.message, "bad"); }
    } else if (a === "ignore") {
      await api("/api/knowledge/ignore", {json: {term: it.term}}).catch(() => {});
      Q.skipped++;
    } else if (a === "skip") Q.skipped++;
    Q.i++;
    this.drawQuiz();
    if (a === "save") this.loadK();
  },

  /* ── 3. glossario ── */
  drawGlossary() {
    const K = this.k; if (!K) return;
    const q = this.gq.toLowerCase();
    const terms = K.terms.filter(t => (!this.gcat || t.category === this.gcat) &&
      (!q || (t.term + " " + t.meaning + " " + (t.notes || "") + " " + (t.aliases || []).join(" ")).toLowerCase().includes(q)));
    const counts = {};
    K.terms.forEach(t => counts[t.category] = (counts[t.category] || 0) + 1);
    $("#glossary").innerHTML = `<div class="gl-h"><h3>📖 Glossario <small>${K.terms.length}</small></h3>
        <button class="btn small" data-g="add" title="Aggiungi un termine a mano">➕</button>
        <button class="btn small" data-g="export" title="Scarica il glossario (JSON)">⬇</button></div>
      <div class="search small"><span class="sicon">🔎</span><input id="glQ" type="search" placeholder="Cerca nel glossario…" value="${esc(this.gq)}"></div>
      <div class="gl-cats"><button class="fchip${this.gcat ? "" : " on"}" data-cat="">Tutti</button>${Object.entries(K.categories).filter(([k]) => counts[k]).map(([k, v]) =>
        `<button class="fchip${this.gcat === k ? " on" : ""}" data-cat="${k}" title="${esc(v)}">${CAT_ICON[k] || "•"} ${esc(v.split(" /")[0])} <span class="n">${counts[k]}</span></button>`).join("")}</div>
      <div id="glAdd"></div>
      <div class="gl-list">${terms.map(t => `<div class="gl-item" data-term="${esc(t.term)}">
        <div class="gl-t"><span class="gl-cat" title="${esc(K.categories[t.category] || "")}">${CAT_ICON[t.category] || "•"}</span><b>${esc(t.term)}</b>
          <span class="spacer"></span><button class="btn icon small" data-g="edit" title="Modifica">✏️</button><button class="btn icon small" data-g="del" title="Elimina">🗑</button></div>
        <div class="gl-m">${esc(t.meaning)}</div>${t.notes ? `<div class="gl-n">${esc(t.notes)}</div>` : ""}</div>`).join("")
        || `<div class="xnone">${K.terms.length ? "Nessun termine corrisponde." : "Il glossario è vuoto: inizia una lezione a sinistra 👈"}</div>`}</div>
      <small class="muted gl-file" title="${esc(K.file)}">💾 ${esc(K.file)}</small>`;
  },
  editForm(t) {
    t = t || {term: "", meaning: "", category: "sigla", notes: ""};
    $("#glAdd").innerHTML = `<div class="gl-form"><input type="text" id="geT" placeholder="Termine / sigla" value="${esc(t.term)}" ${t.term ? "readonly" : ""}>
      <textarea id="geM" rows="2" placeholder="Significato">${esc(t.meaning)}</textarea>
      <select id="geC">${this.catOpts(t.category)}</select><input type="text" id="geN" placeholder="Note" value="${esc(t.notes || "")}">
      <div class="ls-row"><button class="btn primary small" data-g="gsave">✔ Salva</button><button class="btn small" data-g="gcancel">Annulla</button></div></div>`;
    $(t.term ? "#geM" : "#geT").focus();
  },
  async glAct(a, el) {
    const term = el.closest("[data-term]") && el.closest("[data-term]").dataset.term;
    if (a === "add") return this.editForm();
    if (a === "gcancel") { $("#glAdd").innerHTML = ""; return; }
    if (a === "edit") return this.editForm(this.k.terms.find(t => t.term === term));
    if (a === "del") {
      if (!confirm(`Eliminare «${term}» dal glossario?`)) return;
      await api("/api/knowledge/term?term=" + encodeURIComponent(term), {method: "DELETE"});
      toast(`«${term}» eliminato`, "ok");
      return this.loadK();
    }
    if (a === "gsave") {
      try {
        await api("/api/knowledge/term", {json: {term: $("#geT").value.trim(), meaning: $("#geM").value.trim(), category: $("#geC").value, notes: $("#geN").value.trim(), source: "manuale"}});
        toast("Termine salvato", "ok");
        return this.loadK();
      } catch (e) { return toast(e.message, "bad"); }
    }
    if (a === "export") {
      const blob = new Blob([JSON.stringify(this.k.terms, null, 2)], {type: "application/json"});
      const u = URL.createObjectURL(blob), l = document.createElement("a");
      l.href = u; l.download = "glossario_asktrainmind.json"; l.click();
      setTimeout(() => URL.revokeObjectURL(u), 2000);
    }
  },
};
const CAT_ICON = {sensore: "🌡️", centralina: "🖥️", attuatore: "⚙️", rele: "🔀", segnale: "📶", sottosistema: "🏗️", concetto: "💡", sigla: "🔤", componente: "🔩"};

(() => {
  const L = window.Learn;
  $("#learnStart").addEventListener("click", e => {
    const m = e.target.closest("#lsMode button");
    if (m) { L.mode = m.dataset.m; return L.drawStart(); }
    const p = e.target.closest(".ls-pdf");
    if (p) { L.pdfSel = {fid: p.dataset.fid, file: p.dataset.file}; return L.drawStart(); }
    if (e.target.closest("#lsGo")) L.start();
  });
  $("#learnStart").addEventListener("input", e => {
    if (e.target.id === "lsPdfQ") { L.pdfQ = e.target.value; $("#lsPdfs").innerHTML = L.pdfList(L.docs ? L.docs.items : []); }
  });
  $("#learnQuiz").addEventListener("click", e => { const b = e.target.closest("[data-q]"); if (b) L.quizAct(b.dataset.q); });
  $("#learnQuiz").addEventListener("keydown", e => { if (e.key === "Enter" && e.ctrlKey) L.quizAct("save"); });
  $("#glossary").addEventListener("click", e => {
    const c = e.target.closest("[data-cat]"); if (c) { L.gcat = c.dataset.cat; return L.drawGlossary(); }
    const b = e.target.closest("[data-g]"); if (b) L.glAct(b.dataset.g, b);
  });
  $("#glossary").addEventListener("input", e => {
    if (e.target.id !== "glQ") return;
    L.gq = e.target.value;
    const pos = e.target.selectionStart;
    L.drawGlossary();
    const i = $("#glQ"); i.focus(); i.setSelectionRange(pos, pos);
  });
})();
