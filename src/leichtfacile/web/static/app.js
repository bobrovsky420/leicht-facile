// Leicht·Facile: start-page form, job progress polling, provenance highlighting and
// review decisions. No dependencies; every page works without it, with less comfort.
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

  // -- start page: source tabs, example texts, endpoint status, relative times --------
  const tabs = $$(".tab");
  if (tabs.length) {
    const show = (name) => {
      tabs.forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === name)));
      $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
    };
    tabs.forEach((t) => t.addEventListener("click", () => show(t.dataset.tab)));
    // After a rejected submission, open the tab that holds the user's input.
    if ($("#url") && $("#url").value) show("url");
    else if ($("#file") && $("#file").files && $("#file").files.length) show("file");

    const examples = $("#example-texts");
    if (examples) {
      let texts = [];
      try {
        texts = JSON.parse(examples.textContent);
      } catch (e) {
        texts = [];
      }
      $$("[data-example]").forEach((button) => {
        button.addEventListener("click", () => {
          const example = texts.find((t) => t.id === button.dataset.example);
          if (!example) return;
          show("text");
          $("#text").value = example.text;
          $("#url").value = "";
          $("#title").value = "";
          $("#text").focus();
        });
      });
    }

    const status = $("#endpoint-status");
    if (status) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 8000);
      fetch(status.dataset.url, { signal: controller.signal })
        .then((res) => res.json())
        .then((data) => {
          const llm = data.llm || {};
          if (llm.reachable) {
            const key = llm.model_listed ? "endpoint.listed" : "endpoint.unlisted";
            status.textContent = t(key, { url: llm.base_url });
            status.className = "hint " + (llm.model_listed ? "ok" : "bad");
          } else {
            const error = llm.error || t("endpoint.no_answer");
            status.textContent = t("endpoint.unreachable", { url: llm.base_url || "", error });
            status.className = "hint bad";
          }
        })
        .catch(() => {
          status.textContent = t("endpoint.unknown");
        })
        .finally(() => clearTimeout(timer));
    }
  }

  const relative = new Intl.RelativeTimeFormat(lang, { numeric: "auto", style: "short" });
  $$("time[data-relative]").forEach((el) => {
    const then = new Date(el.getAttribute("datetime"));
    if (Number.isNaN(then.getTime())) return;
    const minutes = Math.round((Date.now() - then.getTime()) / 60000);
    let text;
    if (minutes < 1) text = relative.format(0, "minute");
    else if (minutes < 60) text = relative.format(-minutes, "minute");
    else if (minutes < 60 * 24) text = relative.format(-Math.round(minutes / 60), "hour");
    else text = then.toLocaleDateString(lang, { day: "2-digit", month: "2-digit", year: "numeric" });
    el.title = el.textContent;
    el.textContent = text;
  });

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
      } catch (e) {
        /* the next tick tries again */
      } finally {
        busy = false;
      }
    };
    setInterval(tick, 2000);
  }

  // -- review: provenance ------------------------------------------------------------
  const clearMarks = () => {
    $$(".seg.linked").forEach((el) => el.classList.remove("linked"));
    $$(".block.selected").forEach((el) => el.classList.remove("selected"));
    $$(".block.fact-hit").forEach((el) => el.classList.remove("fact-hit"));
    $$(".fact.hit").forEach((el) => el.classList.remove("hit"));
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

  const blocks = $$(".block");
  let currentBlock = null;
  const selectBlock = (block, scroll = false) => {
    clearMarks();
    currentBlock = block;
    block.classList.add("selected");
    showSegments((block.dataset.segments || "").split(" "));
    if (scroll) block.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };
  blocks.forEach((block) => {
    block.addEventListener("click", (event) => {
      if (event.target.closest(".decision, details")) return;
      selectBlock(block);
    });
    block.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.target === block) selectBlock(block);
    });
  });

  $$(".fact[data-fact]").forEach((fact) => {
    const show = () => {
      clearMarks();
      fact.classList.add("hit");
      const id = fact.dataset.fact;
      const hits = blocks.filter((b) => (b.dataset.facts || "").split(" ").includes(id));
      hits.forEach((b) => b.classList.add("fact-hit"));
      if (hits[0]) hits[0].scrollIntoView({ block: "center", behavior: "smooth" });
    };
    fact.addEventListener("click", show);
    fact.addEventListener("keydown", (e) => e.key === "Enter" && show());
  });

  $$(".linkable[data-segments]").forEach((el) => {
    const show = () => {
      clearMarks();
      showSegments((el.dataset.segments || "").split(" "));
    };
    el.addEventListener("click", show);
    el.addEventListener("keydown", (e) => e.key === "Enter" && show());
  });

  // -- review: decisions, filters, keyboard ---------------------------------------------
  const form = $("#review-form");
  if (form) {
    let dirty = false;
    const total = blocks.length;
    const decidedCount = $("#decided-count");
    const undecidedN = $("#undecided-n");
    const chosen = (block) => $$("input[type=radio]", block).find((r) => r.checked);

    const refresh = () => {
      let decided = 0;
      blocks.forEach((block) => {
        const has = Boolean(chosen(block));
        block.classList.toggle("decided", has);
        if (has) decided += 1;
      });
      if (decidedCount) decidedCount.textContent = t("decided", { decided, total });
      if (undecidedN) undecidedN.textContent = String(total - decided);
      applyFilter();
    };

    let filter = "all";
    const applyFilter = () => {
      blocks.forEach((block) => {
        let visible = true;
        if (filter === "issues") visible = block.classList.contains("has-issues");
        if (filter === "undecided") visible = !chosen(block);
        block.hidden = !visible;
      });
    };
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

    $$(".decision input[type=radio]").forEach((radio) => {
      radio.addEventListener("change", () => {
        const area = radio.closest(".decision").querySelector("textarea");
        area.hidden = radio.value !== "edited";
        if (!area.hidden) area.focus();
        dirty = true;
        refresh();
      });
    });
    $$(".decision textarea").forEach((area) => area.addEventListener("input", () => (dirty = true)));

    $("#approve-all").addEventListener("click", () => {
      blocks.forEach((block) => {
        const radios = $$("input[type=radio]", block);
        if (!radios.some((r) => r.checked)) {
          radios.find((r) => r.value === "approved").checked = true;
        }
      });
      dirty = true;
      refresh();
    });

    const decide = (block, value) => {
      const radio = $$("input[type=radio]", block).find((r) => r.value === value);
      if (!radio) return;
      radio.checked = true;
      radio.dispatchEvent(new Event("change", { bubbles: true }));
    };
    document.addEventListener("keydown", (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.target.matches("input, textarea, select")) return;
      const visible = blocks.filter((b) => !b.hidden);
      if (!visible.length) return;
      if (e.key === "j" || e.key === "k") {
        const index = currentBlock ? visible.indexOf(currentBlock) : -1;
        const next = e.key === "j" ? Math.min(index + 1, visible.length - 1) : Math.max(index - 1, 0);
        selectBlock(visible[next], true);
        visible[next].focus({ preventScroll: true });
        e.preventDefault();
      } else if (currentBlock && (e.key === "a" || e.key === "e" || e.key === "r")) {
        decide(currentBlock, { a: "approved", e: "edited", r: "rejected" }[e.key]);
        e.preventDefault();
      }
    });

    window.addEventListener("beforeunload", (e) => {
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = "";
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const decisions = [];
      blocks.forEach((block) => {
        const picked = chosen(block);
        if (!picked) return;
        const entry = { block_id: block.dataset.block, decision: picked.value };
        if (picked.value === "edited") entry.text = $("textarea", block).value;
        decisions.push(entry);
      });
      const body = {
        draft_version: Number(form.dataset.version),
        decisions,
        completed: form.elements.completed.checked,
      };
      const out = $("#save-status");
      out.textContent = t("saving");
      out.className = "";
      try {
        const res = await fetch(`/api/jobs/${form.dataset.job}/review`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (res.ok) {
          dirty = false;
          out.textContent = t(data.completed ? "saved_complete" : "saved", { n: data.saved });
          out.className = "ok";
          const chip = $(".review-head .status");
          if (chip) {
            const status = data.completed ? "done" : "needs_review";
            chip.textContent = t(`status.${status}`);
            chip.className = `chip status status-${status}`;
          }
        } else {
          out.textContent = t("not_saved", { detail: data.detail });
          out.className = "bad";
        }
      } catch (e) {
        out.textContent = t("no_answer");
        out.className = "bad";
      }
    });

    refresh();
  }
})();
