// Leicht·Facile: provenance highlighting, review decisions, job polling. No dependencies.
"use strict";

(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // -- job progress: poll until the job leaves the queue -------------------------------
  const status = $("#job-status");
  if (status && ["queued", "running"].includes(status.dataset.status)) {
    const id = status.dataset.job;
    const labels = {
      understand: "Apertus reads the document and writes the fact sheet",
      write: "Apertus writes the easy-language draft",
      check: "Code checks the rules and the facts",
      judge: "A second Apertus model checks meaning and facts",
      baseline: "Apertus rewrites the text with one prompt (baseline)",
    };
    const tick = async () => {
      try {
        const res = await fetch(`/api/jobs/${id}`);
        if (!res.ok) return;
        const job = await res.json();
        if (!["queued", "running"].includes(job.status)) {
          window.location.reload();
          return;
        }
        const stage = (job.stage || "").split(" ")[0];
        const text = stage.startsWith("repair")
          ? `Apertus repairs the flagged sentences (${job.stage})`
          : labels[stage] || job.stage || "Waiting for the worker";
        $("#stage-text").textContent = text;
      } catch (e) {
        /* the next tick tries again */
      }
    };
    setInterval(tick, 2000);
  }

  // -- review: provenance ------------------------------------------------------------
  const clearMarks = () => {
    $$(".seg.linked").forEach((el) => el.classList.remove("linked"));
    $$(".block.selected").forEach((el) => el.classList.remove("selected"));
    $$(".block.fact-hit").forEach((el) => el.classList.remove("fact-hit"));
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

  $$(".block").forEach((block) => {
    const select = (event) => {
      if (event.target.closest(".decision, details")) return;
      clearMarks();
      block.classList.add("selected");
      showSegments((block.dataset.segments || "").split(" "));
    };
    block.addEventListener("click", select);
    block.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.target === block) select(e);
    });
  });

  $$(".fact").forEach((fact) => {
    const show = () => {
      clearMarks();
      const id = fact.dataset.fact;
      const hits = $$(".block").filter((b) => (b.dataset.facts || "").split(" ").includes(id));
      hits.forEach((b) => b.classList.add("fact-hit"));
      if (hits[0]) hits[0].scrollIntoView({ block: "center", behavior: "smooth" });
    };
    fact.addEventListener("click", show);
    fact.addEventListener("keydown", (e) => e.key === "Enter" && show());
  });

  $$(".omissions li").forEach((li) => {
    li.addEventListener("click", () => {
      clearMarks();
      showSegments((li.dataset.segments || "").split(" "));
    });
  });

  // -- review: decisions -------------------------------------------------------------
  $$(".decision input[type=radio]").forEach((radio) => {
    radio.addEventListener("change", () => {
      const area = radio.closest(".decision").querySelector("textarea");
      area.hidden = radio.value !== "edited";
      if (!area.hidden) area.focus();
    });
  });

  const form = $("#review-form");
  if (form) {
    $("#approve-all").addEventListener("click", () => {
      $$(".block").forEach((block) => {
        const radios = $$("input[type=radio]", block);
        if (!radios.some((r) => r.checked)) radios.find((r) => r.value === "approved").checked = true;
      });
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const decisions = [];
      $$(".block").forEach((block) => {
        const id = block.dataset.block;
        const chosen = $$("input[type=radio]", block).find((r) => r.checked);
        if (!chosen) return;
        const entry = { block_id: id, decision: chosen.value };
        if (chosen.value === "edited") entry.text = $("textarea", block).value;
        decisions.push(entry);
      });
      const body = {
        draft_version: Number(form.dataset.version),
        decisions,
        completed: form.elements.completed.checked,
      };
      const out = $("#save-status");
      out.textContent = "Saving...";
      try {
        const res = await fetch(`/api/jobs/${form.dataset.job}/review`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        out.textContent = res.ok
          ? `Saved ${data.saved} decision${data.saved === 1 ? "" : "s"}${data.completed ? ", review complete" : ""}.`
          : `Not saved: ${data.detail}`;
      } catch (e) {
        out.textContent = "Not saved: the server did not answer.";
      }
    });
  }
})();
