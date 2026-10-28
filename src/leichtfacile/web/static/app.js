// Leicht·Facile: endpoint status, drafts list, new draft form, job progress polling,
// review (provenance, decisions, keys, checks tabs, reader view with its export panel).
// No dependencies; every page reads without it, with less comfort (docs/ui-design.md §6).
// Texts come from the interface catalog the page embeds (#ui-text, see web/i18n.py).
"use strict";

(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const lang = document.documentElement.lang || "en";
  let texts = {};
  try {
    texts = JSON.parse($("#ui-text").textContent);
  } catch (e) {
    texts = {};
  }
  const plural = new Intl.PluralRules(lang);
  // t("saved", { n: 3 }) picks "saved.one" or "saved.other" and fills {n}.
  const t = (key, params = {}) => {
    if ("n" in params) key += plural.select(params.n) === "one" ? ".one" : ".other";
    const text = texts[key] ?? key;
    return text.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));
  };
  // Thousands as the interface language writes them: 1,960 or 1'960 (views.format_number).
  const number = (n) => {
    const text = Math.round(n).toLocaleString("en-US");
    return lang === "de" || lang === "it" ? text.replace(/,/g, "'") : text;
  };
  const clock = (date) => date.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
  const typing = (el) =>
    Boolean(el && el.matches && el.matches("input:not([type=radio]):not([type=checkbox]), textarea, select"));
  const onActivate = (el, handler) => {
    el.addEventListener("click", handler);
    el.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handler(event);
      }
    });
  };

  // -- everything destructive asks first ------------------------------------------------
  $$("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // -- menus close on Escape and on a click outside -------------------------------------
  document.addEventListener("click", (event) => {
    $$("details.menu[open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    $$("details.menu[open]").forEach((menu) => {
      menu.open = false;
      const summary = $("summary", menu);
      if (summary) summary.focus();
    });
  });

  // -- endpoint status in the app bar and on the New draft page, cached for 5 minutes ---
  const endpoints = $$("[data-endpoint]");
  if (endpoints.length) {
    const KEY = "lf-readyz";
    const show = (data) => {
      const llm = (data && data.llm) || {};
      let state = "unknown";
      let text = t("endpoint.unknown");
      if (data && llm.ready === false) {
        state = "bad";
        text = t("endpoint.not_ready");
      } else if (data && llm.reachable) {
        state = llm.model_listed ? "ok" : "warn";
        text = t(llm.model_listed ? "endpoint.listed" : "endpoint.unlisted", { url: llm.base_url });
      } else if (data) {
        state = "bad";
        const error = llm.error || t("endpoint.no_answer");
        text = t("endpoint.unreachable", { url: llm.base_url || "", error });
      }
      endpoints.forEach((el) => {
        el.dataset.state = state;
        el.title = text;
        const out = $("[data-endpoint-text]", el);
        if (out) out.textContent = text;
      });
    };
    let cached = null;
    try {
      const saved = JSON.parse(sessionStorage.getItem(KEY) || "null");
      if (saved && Date.now() - saved.at < 5 * 60 * 1000) cached = saved.data;
    } catch (e) {
      cached = null;
    }
    if (cached) {
      show(cached);
    } else {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 8000);
      fetch(endpoints[0].dataset.url || "/readyz", { signal: controller.signal })
        .then((res) => res.json())
        .then((data) => {
          show(data);
          try {
            sessionStorage.setItem(KEY, JSON.stringify({ at: Date.now(), data }));
          } catch (e) {
            /* not cached: the next page asks again */
          }
        })
        .catch(() => show(null))
        .finally(() => clearTimeout(timer));
    }
  }

  // -- local times: the drafts list's created column, the review's save time ----------
  const dayKey = (d) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
  const today = dayKey(new Date());
  const yesterday = dayKey(new Date(Date.now() - 864e5));
  $$("time[data-local]").forEach((el) => {
    const when = new Date(el.getAttribute("datetime"));
    if (Number.isNaN(when.getTime())) return;
    el.title = when.toLocaleString(lang);
    const day = $(".day", el);
    const tm = $(".tm", el);
    if (day) {
      const key = dayKey(when);
      day.textContent =
        key === today
          ? t("today")
          : key === yesterday
            ? t("yesterday")
            : when.toLocaleDateString("de-CH", { day: "2-digit", month: "2-digit", year: "numeric" });
    }
    if (tm) tm.textContent = clock(when);
  });
  $$("time[data-saved]").forEach((el) => {
    const when = new Date(el.getAttribute("datetime"));
    if (!Number.isNaN(when.getTime())) el.textContent = t("saved_at", { time: clock(when) });
  });

  // -- drafts list: hide the intro strip, filter by language ---------------------------
  [["#intro-close", "intro-hidden", "lf-intro-hidden"]].forEach(([button, hidden, key]) => {
    const close = $(button);
    if (!close) return;
    close.addEventListener("click", () => {
      document.documentElement.classList.add(hidden);
      try {
        localStorage.setItem(key, "1");
      } catch (e) {
        /* hidden until the page reloads */
      }
    });
  });
  $$("select[data-autosubmit]").forEach((select) => {
    select.addEventListener("change", () => select.form.submit());
  });

  // -- new draft: source tabs, examples, character count, file choice and drop ---------
  const srcTabs = $$(".src-tabs [role=tab]");
  if (srcTabs.length) {
    const show = (name, focus = false) => {
      srcTabs.forEach((tab) => {
        const on = tab.dataset.tab === name;
        tab.setAttribute("aria-selected", String(on));
        tab.tabIndex = on ? 0 : -1;
        if (on && focus) tab.focus();
      });
      $$(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === name));
    };
    srcTabs.forEach((tab, i) => {
      tab.addEventListener("click", () => show(tab.dataset.tab));
      tab.addEventListener("keydown", (event) => {
        const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
        if (!step) return;
        event.preventDefault();
        show(srcTabs[(i + step + srcTabs.length) % srcTabs.length].dataset.tab, true);
      });
    });
    // After a rejected submission, open the tab that holds the user's input.
    if ($("#url") && $("#url").value) show("url");

    const area = $("#text");
    const count = $("#char-count");
    const note = $("#lang-note");
    const max = Number(area.dataset.max) || 0;
    const recount = () => {
      if (count) count.textContent = t("chars", { count: number(area.value.length), max: number(max) });
    };
    const noteAuto = () => {
      if (note) note.textContent = t("lang_auto");
    };
    area.addEventListener("input", () => {
      recount();
      noteAuto();
    });

    // Decision mode: the document type reveals the addressee and the notice; the
    // notice's placeholder follows the document language (the server fills the
    // default in when the field stays empty).
    const mode = $("#mode");
    const decisionFields = $("#decision-fields");
    const langSelect = $("#lang");
    const notice = $("#notice");
    const reveal = () => {
      if (mode && decisionFields) decisionFields.hidden = mode.value !== "decision";
    };
    const noticePlaceholder = () => {
      if (!notice) return;
      const code = langSelect && langSelect.value !== "auto" ? langSelect.value : "de";
      const key = `default${code.charAt(0).toUpperCase()}${code.slice(1)}`;
      notice.placeholder = notice.dataset[key] || notice.dataset.defaultDe || "";
    };
    if (mode) mode.addEventListener("change", reveal);
    if (langSelect) langSelect.addEventListener("change", noticePlaceholder);
    reveal();
    noticePlaceholder();

    // The preset picked for this draft: the model placeholders follow its models, and
    // the note says when it takes public documents only.
    const endpointSelect = $("#endpoint");
    const modelPlaceholders = () => {
      const option = endpointSelect && endpointSelect.options[endpointSelect.selectedIndex];
      if (!option) return;
      const note = $("#endpoint-documents");
      if (note) note.hidden = option.dataset.documents !== "public";
      [["writer_model", "writer"], ["understand_model", "understand"], ["judge_model", "judge"]].forEach(
        ([id, key]) => {
          const input = $(`#${id}`);
          if (input) input.placeholder = option.dataset[key] || "";
        },
      );
    };
    if (endpointSelect) endpointSelect.addEventListener("change", modelPlaceholders);
    modelPlaceholders();

    let examples = [];
    try {
      examples = JSON.parse($("#example-texts").textContent);
    } catch (e) {
      examples = [];
    }
    $$("[data-example]").forEach((button) => {
      button.addEventListener("click", () => {
        const example = examples.find((x) => x.id === button.dataset.example);
        if (!example) return;
        show("text");
        area.value = example.text;
        $("#url").value = "";
        $("#title").value = "";
        if (mode) {
          mode.value = example.mode || "standard";
          reveal();
        }
        if ($("#addressee")) $("#addressee").value = example.addressee || "";
        if (notice) notice.value = example.notice || "";
        recount();
        if (note) note.textContent = example.lang_name ? t("lang_detected", { lang: example.lang_name }) : t("lang_auto");
        area.focus();
      });
    });
    const clear = $("#clear-text");
    if (clear) {
      clear.addEventListener("click", () => {
        area.value = "";
        recount();
        noteAuto();
        area.focus();
      });
    }

    const file = $("#file");
    const chosen = $("#file-chosen");
    const zone = $("#dropzone");
    const describe = () => {
      const picked = file.files && file.files[0];
      chosen.textContent = picked ? `${picked.name}, ${number(Math.max(1, picked.size / 1024))} KB` : "";
    };
    file.addEventListener("change", describe);
    ["dragenter", "dragover"].forEach((type) => {
      zone.addEventListener(type, (event) => {
        event.preventDefault();
        zone.classList.add("over");
      });
    });
    ["dragleave", "drop"].forEach((type) => zone.addEventListener(type, () => zone.classList.remove("over")));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      if (!event.dataTransfer || !event.dataTransfer.files.length) return;
      file.files = event.dataTransfer.files;
      describe();
    });
  }

  // -- job progress: poll the fragment until the job leaves the queue -------------------
  const progress = $("#progress");
  if (progress && ["queued", "running"].includes(progress.dataset.status)) {
    const id = progress.dataset.job;
    let busy = false;
    const tick = async () => {
      if (busy) return;
      busy = true;
      try {
        const res = await fetch(`/jobs/${id}/progress`, { cache: "no-store" });
        if (!res.ok) return;
        const status = res.headers.get("X-Job-Status");
        if (status && !["queued", "running"].includes(status)) {
          window.location.reload();
          return;
        }
        progress.innerHTML = await res.text();
        const grid = $(".jobgrid", progress);
        const line = $("#run-numbers");
        if (grid && line && grid.dataset.run) line.textContent = grid.dataset.run;
        const badge = $("#job-status");
        if (badge && status) {
          badge.className = `badge status-${status}`;
          badge.textContent = t(`status.${status}`);
        }
      } catch (e) {
        /* the next tick tries again */
      } finally {
        busy = false;
      }
    };
    // Every 2 s for the first two minutes, then every 5 s: a long job (a repair loop
    // on a slow endpoint) must not keep the server busy with its own page.
    let ticks = 0;
    const schedule = () => {
      ticks += 1;
      setTimeout(async () => {
        await tick();
        schedule();
      }, ticks <= 60 ? 2000 : 5000);
    };
    schedule();
  }

  // -- review ---------------------------------------------------------------------------
  const form = $("#review-form");
  if (!form) return;

  const blocks = $$(".block", form);
  const draftPane = $(".pane.draft");
  const total = blocks.length;
  let current = null;
  let dirty = false;
  let view = "review";
  let filter = "all";

  const radios = (block) => $$("input[type=radio]", block);
  const chosen = (block) => radios(block).find((r) => r.checked);
  const areaOf = (block) => $("textarea", block);

  // provenance: the selected block's source sentences, a fact's blocks
  const clearMarks = () => {
    $$(".seg-row.linked").forEach((el) => el.classList.remove("linked"));
    $$(".block.fact-hit, .block.fact-near").forEach((el) => el.classList.remove("fact-hit", "fact-near"));
    $$(".fact.hit").forEach((el) => {
      el.classList.remove("hit");
      el.setAttribute("aria-pressed", "false");
    });
    $$(".linked-src").forEach((el) => el.classList.remove("linked-src"));
  };
  const showSegments = (ids) => {
    let first = null;
    ids.filter(Boolean).forEach((id) => {
      const seg = document.getElementById(`seg-${id}`);
      if (seg) {
        seg.classList.add("linked");
        first = first || seg;
      }
    });
    if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  const applyFilter = () => {
    let shown = 0;
    blocks.forEach((block) => {
      let visible = true;
      if (filter === "issues") visible = block.classList.contains("has-issues");
      if (filter === "undecided") visible = !chosen(block) || block === current;
      block.hidden = !visible;
      if (visible) shown += 1;
    });
    $("#no-match").hidden = shown > 0;
  };

  const select = (block, { scroll = false, focus = false } = {}) => {
    clearMarks();
    blocks.forEach((b) => b.classList.remove("selected", "is-open"));
    current = block;
    applyFilter();
    if (!block) return;
    block.classList.add("selected", "is-open");
    showSegments((block.dataset.segments || "").split(" "));
    if (scroll) block.scrollIntoView({ block: "nearest", behavior: "smooth" });
    if (focus) block.focus({ preventScroll: true });
  };

  // decisions: the radios are the state; classes and texts follow them
  const sync = (block) => {
    const picked = chosen(block);
    const value = picked ? picked.value : "";
    block.classList.toggle("decided", Boolean(picked));
    ["approved", "edited", "rejected"].forEach((v) => block.classList.toggle(v, v === value));
    radios(block).forEach((r) => {
      r.dataset.was = r.checked ? "1" : "0";
    });
    const edited = $(".edited-text", block);
    if (edited) edited.textContent = areaOf(block).value;
  };
  const refresh = () => {
    let decided = 0;
    blocks.forEach((block) => {
      sync(block);
      if (chosen(block)) decided += 1;
    });
    $("#decided-count").textContent = t("decided", { decided, total });
    $("#decided-meter").style.width = `${total ? Math.round((100 * decided) / total) : 0}%`;
    $("#undecided-n").textContent = String(total - decided);
    const check = $("#check-decided");
    if (check) {
      check.classList.toggle("done", decided === total);
      $("#check-decided-text").textContent = t("reader_decided", { decided, total });
    }
    applyFilter();
  };
  const exportNote = $("#export-note");
  const updateExportNote = () => {
    if (!exportNote) return;
    exportNote.classList.remove("bad");
    exportNote.textContent = dirty ? t("reader_unsaved") : t("saved_only");
  };
  const markDirty = () => {
    dirty = true;
    const out = $("#save-status");
    out.className = "save-state dirty";
    out.textContent = t("unsaved");
    out.removeAttribute("title");
    updateExportNote();
  };
  const undecidedAfter = (block) => {
    const start = block ? blocks.indexOf(block) : -1;
    const order = blocks.slice(start + 1).concat(blocks.slice(0, start + 1));
    return order.find((b) => !chosen(b) && b !== block) || null;
  };
  const afterDecision = (block, advance) => {
    markDirty();
    refresh();
    const picked = chosen(block);
    if (picked && picked.value === "edited") {
      areaOf(block).focus();
      return;
    }
    const next = picked && advance ? undecidedAfter(block) : null;
    if (next) select(next, { scroll: true, focus: true });
    else block.focus({ preventScroll: true });
  };
  // The keys: choosing the pressed decision again clears it.
  const decide = (block, value) => {
    const radio = radios(block).find((r) => r.value === value);
    if (!radio) return;
    radio.checked = !radio.checked;
    afterDecision(block, true);
  };

  blocks.forEach((block) => {
    block.addEventListener("click", (event) => {
      if (event.target.closest(".block-details")) return;
      if (current !== block) select(block);
    });
    block.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.target === block) select(block);
    });
    radios(block).forEach((radio) => {
      // A click on the pressed decision clears it; a mouse click moves on (keyboard
      // clicks, detail 0, stay: the keys A, E and R move on by themselves).
      radio.addEventListener("click", (event) => {
        if (radio.dataset.was === "1") radio.checked = false;
        afterDecision(block, event.detail > 0);
      });
    });
    areaOf(block).addEventListener("input", () => {
      markDirty();
      sync(block);
    });
    $$("[data-apply]", block).forEach((button) => {
      button.addEventListener("click", () => {
        const area = areaOf(block);
        const editing = chosen(block) && chosen(block).value === "edited";
        const base = editing ? area.value : $(".orig-text", block).textContent;
        area.value = base.split(button.dataset.evidence).join(button.dataset.suggestion);
        radios(block).find((r) => r.value === "edited").checked = true;
        markDirty();
        refresh();
        area.focus();
      });
    });
    const next = $(".next-undecided", block);
    if (next) {
      next.addEventListener("click", () => {
        const target = undecidedAfter(block);
        if (target) select(target, { scroll: true, focus: true });
      });
    }
  });

  // Single-key shortcuts act only while the focus is in the draft pane (WCAG 2.1.4).
  draftPane.addEventListener("keydown", (event) => {
    if (view !== "review" || event.altKey || event.ctrlKey || event.metaKey) return;
    if (typing(event.target)) return;
    const visible = blocks.filter((b) => !b.hidden);
    if (!visible.length) return;
    const key = event.key;
    if (key === "j" || key === "k" || key === "ArrowDown" || key === "ArrowUp") {
      if (key.startsWith("Arrow") && event.target.matches("input[type=radio]")) return;
      const index = current ? visible.indexOf(current) : -1;
      const down = key === "j" || key === "ArrowDown";
      const target = down ? visible[Math.min(index + 1, visible.length - 1)] : visible[Math.max(index - 1, 0)];
      select(target, { scroll: true, focus: true });
      event.preventDefault();
    } else if (current && (key === "a" || key === "e" || key === "r")) {
      decide(current, { a: "approved", e: "edited", r: "rejected" }[key]);
      event.preventDefault();
    } else if (key === "n") {
      const target = undecidedAfter(current);
      if (target) select(target, { scroll: true, focus: true });
      event.preventDefault();
    }
  });
  // Ctrl+S (Cmd+S) saves from anywhere on the page.
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (form.requestSubmit) form.requestSubmit();
    }
  });

  $$(".filter").forEach((button) => {
    button.addEventListener("click", () => {
      filter = button.dataset.filter;
      $$(".filter").forEach((b) => {
        const on = b === button;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", String(on));
      });
      applyFilter();
    });
  });

  $("#approve-all").addEventListener("click", () => {
    blocks.forEach((block) => {
      if (!chosen(block)) radios(block).find((r) => r.value === "approved").checked = true;
    });
    markDirty();
    refresh();
  });

  const completed = form.elements.completed;
  completed.addEventListener("change", () => {
    markDirty();
    const item = $("#check-complete");
    if (item) {
      item.classList.toggle("done", completed.checked);
      $("#check-complete-text").textContent = t(completed.checked ? "reader_complete" : "reader_not_complete");
    }
  });

  window.addEventListener("beforeunload", (event) => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  // The decisions on screen, in the body the review API takes.
  const currentReview = () => {
    const decisions = [];
    blocks.forEach((block) => {
      const picked = chosen(block);
      if (!picked) return;
      const entry = { block_id: block.dataset.block, decision: picked.value };
      if (picked.value === "edited") entry.text = areaOf(block).value;
      decisions.push(entry);
    });
    // saved_at: the stored review this page was loaded with (null: none). The server
    // refuses the save with 409 when someone else saved in the meantime.
    return {
      draft_version: Number(form.dataset.version),
      decisions,
      completed: completed.checked,
      saved_at: form.dataset.savedAt || null,
    };
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const out = $("#save-status");
    out.className = "save-state";
    out.textContent = t("saving");
    try {
      const res = await fetch(`/api/jobs/${form.dataset.job}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentReview()),
      });
      const data = await res.json();
      if (res.ok) {
        dirty = false;
        if (data.saved_at) form.dataset.savedAt = data.saved_at;
        out.className = "save-state saved";
        out.textContent = t("saved_at", { time: clock(new Date()) });
        out.title = t(data.completed ? "saved_complete" : "saved", { n: data.saved });
        const badge = $("#job-status");
        if (badge) {
          const status = data.completed ? "done" : "needs_review";
          badge.textContent = t(`status.${status}`);
          badge.className = `badge status-${status}`;
        }
        updateExportNote();
      } else {
        out.className = "save-state bad";
        out.textContent = res.status === 409 ? t("conflict") : t("not_saved", { detail: data.detail });
      }
    } catch (e) {
      out.className = "save-state bad";
      out.textContent = t("no_answer");
    }
  });

  // checks pane: tabs (WAI-ARIA tabs pattern), facts and findings that point elsewhere
  const tabs = $$(".pane.checks [role=tab]");
  const activate = (tab, focus = false) => {
    tabs.forEach((other) => {
      const on = other === tab;
      other.setAttribute("aria-selected", String(on));
      other.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(other.getAttribute("aria-controls"));
      if (panel) panel.classList.toggle("active", on);
    });
    if (focus) tab.focus();
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => activate(tab));
    tab.addEventListener("keydown", (event) => {
      const keys = { ArrowRight: (i + 1) % tabs.length, ArrowLeft: (i - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1 };
      if (!(event.key in keys)) return;
      event.preventDefault();
      activate(tabs[keys[event.key]], true);
    });
  });

  const showFact = (id, source) => {
    clearMarks();
    blocks.forEach((b) => b.classList.remove("selected", "is-open"));
    current = null;
    applyFilter();
    if (source) {
      source.classList.add("hit");
      source.setAttribute("aria-pressed", "true");
    }
    // the source sentences of the fact, and the blocks that carry it; a fact no block
    // carries marks the blocks built from its source sentences, where it belongs
    const segs = ((source && source.dataset.factSegments) || "").split(" ").filter(Boolean);
    showSegments(segs);
    let hits = blocks.filter((b) => (b.dataset.facts || "").split(" ").includes(id));
    let mark = "fact-hit";
    if (!hits.length) {
      hits = blocks.filter((b) => (b.dataset.segments || "").split(" ").some((s) => segs.includes(s)));
      mark = "fact-near";
    }
    hits.forEach((b) => b.classList.add(mark));
    if (hits[0]) hits[0].scrollIntoView({ block: "center", behavior: "smooth" });
  };
  $$(".fact[data-fact]").forEach((fact) => {
    fact.addEventListener("click", () => {
      if (fact.classList.contains("hit")) clearMarks();
      else showFact(fact.dataset.fact, fact);
    });
  });
  $$("[data-fact-ref]").forEach((el) => {
    onActivate(el, () => showFact(el.dataset.factRef, $(`.fact[data-fact="${el.dataset.factRef}"]`)));
  });

  // a missing fact: sentences from its source paragraph, one model call
  // (POST /api/jobs/{id}/facts/{fact}/recover); the reviewer adds them to a block as an edit
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const docLang = form.getAttribute("lang") || "";
  const addToBlock = (blockId, texts) => {
    const block = document.getElementById(`blk-${blockId}`);
    if (!block) return false;
    const area = areaOf(block);
    const editing = chosen(block) && chosen(block).value === "edited";
    const base = (editing ? area.value : $(".orig-text", block).textContent).trimEnd();
    area.value = [base, ...texts].join(" ");
    radios(block).find((r) => r.value === "edited").checked = true;
    markDirty();
    refresh();
    select(block, { scroll: true });
    area.focus({ preventScroll: true });
    return true;
  };
  $$("[data-recover]").forEach((box) => {
    const ask = $("[data-recover-ask]", box);
    const out = $(".recover-out", box);
    ask.addEventListener("click", async () => {
      ask.disabled = true;
      out.replaceChildren(el("p", "hint", t("recover_asking")));
      let data = null;
      try {
        const res = await fetch(`/api/jobs/${form.dataset.job}/facts/${box.dataset.recover}/recover?version=${form.dataset.version}`, { method: "POST" });
        data = await res.json();
        if (!res.ok) throw new Error(data.detail || res.status);
      } catch (e) {
        out.replaceChildren(el("p", "recover-check bad", t("recover_failed", { detail: String(e.message || e) })));
        ask.disabled = false;
        return;
      }
      ask.disabled = false;
      ask.lastChild.textContent = t("recover_again");
      if (data.rejected) {
        const reason = el("p", "recover-check bad", t(`recover_rejected.${data.rejected}`, { values: (data.foreign || []).join(", ") }));
        out.replaceChildren(reason);
        return;
      }
      const card = el("div", "recover-box");
      card.append(el("p", "label", t("recover_title")));
      data.texts.forEach((text) => {
        const p = el("p", "recover-text", text);
        p.lang = docLang;
        card.append(p);
      });
      data.source.forEach((seg) => {
        const p = el("p", "recover-src");
        const text = el("span", "", seg.text);
        text.lang = docLang;
        p.append(el("span", "ref", seg.id), text);
        card.append(p);
      });
      const check = data.resolved === true ? ["ok", "recover_resolved"] : data.resolved === false ? ["bad", "recover_unresolved"] : ["", "recover_no_value"];
      card.append(el("p", `recover-check ${check[0]}`, t(check[1])));
      if (data.findings.length) {
        const list = el("ul");
        data.findings.forEach((f) => {
          const li = el("li", `sev-${f.severity}`);
          li.append(el("span", "rid", f.rule_id), el("span", "", f.message));
          list.append(li);
        });
        card.append(list);
      }
      const actions = el("div", "recover-actions");
      const add = el("button", "btn btn-sm btn-primary", t("recover_add", { block: data.block_id }));
      add.type = "button";
      add.addEventListener("click", () => {
        if (addToBlock(data.block_id, data.texts)) {
          actions.replaceChildren(el("span", "recover-check ok", t("recover_added", { block: data.block_id })));
        }
      });
      actions.append(add);
      card.append(actions);
      out.replaceChildren(card);
    });
  });
  $$(".linkable[data-segments]").forEach((el) => {
    onActivate(el, () => {
      clearMarks();
      el.classList.add("linked-src");
      showSegments((el.dataset.segments || "").split(" "));
    });
  });

  // reader view: the export of the decisions on screen in place of the panes
  const grid = $("#review-grid");
  const reader = $("#reader-pane");
  const frame = $("#reader-frame");
  const fit = () => {
    const doc = frame.contentDocument;
    if (doc && doc.documentElement) frame.style.height = `${doc.documentElement.scrollHeight}px`;
  };
  frame.addEventListener("load", fit);
  window.addEventListener("resize", () => view === "reader" && fit());

  const showView = async (name) => {
    view = name;
    $$(".view-opt").forEach((a) => {
      if (a.dataset.view === name) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
    grid.hidden = name !== "review";
    reader.hidden = name !== "reader";
    history.replaceState(null, "", name === "reader" ? "#reader" : location.pathname + location.search);
    if (name !== "reader") return;
    updateExportNote();
    try {
      const res = await fetch(`/jobs/${form.dataset.job}/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentReview()),
      });
      if (!res.ok) throw new Error(String(res.status));
      frame.srcdoc = await res.text();
    } catch (e) {
      frame.srcdoc = "";
      if (exportNote) {
        exportNote.textContent = t("reader_failed");
        exportNote.classList.add("bad");
      }
    }
  };
  $$(".view-opt").forEach((a) =>
    a.addEventListener("click", (event) => {
      event.preventDefault();
      if (a.dataset.view !== view) showView(a.dataset.view);
    })
  );

  // export panel: the chosen format builds the download link
  const download = $("#export-download");
  $$("input[name=export-format]").forEach((radio) => {
    radio.addEventListener("change", () => {
      const version = radio.value === "json" ? "" : `&version=${download.dataset.version}`;
      download.href = `/api/jobs/${download.dataset.job}/export?format=${radio.value}${version}`;
      $("#export-label").textContent = t("download", { ext: radio.dataset.ext });
    });
  });

  // print what the reader view shows (A4, the export's print styles); "Save as PDF"
  // as the printer gives the PDF
  const printButton = $("#reader-print");
  if (printButton) printButton.addEventListener("click", () => frame.contentWindow && frame.contentWindow.print());

  refresh();
  if (location.hash === "#reader") showView("reader");
})();
