// Scripted screen capture of the real web UI for the product scenes. Run from video/.
// Drives Edge against the app on a scratch data folder; the job states come from
// scripts/stage_demo.py (a copy of the real example job). Writes public/capture/*.jpg
// and public/capture/manifest.json.
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import puppeteer from "puppeteer-core";

// EDGE overrides the browser, for example Remotion's headless Chrome while an Edge update
// is pending (msedge.exe then hands over to the new binary and puppeteer loses it)
const EDGE = process.env.EDGE || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const BASE = "http://127.0.0.1:8791";
const OUT = "public/capture";
const STAGE = "scripts/stage_demo.py";
const REPO = process.env.LF_REPO || ".."; // set it when building outside the repo
const LETTER = readFileSync(`${REPO}/track_2b/data/examples/sources/praemienverbilligung-brief.txt`, "utf8");
mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: true,
  userDataDir: "out/edge-profile",
  args: ["--hide-scrollbars", "--no-first-run", "--no-default-browser-check", "--lang=en-US"],
  defaultViewport: { width: 1440, height: 810, deviceScaleFactor: 2 },
});
const page = await browser.newPage();
await page.setExtraHTTPHeaders({ "Accept-Language": "en-US,en;q=0.9" });
// the endpoint indicator as the app shows it against CSCS (cached answer of /healthz)
await page.evaluateOnNewDocument(() => {
  try {
    const data = {
      status: "ok",
      llm: {
        base_url: "https://api.inference.cscs.ch",
        model: "swiss-ai/Apertus-v1.5-8B",
        judge_model: "swiss-ai/Apertus-v1.5-70B",
        reachable: true,
        model_listed: true,
        judge_model_listed: true,
      },
    };
    sessionStorage.setItem("lf-healthz", JSON.stringify({ at: Date.now(), data }));
  } catch (e) {
    /* about:blank */
  }
});

const manifest = {};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function settle(ms = 400) {
  await page.evaluate(() => document.fonts.ready);
  await sleep(ms);
}

async function rects(spec) {
  const out = {};
  for (const [key, sel] of Object.entries(spec)) {
    out[key] = await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)];
    }, sel);
  }
  return out;
}

async function shot(name, spec = {}) {
  const file = `${name}.jpg`;
  await page.screenshot({ path: `${OUT}/${file}`, type: "jpeg", quality: 93 });
  manifest[name] = { file, rects: await rects(spec) };
  const missing = Object.entries(manifest[name].rects).filter(([, v]) => !v).map(([k]) => k);
  console.log(name, missing.length ? `missing: ${missing.join(", ")}` : "");
}

function stage(state) {
  execFileSync("python", [STAGE, state], { stdio: "inherit" });
}

// -- drafts list and New draft ------------------------------------------------------------
await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
await settle();
await shot("list", { newDraft: 'a[href="/new"].btn-primary', table: "table" });

await page.goto(`${BASE}/new`, { waitUntil: "networkidle0" });
await settle();
const newRects = {
  text: "#text",
  create: "#new-job button[type=submit]",
  level: "input[name=level][value=A2]",
  pipeline: "input[name=condition][value=P2]",
  settings: "#set-h",
  count: "#char-count",
};
await shot("new-empty", newRects);
await page.evaluate((text) => {
  const ta = document.querySelector("#text");
  ta.value = text;
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  ta.scrollTop = 0;
}, LETTER);
await settle(200);
await shot("new-filled", newRects);
await page.hover("#new-job button[type=submit]");
await settle(200);
await shot("new-hover", newRects);

// -- the job running, stage by stage ------------------------------------------------------
const jobRects = {
  pipeline: ".pipeline",
  step1: ".steps .step:nth-child(1)",
  step2: ".steps .step:nth-child(2)",
  step3: ".steps .step:nth-child(3)",
  step4: ".steps .step:nth-child(4)",
  step5: ".steps .step:nth-child(5)",
  factsheet: ".results-cards .card:nth-child(1)",
  factlines: ".factlines",
  draft: ".results-cards .card:nth-child(2)",
  runline: ".run-line",
  coreList: "dl.core-list",
  byWhen: "dl.core-list > div:nth-child(3)",
  f01: ".factlines li:nth-child(1)",
};
for (const state of ["understand", "write", "check", "judge", "repair"]) {
  stage(state);
  await page.goto(`${BASE}/jobs/demo-run`, { waitUntil: "networkidle0" });
  await settle();
  await shot(`job-${state}`, jobRects);
}

// -- review -------------------------------------------------------------------------------
stage("review");
const revRects = {
  panes: "#review-grid",
  versions: ".versions",
  pillFirst: ".versions a.version:first-of-type",
  pillLast: ".versions a.version:last-of-type",
  source: ".pane.source",
  draft: ".pane.draft",
  checks: ".pane.checks",
  strip: ".strip",
  b002: "#blk-b002",
  b012: "#blk-b012",
  linked: ".seg-row.linked",
  omitted: ".seg-row.omitted",
  findings: "#panel-findings",
  facts: "#panel-facts",
  foot: ".draft-foot",
  decided: "#decided-count",
  save: ".pagehead-actions .btn-primary",
  factF01: '[data-fact="f01"]',
  factF07: '[data-fact="f07"]',
  s0007: "#seg-s0007",
};
await page.goto(`${BASE}/jobs/demo-run?version=1`, { waitUntil: "networkidle0" });
await settle();
await shot("rev-v1", revRects);
await page.goto(`${BASE}/jobs/demo-run`, { waitUntil: "networkidle0" });
await settle();
await shot("rev-final", revRects);

await page.click("#blk-b002 .block-text");
await settle(300);
await shot("rev-select", revRects);

// the first left-out sentence, scrolled into view in the source pane
await page.evaluate(() => {
  const row = document.querySelector(".seg-row.omitted");
  const pane = document.querySelector(".pane.source .pane-body");
  if (row && pane) pane.scrollTop = row.offsetTop - pane.offsetTop - 160;
});
await settle(200);
await shot("rev-omitted", revRects);

await page.click("#tab-findings");
await settle(300);
await shot("rev-findings", revRects);
await page.click("#tab-facts");
await settle(200);

// approve with the keyboard: A approves and moves on to the next undecided block
await page.click("#blk-b001 .block-text");
await settle(200);
await shot("rev-approve-0", revRects);
for (let i = 1; i <= 5; i++) {
  await page.keyboard.press("a");
  await settle(180);
  await shot(`rev-approve-${i}`, revRects);
}

// reader view with the export panel
await page.click('[data-view="reader"]');
await sleep(1200);
await settle(300);
await shot("rev-reader", {
  side: ".reader-side",
  paper: ".reader-page .paper",
  download: ".reader-side .btn-primary",
  before: ".reader-side h2",
});

writeFileSync(`${OUT}/manifest.json`, JSON.stringify({ css: [1440, 810], scale: 2, shots: manifest }, null, 1));
await browser.close();
console.log("done", Object.keys(manifest).length, "shots");
