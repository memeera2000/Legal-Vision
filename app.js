/* Legal Vision — frontend logic (dashboard UI · v10) */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  const els = {
    health: $("#health-badge"),
    banner: $("#origin-banner"),
    bannerClose: $("#origin-banner-close"),
    pageTitle: $("#page-title"),
    pageSub: $("#page-sub"),
    sections: document.querySelectorAll(".section"),
    navItems: document.querySelectorAll(".nav-item"),
    newReview: $("#new-review"),
    dropzone: $("#dropzone"),
    fileInput: $("#file-input"),
    fileName: $("#file-name"),
    fileSize: $("#file-size"),
    fileRow: $("#file-row"),
    fileRemove: $("#file-remove"),
    analyzeBtn: $("#analyze-btn"),
    progress: $("#progress"),
    progressFill: $("#progress-fill"),
    progressStage: $("#progress-stage"),
    progressPct: $("#progress-pct"),
    progressTime: $("#progress-time"),
    redlineKicker: $("#redline-kicker"),
    redlineLegend: $("#redline-legend"),
    rlFilters: document.querySelectorAll(".rl-filter"),
    rlAll: $("#rl-all"),
    rlHigh: $("#rl-high"),
    rlMedium: $("#rl-medium"),
    rlLow: $("#rl-low"),
    rlNone: $("#rl-none"),
    rlMissing: $("#rl-missing"),
    rlMissingCount: $("#rl-missing-count"),
    scanbar: $("#scanbar"),
    scanStatus: $("#scan-status"),
    scanCount: $("#scan-count"),
    scanFill: $("#scan-fill"),
    redlineDoc: $("#redline-doc"),
    clauseDrawer: $("#clause-drawer"),
    cdMask: $("#cd-mask"),
    cdClose: $("#cd-close"),
    cdNo: $("#cd-no"),
    cdHeat: $("#cd-heat"),
    cdTitle: $("#cd-title"),
    cdText: $("#cd-text"),
    cdRules: $("#cd-rules"),
    cdChecklist: $("#cd-checklist"),
    filterBar: $("#filter-bar"),
    filterBtns: document.querySelectorAll(".filter-btn"),
    fAll: $("#f-all"),
    fPass: $("#f-pass"),
    fMissing: $("#f-missing"),
    uploadError: $("#upload-error"),
    results: $("#results"),
    scoreBadge: $("#score-badge"),
    scoreRingFill: $("#score-ring-fill"),
    scorePass: $("#score-pass-count"),
    scoreMissing: $("#score-missing-count"),
    scoreNote: $("#score-note"),
    checklistGrid: $("#checklist-grid"),
    chipsCount: $("#chips-count"),
    missingBlock: $("#missing-block"),
    missingChips: $("#missing-chips"),
    summaryBody: $("#summary-body"),
    summaryCopy: $("#summary-copy"),
    chatLog: $("#chat-log"),
    chatStatus: $("#chat-status"),
    chatForm: $("#chat-form"),
    questionInput: $("#question-input"),
    askBtn: $("#ask-btn"),
    detailModal: $("#detail-modal"),
    detailMask: $("#detail-mask"),
    detailTitle: $("#detail-title"),
    detailCount: $("#detail-count"),
    detailStatus: $("#detail-status"),
    detailSev: $("#detail-sev"),
    detailCat: $("#detail-cat"),
    detailStatusRow: $("#detail-status-row"),
    detailProtects: $("#detail-protects"),
    detailBasis: $("#detail-basis"),
    detailQuoteSec: $("#detail-quote-sec"),
    detailQuote: $("#detail-quote"),
    detailKeywords: $("#detail-keywords"),
    detailRemedy: $("#detail-remedy"),
    detailRemedyText: $("#detail-remedy-text"),
    detailPrev: $("#detail-prev"),
    detailNext: $("#detail-next"),
    detailClose: $("#detail-close"),
  };

  const state = {
    file: null,
    busy: false,
    jobTimer: null,
    timerId: null,
    onFallback: false,
    engineReachable: null,
    backendOnly: false,
    ackChecked: false,
    hasResults: false,
    activeSection: "sec-upload",
    filter: "all",
    lastChecklist: null,
    resultsItems: [],
    detailIndex: 0,
    lastSummaryRaw: "",
    redline: null,
    rlScrollLock: null,
    clauseNameIdx: {},
  };

  const POLL_MS = 1500;

  /* section → [page title, page subtitle] */
  const AREA_TITLES = {
    "sec-upload": ["Analyze a contract", "Upload, then review the results"],
    "sec-redline": ["Live redline", "Your contract, annotated clause by clause"],
    "sec-checklist": ["Compliance checklist", "Every standard protection in your contract"],
    "sec-summary": ["Plain-English summary", "Simple explanations of the dense clauses"],
    "sec-ask": ["Ask about a clause", "Get cited answers grounded in the document"],
  };

  /* ── API access ───────────────────────────────────────
     The page may be served straight from the backend (http://localhost:8000)
     OR opened from a different origin (file://, Live Server, etc.). In the
     latter case all API calls still need to reach the backend, which allows
     cross-origin access via CORS.
  */
  const BACKEND = "http://localhost:8000";

  function originBase() {
    const o = window.location.origin;
    return o && o !== "null" ? o : null;
  }

  async function rawFetch(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) {
      let detail = `HTTP ${r.status}`;
      try {
        const j = await r.json();
        if (j && j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } catch {
        /* non-JSON body */
      }
      throw Object.assign(new Error(detail), { status: r.status, url });
    }
    return r;
  }

  async function ensureAck() {
    /* Decide ONCE where the API lives.
       When the backend serves the page it injects
         window.__LEGAL_VISION_BACKEND__ = true;
       If that is present the page is served by the engine itself —
       everything goes to the same origin.
       If it's missing the page came from somewhere else (VS Code preview,
       file://, another server) — route straight to the engine. */
    if (state.ackChecked) return;
    state.ackChecked = true;
    if (window.__LEGAL_VISION_BACKEND__ === true) return;
    state.backendOnly = true;
  }

  async function api(path, opts = {}) {
    await ensureAck();
    const base = state.backendOnly ? BACKEND : originBase() || BACKEND;
    if (state.backendOnly) state.onFallback = originBase() !== BACKEND;
    else state.onFallback = false;
    const r = await rawFetch(base + path, opts);
    state.engineReachable = true;
    return r;
  }

  /* ── helpers ─────────────────────────────────────────── */
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  /* deterministic color index for free-text category names */
  const hashCat = (s) =>
    Array.from(String(s)).reduce((a, c) => (a + c.codePointAt(0)) % 997, 7) % 12;

  const setHealth = (ok, text) => {
    els.health.classList.toggle("ok", ok);
    els.health.classList.toggle("bad", !ok);
    els.health.classList.remove("checking");
    els.health.querySelector(".health-text").textContent = text;
  };

  const setBusy = (busy) => {
    state.busy = busy;
    els.analyzeBtn.disabled = busy || !state.file;
    els.askBtn.disabled = busy;
    els.questionInput.disabled = busy;
  };

  /* ── navigation ─────────────────────────────────────── */
  function showSection(name, { force = false } = {}) {
    if (name !== "sec-upload" && !state.hasResults && !force) return;
    state.activeSection = name;
    for (const sec of els.sections) sec.classList.toggle("hidden", sec.id !== name);
    for (const btn of els.navItems) btn.classList.toggle("active", btn.dataset.target === name);
    const t = AREA_TITLES[name];
    if (t) {
      els.pageTitle.textContent = t[0];
      els.pageSub.textContent = t[1];
    }
    const target = document.getElementById(name);
    if (target && target.getBoundingClientRect().top < 0) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function enableNav() {
    for (const btn of els.navItems) btn.disabled = false;
  }

  /* ── progress ────────────────────────────────────────── */
  const showProgress = (stage, pct) => {
    els.progress.classList.remove("hidden");
    els.progressFill.style.width = `${Math.round(pct * 100)}%`;
    els.progressStage.textContent = stage;
    if (els.progressPct) els.progressPct.textContent = `${Math.round(pct * 100)}%`;
  };

  const hideProgress = () => {
    els.progress.classList.add("hidden");
    if (els.progressPct) els.progressPct.textContent = "0%";
    if (state.timerId) { clearInterval(state.timerId); state.timerId = null; }
    if (elapsedStart) { elapsedStart = 0; els.progressTime.textContent = "0:00"; }
  };

  /* elapsed timer */
  let elapsedStart = 0;
  const startTimer = () => {
    if (state.timerId) return;
    elapsedStart = Date.now();
    const fmt = (ms) => {
      const s = Math.floor(ms / 1000);
      return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    };
    const t = () => { els.progressTime.textContent = fmt(Date.now() - elapsedStart); };
    t();
    state.timerId = setInterval(t, 1000);
  };

  /* ── job polling ─────────────────────────────────────── */
  async function pollJob(jobId, onUpdate) {
    const MAX_RUN_MS = 900000;      // hard cap: 15 min
    const STALL_WARN_MS = 120000;   // warn if the bar hasn't moved in 2 min
    const started = Date.now();
    let lastSig = null;
    let lastChangeAt = started;
    let stallWarned = false;
    return new Promise((resolve, reject) => {
      const tick = async () => {
        if (Date.now() - started > MAX_RUN_MS) {
          return reject(
            new Error(
              "Analysis timed out after 15 minutes. The engine may have stopped responding. Re-upload the contract, or restart via start.bat."
            )
          );
        }
        try {
          const r = await api(`/api/jobs/${jobId}`);
          if (!r.ok) {
            let msg = `Server error (HTTP ${r.status})`;
            try {
              const j = await r.json();
              if (j && j.detail) msg = j.detail;
            } catch { /* keep default msg */ }
            if (r.status === 404)
              msg += " — the engine restarted while analyzing. Run start.bat (or python backend.py) and upload the contract again.";
            return reject(new Error(msg));
          }
          const job = await r.json();
          if (job.status === "done") return resolve(job.result);
          if (job.status === "error") return reject(new Error(job.error || "Job failed."));

          const sig = `${job.stage || ""}|${Math.round((job.progress || 0) * 1000)}`;
          if (sig !== lastSig) {
            lastSig = sig;
            lastChangeAt = Date.now();
            stallWarned = false;
          }
          onUpdate?.(job);
          if (!stallWarned && Date.now() - lastChangeAt > STALL_WARN_MS) {
            stallWarned = true;
            onUpdate?.({
              stage: `${job.stage || "Analyzing"} — still working, this can take a few minutes…`,
              progress: job.progress || 0,
            });
          }
          state.jobTimer = setTimeout(tick, POLL_MS);
        } catch (e) {
          reject(e);
        }
      };
      tick();
    });
  }

  /* ── upload & analyze ───────────────────────────────── */
  async function analyze() {
    if (!state.file || state.busy) return;
    setBusy(true);
    els.uploadError.classList.add("hidden");
    els.results.classList.add("hidden");
    els.chatLog.innerHTML = "";
    state.filter = "all";
    for (const btn of els.filterBtns) btn.classList.toggle("active", btn.dataset.filter === "all");
    showProgress("Uploading contract…", 0.02);
    startTimer();
    try {
      const fd = new FormData();
      fd.append("file", state.file);
      const r = await api("/api/upload", { method: "POST", body: fd });
      const { job_id } = await r.json();
      if (!job_id) throw new Error("No job id returned by the server.");

      const result = await pollJob(job_id, (job) => {
        if (job.stage) showProgress(job.stage, job.progress || 0);
      });

      renderResults(result);
      hideProgress();
    } catch (e) {
      hideProgress();
      els.uploadError.textContent = `Analysis failed: ${e.message}`;
      els.uploadError.classList.remove("hidden");
    } finally {
      setBusy(false);
    }
  }

  /* ── render results ─────────────────────────────────── */
  function renderResults(result) {
    renderChecklist(result.checklist);
    renderRedline(result.redline);
    renderSummary(result.summary || result.report);
    state.hasResults = true;
    enableNav();
    els.results.classList.remove("hidden");
    showSection("sec-redline", { force: true });
  }

  function renderChecklist(checklist) {
    els.checklistGrid.innerHTML = "";
    const total = checklist.total || 0;
    const passed = checklist.passed || 0;
    const missing = checklist.missing || 0;
    const pct = total ? passed / total : 0;

    els.scoreBadge.textContent = `${passed}/${total}`;
    els.scorePass.textContent = passed;
    els.scoreMissing.textContent = missing;
    els.chipsCount.textContent = `${total} checks`;

    if (els.fAll) els.fAll.textContent = total;
    if (els.fPass) els.fPass.textContent = passed;
    if (els.fMissing) els.fMissing.textContent = missing;

    /* score ring: muted spectrum instead of traffic-light colors */
    const circ = 326.7;
    const color = pct === 0 ? "#ef4444" : pct < 0.4 ? "#ef4444" : pct <= 0.7 ? "#f59e0b" : "#22c55e";
    els.scoreRingFill.style.transition = "none";
    els.scoreRingFill.style.strokeDashoffset = String(circ);
    void els.scoreRingFill.getBoundingClientRect();
    els.scoreRingFill.style.transition = "";
    requestAnimationFrame(() => {
      els.scoreRingFill.style.stroke = color;
      els.scoreRingFill.style.strokeDashoffset = String(circ * (1 - pct));
    });

    if (missing === 0) {
      els.scoreNote.textContent = "Excellent — every standard protection was found in this contract.";
    } else if (pct >= 0.7) {
      els.scoreNote.textContent = `Strong coverage: ${passed} of ${total} standard protections found. Review the missing clauses below before signing.`;
    } else if (pct >= 0.4) {
      els.scoreNote.textContent = `Partial coverage: ${missing} common protections are absent. Consider adding the missing clauses before signing.`;
    } else {
      els.scoreNote.textContent = `Low coverage: only ${passed} of ${total} standard protections found. Strongly consider revising before signing.`;
    }

    for (let i = 0; i < checklist.results.length; i++) {
      const item = checklist.results[i];
      const pass = item.status === "pass";

      const card = document.createElement("div");
      card.className = `check-card ${pass ? "pass" : "missing"}`;
      card.dataset.status = pass ? "pass" : "missing";
      card.style.animationDelay = `${Math.min(i * 0.03, 0.5)}s`;
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      card.setAttribute("aria-haspopup", "dialog");
      card.setAttribute("aria-label", `View details for ${item.name}`);
      card.addEventListener("click", (e) => { e.stopPropagation(); openDetail(i); });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDetail(i); }
      });

      /* top row: dot + title + status tag */
      const top = document.createElement("div");
      top.className = "card-top";

      const dot = document.createElement("span");
      dot.className = `status-dot ${pass ? "pass" : "missing"}`;
      top.appendChild(dot);

      const title = document.createElement("h3");
      title.className = "card-title";
      title.textContent = item.name;
      top.appendChild(title);

      const tag = document.createElement("span");
      tag.className = "status-tag";
      const badge = document.createElement("span");
      badge.className = `badge ${pass ? "pass" : "missing"}`;
      badge.innerHTML =
        (pass
          ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
          : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>') +
        esc(pass ? "Present" : "Missing");
      tag.appendChild(badge);
      top.appendChild(tag);
      card.appendChild(top);

      /* category + severity line */
      const sev = (item.severity || "medium").toLowerCase();
      const cat = document.createElement("span");
      cat.className = "card-cat";
      cat.textContent = (item.category ? `${item.category} · ` : "") + sev;
      card.appendChild(cat);

      /* explanation line */
      if (item.explanation) {
        const why = document.createElement("p");
        why.className = "card-why";
        why.textContent = item.explanation;
        card.appendChild(why);
      }

      /* matched language quote */
      if (item.matched_text) {
        const q = document.createElement("blockquote");
        q.className = "basis-quote";
        q.textContent = `"${item.matched_text}"`;
        card.appendChild(q);
      }

      /* footer */
      const foot = document.createElement("div");
      foot.className = "card-footer";
      const more = document.createElement("span");
      more.className = "card-more";
      more.textContent = "View details";
      const chev = document.createElement("span");
      chev.className = "chev";
      chev.innerHTML = "&#8594;";
      more.appendChild(chev);
      foot.appendChild(more);
      if (!pass) {
        const flag = document.createElement("span");
        flag.className = "card-remedy-flag";
        flag.textContent = "Add before signing";
        foot.appendChild(flag);
      }
      card.appendChild(foot);

      els.checklistGrid.appendChild(card);
    }

    state.lastChecklist = checklist;
    state.resultsItems = checklist.results || [];
    state.detailIndex = 0;
    applyFilter(state.filter);

    if (checklist.missing_names?.length) {
      els.missingBlock.classList.remove("hidden");
      els.missingChips.innerHTML = "";
      for (const name of checklist.missing_names) {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = name;
        els.missingChips.appendChild(chip);
      }
    } else {
      els.missingBlock.classList.add("hidden");
    }
  }

  function renderSummary(md) {
    state.lastSummaryRaw = md || "_No summary available._";
    els.summaryBody.innerHTML = renderMarkdown(state.lastSummaryRaw);
  }

  /* ── live redline ─────────────────────────────────── */
  const RL_SEV_LABEL = { high: "Critical heat", medium: "Watch", low: "Low", none: "Standard" };

  function renderRedline(data) {
    if (!data) data = { clauses: [], hot: { high: 0, medium: 0, low: 0 }, missing_count: 0 };

    /* cancel any in-flight scan before re-rendering */
    if (state.rlScrollLock) {
      cancelAnimationFrame(state.rlScrollLock);
      state.rlScrollLock = null;
    }

    state.redline = data;
    state.clauseNameIdx = {};
    (state.resultsItems || []).forEach((it, i) => { state.clauseNameIdx[it.name] = i; });

    const hot = data.hot || {};
    const flagged = (hot.high || 0) + (hot.medium || 0) + (hot.low || 0);
    els.rlAll.textContent = data.clauses.length;
    els.rlHigh.textContent = hot.high || 0;
    els.rlMedium.textContent = hot.medium || 0;
    els.rlLow.textContent = hot.low || 0;
    els.rlNone.textContent = Math.max(0, data.clauses.length - flagged);
    els.rlMissingCount.textContent = data.missing_count || 0;
    els.redlineKicker.textContent = `${data.clauses.length} clauses · ${flagged} flagged`;

    state.rlFilter = "all";
    for (const b of els.rlFilters) b.classList.toggle("active", b.dataset.filter === "all");

    const doc = els.redlineDoc;
    doc.innerHTML = "";
    doc.classList.remove("scanned");
    const clauseEls = [];

    data.clauses.forEach((c) => {
      const art = document.createElement("article");
      art.className = `clause ${c.heat !== "none" ? "hot-" + c.heat : ""}`;
      art.dataset.idx = String(c.idx);
      art.dataset.sev = c.heat || "none";
      art.setAttribute("role", "button");
      art.setAttribute("tabindex", "0");
      art.setAttribute("aria-label", `Clause ${c.idx + 1}: ${c.head || "clause"}`);

      const textEl = document.createElement("div");
      textEl.className = "clause-body";
      if (c.head) {
        const hline = document.createElement("div");
        hline.className = "clause-head-line";
        const h = document.createElement("span");
        h.className = "clause-head";
        h.textContent = c.head;
        const dot = document.createElement("i");
        dot.className = `clause-dot ${c.heat !== "none" ? "hd-" + c.heat : "hd-none"}`;
        hline.appendChild(h);
        hline.appendChild(dot);
        textEl.appendChild(hline);
      }

      let txt = String(c.text || "").trim();
      if (c.head && txt.indexOf("\n") !== -1 && txt.split("\n")[0].trim() === c.head) {
        txt = txt.split("\n").slice(1).join("\n").trim();
      }
      const p = document.createElement("p");
      p.className = "clause-text";
      p.textContent = txt;
      textEl.appendChild(p);

      if (c.rules && c.rules.length) {
        const rr = document.createElement("div");
        rr.className = "clause-rules";
        for (const rule of c.rules) {
          const chip = document.createElement("span");
          chip.className = `clause-rule-chip sev-${rule.severity || "low"}`;
          chip.textContent = rule.name;
          chip.title = `${rule.severity || "low"} severity · ${rule.category || ""}`;
          rr.appendChild(chip);
        }
        textEl.appendChild(rr);
      }

      const no = document.createElement("span");
      no.className = "clause-no";
      no.textContent = String(c.idx + 1);

      art.appendChild(no);
      art.appendChild(textEl);
      art.addEventListener("click", () => openClause(c.idx));
      art.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openClause(c.idx); }
      });
      doc.appendChild(art);
      clauseEls.push(art);
    });

    playScan(clauseEls);
  }

  function playScan(clauseEls) {
    const total = clauseEls.length;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    els.scanbar.classList.remove("hidden");
    els.scanStatus.textContent = total ? "Reading your contract…" : "No clauses extracted";
    els.scanCount.textContent = `0 / ${total}`;
    els.scanFill.style.width = "0%";

    const finish = () => {
      for (const el of clauseEls) el.classList.add("seen");
      els.redlineDoc.classList.add("scanned");
      const flagged = els.redlineDoc.querySelectorAll(".clause.hot-high, .clause.hot-medium, .clause.hot-low").length;
      els.scanCount.textContent = `${total} / ${total}`;
      els.scanFill.style.width = "100%";
      els.scanStatus.textContent = total
        ? `Scanned ${total} clauses — ${flagged} flagged for review`
        : "No clauses extracted";
      state.rlScrollLock = null;
    };
    if (reduced || total === 0) { finish(); return; }

    const DUR = Math.min(3400, 1300 + total * 55);
    const start = performance.now();

    const tick = (t) => {
      const p = Math.min(1, (t - start) / DUR);
      const seen = Math.min(total - 1, Math.floor(p * total));
      for (let i = 0; i <= seen; i++) clauseEls[i].classList.add("seen");
      els.scanFill.style.width = `${Math.round(p * 100)}%`;
      els.scanCount.textContent = `${seen + 1} / ${total}`;
      if (p < 1) {
        state.rlScrollLock = requestAnimationFrame(tick);
      } else {
        finish();
      }
    };
    state.rlScrollLock = requestAnimationFrame(tick);
  }

  function applyRLFilter(sev) {
    state.rlFilter = sev;
    for (const b of els.rlFilters) b.classList.toggle("active", b.dataset.filter === sev);
    const cards = els.redlineDoc.querySelectorAll(".clause");
    for (const card of cards) {
      const show = sev === "all" || card.dataset.sev === sev;
      card.classList.toggle("hidden", !show);
    }
  }

  function openClause(idx) {
    const data = state.redline;
    if (!data) return;
    const c = data.clauses.find((x) => x.idx === idx);
    if (!c) return;
    els.cdNo.textContent = `#${c.idx + 1}`;
    els.cdHeat.textContent = RL_SEV_LABEL[c.heat || "none"];
    els.cdHeat.className = `cd-heat hd-lab-${c.heat || "none"}`;
    els.cdTitle.textContent = c.head || `Clause ${c.idx + 1}`;

    let txt = String(c.text || "").trim();
    if (c.head && txt.indexOf("\n") !== -1 && txt.split("\n")[0].trim() === c.head) {
      txt = txt.split("\n").slice(1).join("\n").trim();
    }
    els.cdText.textContent = txt;

    els.cdRules.innerHTML = "";
    if (c.rules && c.rules.length) {
      for (const rule of c.rules) {
        const row = document.createElement("button");
        row.type = "button";
        row.className = `clause-rule sev-${rule.severity || "low"}`;
        row.dataset.name = rule.name;
        const dot = document.createElement("i");
        dot.className = `clause-dot hd-${rule.severity || "low"}`;
        const info = document.createElement("div");
        info.className = "clause-rule-info";
        const name = document.createElement("span");
        name.className = "clause-rule-name";
        name.textContent = rule.name;
        const cat = document.createElement("span");
        cat.className = "clause-rule-cat";
        cat.textContent = `${rule.category || ""} · ${rule.severity || "low"}`;
        info.appendChild(name);
        info.appendChild(cat);
        if (rule.matched) {
          const m = document.createElement("span");
          m.className = "clause-rule-match";
          m.textContent = `"${rule.matched}"`;
          info.appendChild(m);
        }
        const go = document.createElement("span");
        go.className = "clause-rule-go";
        go.textContent = "Open details";
        row.appendChild(dot);
        row.appendChild(info);
        row.appendChild(go);
        row.addEventListener("click", () => {
          const itemIdx = state.clauseNameIdx[rule.name];
          closeClause();
          if (itemIdx !== undefined && itemIdx !== null) openDetail(itemIdx);
        });
        els.cdRules.appendChild(row);
      }
    } else {
      const none = document.createElement("p");
      none.className = "muted drawer-none";
      none.textContent = "No standard-protection rule concentrated in this clause — appears to be routine boilerplate.";
      els.cdRules.appendChild(none);
    }

    els.clauseDrawer.classList.remove("hidden");
    document.body.classList.add("drawer-open");
    els.cdClose.focus();
  }

  function closeClause() {
    els.clauseDrawer.classList.add("hidden");
    document.body.classList.remove("drawer-open");
  }

  /* ── filter checklist by status ──────────────────────── */
  function applyFilter(filter) {
    state.filter = filter;
    for (const btn of els.filterBtns) btn.classList.toggle("active", btn.dataset.filter === filter);
    const cards = els.checklistGrid.querySelectorAll(".check-card");
    for (const card of cards) {
      const show =
        filter === "all" ||
        card.dataset.status === filter ||
        (filter === "pass" && card.dataset.status === "pass");
      card.classList.toggle("hidden", !show);
    }
  }

  /* ── details modal ───────────────────────────────────── */
  function openDetail(index) {
    const items = state.resultsItems;
    if (!items || !items.length) return;
    state.detailIndex = Math.max(0, Math.min(index, items.length - 1));
    const item = items[state.detailIndex];
    const pass = item.status === "pass";
    const sev = (item.severity || "medium").toLowerCase();

    els.detailTitle.textContent = item.name;
    els.detailCount.textContent = `${state.detailIndex + 1} / ${items.length}`;

    els.detailStatus.className = `badge ${pass ? "pass" : "missing"}`;
    els.detailStatus.innerHTML =
      (pass
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>') +
      (pass ? " Present" : " Missing");
    els.detailStatusRow.className = `detail-status-row ${pass ? "is-pass" : "is-miss"}`;

    els.detailSev.className = `sev-chip ${sev}`;
    els.detailSev.textContent = sev;

    els.detailCat.className = `chip-cat cat-${hashCat(item.category || "")}`;
    els.detailCat.textContent = item.category || "General";

    els.detailProtects.textContent =
      item.description || "This standard protection is part of the compliance checklist.";
    els.detailBasis.textContent = item.explanation || "No basis recorded.";

    if (item.matched_text) {
      els.detailQuote.textContent = `"${item.matched_text}"`;
      els.detailQuoteSec.classList.remove("hidden");
    } else {
      els.detailQuoteSec.classList.add("hidden");
    }

    els.detailKeywords.innerHTML = "";
    const kws = item.keywords || [];
    if (kws.length) {
      for (const kw of kws) {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = kw;
        els.detailKeywords.appendChild(chip);
      }
    } else {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = "keyword match";
      els.detailKeywords.appendChild(chip);
    }

    if (!pass) {
      els.detailRemedyText.textContent =
        "This protection is not addressed in the contract. Before signing, consider " +
        "adding a clause that covers these terms and expressly states the parties' " +
        "obligations.";
      els.detailRemedy.classList.remove("hidden");
    } else {
      els.detailRemedy.classList.add("hidden");
    }

    els.detailPrev.disabled = state.detailIndex === 0;
    els.detailNext.disabled = state.detailIndex === items.length - 1;

    els.detailModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    els.detailClose.focus();
  }

  function closeDetail() {
    els.detailModal.classList.add("hidden");
    document.body.classList.remove("modal-open");
  }

  /* ── chat ───────────────────────────────────────────── */
  function addChat(type, html) {
    const div = document.createElement("div");
    div.className = `msg ${type === "user" ? "msg-user" : "msg-ai"}`;
    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = type === "user" ? "You" : "AI";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = html;
    div.appendChild(avatar);
    div.appendChild(bubble);
    els.chatLog.appendChild(div);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
    return div;
  }

  function addTyping() {
    const div = document.createElement("div");
    div.className = "msg msg-ai";
    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = "AI";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const typing = document.createElement("span");
    typing.className = "typing";
    typing.innerHTML = "<i></i><i></i><i></i>";
    bubble.appendChild(typing);
    div.appendChild(avatar);
    div.appendChild(bubble);
    els.chatLog.appendChild(div);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
    return div;
  }

  async function ask() {
    const q = els.questionInput.value.trim();
    if (!q || state.busy) return;
    setBusy(true);
    addChat("user", esc(q));
    els.questionInput.value = "";
    const typing = addTyping();
    els.chatStatus.textContent = "Retrieving the clause and generating a cited answer…";
    try {
      const r = await api("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await r.json();
      if (!data.job_id) throw new Error("No job id returned by the server.");

      const result = await pollJob(data.job_id, (job) => {
        els.chatStatus.textContent = job.stage || "Working…";
      });

      typing.remove();
      const html = renderMarkdown(result.answer || "_No answer produced._") +
        (result.citation
          ? `<div class="citation">${esc(result.citation)}</div>`
          : "");
      addChat("bot", html);
      els.chatStatus.textContent = "";
    } catch (e) {
      typing.remove();
      addChat("bot", `<b>Error:</b> ${esc(e.message)}`);
      els.chatStatus.textContent = "";
    } finally {
      setBusy(false);
      els.questionInput.focus();
    }
  }

  /* ── tiny markdown renderer (escaped → html) ────────── */
  function renderMarkdown(raw) {
    const lines = String(raw ?? "").split("\n");
    const out = [];
    let listType = null;

    const closeList = () => {
      if (listType) { out.push(`</${listType}>`); listType = null; }
    };

    for (let line of lines) {
      const inline = (t) =>
        esc(t)
          .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
          .replace(/(^|[^*])\*([^*]+?)\*(?!\*)/g, "$1<em>$2</em>")
          .replace(/`([^`]+)`/g, "<code>$1</code>");

      const s = line.trim();

      if (s === "") { closeList(); continue; }
      if (/^---+$/.test(s)) { closeList(); out.push("<hr />"); continue; }

      let m;
      if ((m = s.match(/^#{1,3}\s+(.*)$/))) {
        closeList();
        const level = s.startsWith("###") ? 4 : s.startsWith("##") ? 3 : 2;
        out.push(`<h${level}>${inline(m[1])}</h${level}>`);
        continue;
      }
      if ((m = s.match(/^>\s?(.*)$/))) {
        closeList();
        out.push(`<blockquote>${inline(m[1])}</blockquote>`);
        continue;
      }
      if ((m = s.match(/^\s*[-*]\s+(.*)$/))) {
        if (listType !== "ul") { closeList(); out.push("<ul>"); listType = "ul"; }
        out.push(`<li>${inline(m[1])}</li>`);
        continue;
      }
      if ((m = s.match(/^\s*\d+[.)]\s+(.*)$/))) {
        if (listType !== "ol") { closeList(); out.push("<ol>"); listType = "ol"; }
        out.push(`<li>${inline(m[1])}</li>`);
        continue;
      }
      closeList();
      out.push(`<p>${inline(s)}</p>`);
    }
    closeList();
    return out.join("\n");
  }

  /* ── health & engine check ──────────────────────────── */
  let healthFails = 0; // require several consecutive failures before alarming

  async function refreshHealth() {
    try {
      const r = await api("/api/health");
      const h = await r.json();
      healthFails = 0;
      state.engineReachable = true;
      if (h.ollama) {
        setHealth(true, state.onFallback ? `Engine ready · ${h.model} (cross-origin)` : `Engine ready · ${h.model}`);
      } else {
        setHealth(false, "Ollama unreachable — check it is running");
      }
    } catch {
      healthFails += 1;
      if (healthFails >= 3) {
        state.engineReachable = false;
        setHealth(false, "Engine offline — run start.bat");
      } else {
        state.engineReachable = true; // keep retrying; engine may still be starting
        setHealth(false, "Starting engine…");
      }
    }
    maybeShowBanner();
  }

  function maybeShowBanner() {
    if (state.engineReachable === false) {
      els.banner.classList.remove("hidden");
    } else {
      els.banner.classList.add("hidden");
    }
  }

  /* ── wire up ────────────────────────────────────────── */
  function setFile(file) {
    state.file = file;
    if (file) {
      els.fileName.textContent = file.name;
      els.fileSize.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB (` + (file.size / 1024).toFixed(0) + " KB)";
      els.fileRow.classList.remove("hidden");
      els.dropzone.classList.add("has-file");
    } else {
      els.fileRow.classList.add("hidden");
      els.dropzone.classList.remove("has-file");
    }
    els.analyzeBtn.disabled = !file || state.busy;
  }

  els.dropzone.addEventListener("click", () => els.fileInput.click());
  els.dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); els.fileInput.click(); }
  });
  els.fileInput.addEventListener("change", (e) => setFile(e.target.files[0] || null));
  els.fileRemove.addEventListener("click", () => { setFile(null); els.fileInput.value = ""; });

  ["dragenter", "dragover"].forEach((ev) =>
    els.dropzone.addEventListener(ev, (e) => { e.preventDefault(); els.dropzone.classList.add("dragover"); })
  );
  ["dragleave", "drop"].forEach((ev) =>
    els.dropzone.addEventListener(ev, (e) => { e.preventDefault(); els.dropzone.classList.remove("dragover"); })
  );
  els.dropzone.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0] || null));

  els.analyzeBtn.addEventListener("click", analyze);
  els.askBtn.addEventListener("click", (e) => { e.preventDefault(); ask(); });
  els.chatForm.addEventListener("submit", (e) => { e.preventDefault(); ask(); });
  els.questionInput.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });
  if (els.bannerClose) els.bannerClose.addEventListener("click", () => els.banner.classList.add("hidden"));
  for (const btn of els.filterBtns) {
    btn.addEventListener("click", () => applyFilter(btn.dataset.filter || "all"));
  }

  for (const btn of els.rlFilters) {
    btn.addEventListener("click", () => applyRLFilter(btn.dataset.filter || "all"));
  }
  if (els.rlMissing) {
    els.rlMissing.addEventListener("click", () => showSection("sec-checklist"));
  }
  if (els.cdClose) els.cdClose.addEventListener("click", closeClause);
  if (els.cdMask) els.cdMask.addEventListener("click", closeClause);
  if (els.cdChecklist) {
    els.cdChecklist.addEventListener("click", () => { closeClause(); showSection("sec-checklist"); });
  }

  for (const btn of els.navItems) {
    btn.addEventListener("click", () => showSection(btn.dataset.target));
  }
  if (els.newReview) els.newReview.addEventListener("click", () => window.location.reload());

  /* details modal wiring */
  if (els.detailClose) els.detailClose.addEventListener("click", closeDetail);
  if (els.detailMask) els.detailMask.addEventListener("click", closeDetail);
  if (els.detailPrev) els.detailPrev.addEventListener("click", () => openDetail(state.detailIndex - 1));
  if (els.detailNext) els.detailNext.addEventListener("click", () => openDetail(state.detailIndex + 1));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !els.detailModal.classList.contains("hidden")) closeDetail();
    if (e.key === "Escape" && !els.clauseDrawer.classList.contains("hidden")) closeClause();
    if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && !els.detailModal.classList.contains("hidden")) {
      openDetail(state.detailIndex + (e.key === "ArrowRight" ? 1 : -1));
    }
  });
  if (els.detailModal) {
    els.detailModal.addEventListener("click", (e) => {
      if (e.target === els.detailModal) closeDetail();
    });
  }

  if (els.summaryCopy) {
    els.summaryCopy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(state.lastSummaryRaw || els.summaryBody.innerText);
        els.summaryCopy.textContent = "Copied";
        setTimeout(() => { els.summaryCopy.textContent = "Copy"; }, 1500);
      } catch {
        els.summaryCopy.textContent = "Copy failed";
      }
    });
  }

  window.addEventListener("error", (e) => {
    const box = els.uploadError;
    if (box) {
      box.textContent = `Frontend error: ${e.message}`;
      box.classList.remove("hidden");
    }
  });

  /* ── live background: "the case file" ──────────────────────────────
     A drifting stack of open documents. As each page rises, its ink draws
     itself in line by line; some lines get an indigo review-wash, others a
     redline squiggle, and golden § glyphs pulse in the margins — a quiet,
     living "contract being analyzed" scene behind the glass panels.
  */
  function initBackground() {
    const canvas = document.getElementById("bg-canvas");
    if (!canvas) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let PAPER = "255,255,255";
    let INK = "82,95,120";
    let INDIGO = "92,107,248";
    let GOLD = "202,138,4";
    let RED = "220,38,38";

    function applyThemePalette() {
      const dark = document.documentElement.getAttribute("data-theme") === "dark";
      if (dark) {
        PAPER = "30,35,50";
        INK = "120,132,164";
        INDIGO = "124,138,254";
        GOLD = "230,168,44";
        RED = "248,92,112";
      } else {
        PAPER = "255,255,255";
        INK = "82,95,120";
        INDIGO = "92,107,248";
        GOLD = "202,138,4";
        RED = "220,38,38";
      }
    }
    applyThemePalette();


    let w = 0, h = 0, rafId = null, running = true, t = 0;
    let mouseX = 0, mouseY = 0, parX = 0, parY = 0;
    const pages = [];
    const sparks = [];

    const rand = (a, b) => a + Math.random() * (b - a);
    const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

    function rr(x, y, wd, ht, r) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + wd, y, x + wd, y + ht, r);
      ctx.arcTo(x + wd, y + ht, x, y + ht, r);
      ctx.arcTo(x, y + ht, x, y, r);
      ctx.arcTo(x, y, x + wd, y, r);
      ctx.closePath();
    }

    function makePage() {
      const pw = rand(150, 290);
      const ph = pw * rand(1.28, 1.48);
      const n = 6 + ((Math.random() * 5) | 0);
      const padL = 22;
      const lines = [];
      for (let i = 0; i < n; i++) {
        const lw = rand(0.5, 0.96) * (pw - padL - pw * 0.2);
        lines.push({
          y: (i + 0.5) * (ph - 46) / n + 24,
          x: padL + rand(-4, 8),
          w: lw,
          p0: rand(0.04, 0.5) + i * 0.02,
          highlight: Math.random() < 0.22,
          squiggle: Math.random() < 0.3,
        });
      }
      return {
        x: rand(0, w), y: -180 - rand(0, h),
        pw, ph,
        rot: rand(-0.09, 0.09),
        vy: rand(0.12, 0.3), vx: rand(-0.06, 0.06),
        omega: rand(-8e-5, 8e-5),
        age: rand(0, 46), life: rand(70, 120),
        phase: rand(0, Math.PI * 2),
        gold: Math.random() < 0.55,
        lines,
      };
    }

    function positions() {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      pages.length = 0;
      const total = Math.max(9, Math.min(20, Math.round((w * h) / 110000)));
      for (let i = 0; i < total; i++) pages.push(makePage());

      sparks.length = 0;
      const count = Math.max(8, Math.min(22, Math.round(w / 90)));
      for (let i = 0; i < count; i++) {
        sparks.push({
          x: Math.random() * w, y: Math.random() * h,
          r: rand(0.6, 1.7), vy: rand(0.05, 0.22),
          ph: Math.random() * Math.PI * 2, sway: rand(0.2, 0.6),
          a: rand(0.08, 0.2), col: Math.random() < 0.45 ? GOLD : INDIGO,
        });
      }
    }

    function drawPage(pg) {
      const p = clamp(pg.age / pg.life, 0, 1);
      const fade = p < 0.06 ? p / 0.06 : p > 0.9 ? Math.max(0, (1 - p) / 0.1) : 1;
      if (fade <= 0) return;

      const sway = Math.sin(t * 0.01 + pg.phase) * 7;
      const depth = clamp(pg.pw / 320, 0.35, 1);
      const dx = parX * (14 * depth);
      const dy = parY * (9 * depth);

      ctx.save();
      ctx.translate(pg.x + dx, pg.y + sway + dy);
      ctx.rotate(pg.rot + Math.sin(t * 0.005 + pg.phase) * 0.015);

      const { pw, ph } = pg;
      const shellA = 0.5 * fade;

      const grad = ctx.createLinearGradient(0, 0, 0, ph);
      grad.addColorStop(0, `rgba(${PAPER},${(0.85 * shellA).toFixed(3)})`);
      grad.addColorStop(1, `rgba(${PAPER},${(0.55 * shellA).toFixed(3)})`);
      rr(0, 0, pw, ph, 10);
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.strokeStyle = `rgba(${INK},${(0.22 * shellA).toFixed(3)})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      if (pg.gold) {
        const pulse = 0.5 + 0.5 * Math.sin(t * 0.02 + pg.phase);
        ctx.fillStyle = `rgba(${GOLD},${((0.45 + 0.5 * pulse) * shellA).toFixed(3)})`;
        ctx.font = "700 16px ui-monospace, 'Cascadia Code', Consolas, monospace";
        ctx.fillText("\u00A7", 9, 19);
      }

      rr(0, 0, pw, ph, 10);
      ctx.clip();

      for (const ln of pg.lines) {
        const q = clamp((p - ln.p0) / 0.12, 0, 1);
        if (q <= 0) continue;

        if (ln.highlight && q > 0.5) {
          const ha = Math.min(1, (q - 0.5) / 0.3) * 0.2 * shellA;
          ctx.fillStyle = `rgba(${INDIGO},${ha.toFixed(3)})`;
          ctx.fillRect(ln.x - 2, ln.y - 5, ln.w + 6, 4);
        }

        ctx.fillStyle = `rgba(${INK},${((0.34 * q + 0.06) * shellA).toFixed(3)})`;
        rr(ln.x, ln.y - 1, ln.w * q, 2.6, 1.3);
        ctx.fill();

        if (ln.squiggle && q > 0.72) {
          const sq = Math.min(1, (q - 0.72) / 0.28);
          const len = ln.w * sq;
          const y = ln.y + 4.5;
          const nz = Math.max(2, Math.round(len / 7));
          ctx.strokeStyle = `rgba(${RED},${(0.55 * shellA).toFixed(3)})`;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          for (let i = 0; i <= nz; i++) {
            const x = ln.x + (i / nz) * len;
            const yy = y + (i % 2 === 0 ? 1.8 : -1.8);
            if (i === 0) ctx.moveTo(x, yy);
            else ctx.lineTo(x, yy);
          }
          ctx.stroke();
        }
      }

      ctx.restore();
    }

    function drawFrame() {
      t += 1;
      parX += (mouseX - parX) * 0.045;
      parY += (mouseY - parY) * 0.045;

      ctx.clearRect(0, 0, w, h);

      for (const pg of pages) {
        pg.age += 1 / 60;
        pg.x += pg.vx + Math.sin(t * 0.004 + pg.phase) * 0.15;
        pg.y -= pg.vy;
        pg.rot += pg.omega;

        if (pg.y < -pg.ph - 120) {
          const fresh = makePage();
          fresh.x = rand(0, w);
          fresh.y = -fresh.ph - rand(30, 160);
          Object.assign(pg, fresh);
        }
        if (pg.x < -pg.pw - 120 || pg.x > w + pg.pw + 120) {
          Object.assign(pg, makePage(), { age: 0 });
        }
        drawPage(pg);
      }

      for (const sp of sparks) {
        sp.y -= sp.vy;
        sp.x += Math.sin(sp.ph) * 0.12;
        sp.ph += 0.006 + sp.sway * 0.003;
        if (sp.y < -8) { sp.y = h + 8; sp.x = Math.random() * w; }
        if (sp.x < -8) sp.x = w + 8;
        else if (sp.x > w + 8) sp.x = -8;
        ctx.beginPath();
        ctx.arc(sp.x, sp.y, sp.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${sp.col},${(sp.a * (0.6 + 0.4 * Math.sin(sp.ph))).toFixed(3)})`;
        ctx.fill();
      }

      rafId = requestAnimationFrame(drawFrame);
    }

    window.addEventListener("mousemove", (e) => {
      mouseX = (e.clientX / Math.max(1, w)) * 2 - 1;
      mouseY = (e.clientY / Math.max(1, h)) * 2 - 1;
    }, { passive: true });

    positions();
    if (reduced) {
      for (const pg of pages) { pg.age = pg.life * 0.5; drawPage(pg); }
      for (const sp of sparks) {
        ctx.beginPath();
        ctx.arc(sp.x, sp.y, sp.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${sp.col},${sp.a})`;
        ctx.fill();
      }
    } else {
      rafId = requestAnimationFrame(drawFrame);
    }

    let resizeT;
    window.addEventListener("resize", () => {
      clearTimeout(resizeT);
      resizeT = setTimeout(() => {
        w = window.innerWidth;
        h = window.innerHeight;
        canvas.width = Math.max(1, Math.round(w * dpr));
        canvas.height = Math.max(1, Math.round(h * dpr));
        canvas.style.width = w + "px";
        canvas.style.height = h + "px";
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        positions();
      }, 150);
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        running = false;
        if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
      } else if (!reduced && !running) {
        running = true;
        rafId = requestAnimationFrame(drawFrame);
      }
    });

    /* Re-tint + re-seed hook for the theme controller (lives outside this
       closure): recolors the palette vars and rebuilds pages/sparks so the
       light/dark switch takes effect on the live canvas immediately. */
    window.__lvReseedBg = () => {
      applyThemePalette();
      positions();
    };

    window.addEventListener("beforeunload", () => {
      running = false;
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    });
  }

  initBackground();
  refreshHealth();
  els.health.classList.add("checking");
  setInterval(refreshHealth, 5000);

  /* ── color theme controller ─────────────────────────────────────────
     Light/dark. The toggle button lives in the topbar (#theme-toggle).
     Bootstrapped state (set pre-paint in <head>) wins until the user
     flips it; once flipped we persist to localStorage and re-tint the
     live canvas so pages/sparks re-seed with the light/dark palette.
  */
  const metaTheme = document.querySelector('meta[name="theme-color"]');
  const setTheme = (t, persist) => {
    document.documentElement.setAttribute("data-theme", t);
    if (metaTheme) {
      metaTheme.setAttribute("content", t === "dark" ? "#080d1c" : "#f3f5fa");
    }
    if (persist) {
      try { localStorage.setItem("lv-theme", t); } catch (e) {}
    }
  };

    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        const dark = document.documentElement.getAttribute("data-theme") === "dark";
        const next = dark ? "light" : "dark";
        setTheme(next, true);
        document.documentElement.classList.add("animating");
        queueMicrotask(() => document.documentElement.classList.remove("animating"));
        if (window.__lvReseedBg) window.__lvReseedBg();
      });
    }

  window.addEventListener("storage", (e) => {
    if (e.key === "lv-theme" && e.newValue) {
      setTheme(e.newValue, false);
      if (window.__lvReseedBg) window.__lvReseedBg();
    }
  });
})();