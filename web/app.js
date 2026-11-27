
function reportElement(tag, value, className) {
  const element = document.createElement(tag);
  if (value !== undefined) element.textContent = String(value);
  if (className) element.className = className;
  return element;
}

function reportTable(headers, rows) {
  const wrapper = reportElement("div", undefined, "report-table-wrap");
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const header = document.createElement("tr");

  for (const value of headers) {
    const cell = reportElement("th", value);
    cell.scope = "col";
    header.append(cell);
  }

  head.append(header);
  table.append(head);

  const body = document.createElement("tbody");

  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const value of row) {
      tr.append(reportElement("td", value));
    }
    body.append(tr);
  }

  table.append(body);
  wrapper.append(table);
  return wrapper;
}

function renderVerification(report) {
  const target = $("verification");
  const computed = $("computed");
  const v = report.verification;

  target.replaceChildren();
  computed.replaceChildren();
  $("computedSection").hidden = true;

  if (!v) {
    target.append(reportElement(
      "p",
      "Historical report. Enhanced verification record unavailable."
    ));
    return;
  }

  target.append(reportElement(
    "p",
    v.input_integrity === "verified"
      ? "Source integrity: verified."
      : "Source integrity: not established.",
    "verification-line"
  ));

  target.append(reportElement(
    "p",
    v.analytical_status === "recomputed_match"
      ? "Analytical evidence: recomputed and matched."
      : "Analytical recomputation: not applicable.",
    "verification-line"
  ));

  target.append(reportElement(
    "p",
    "AI summary and recommendations: not independently verified.",
    "verification-line"
  ));

  const findings = Array.isArray(v.analytical_findings)
    ? v.analytical_findings : [];

  for (const finding of findings) {
    if (finding.status !== "recomputed_match") continue;

    const result = finding.result;
    if (!result || typeof result !== "object") continue;

    const panel = reportElement(
      "div", undefined, "computed-panel"
    );

    if (finding.tool === "calculate") {
      panel.append(reportElement(
        "h4", "Calculation - E" + finding.evidence_id
      ));

      panel.append(reportTable(
        ["Operation", "Left", "Right", "Result"],
        [[
          result.operation,
          result.left,
          result.right,
          result.result
        ]]
      ));

      if (result.precision !== undefined) {
        panel.append(reportElement(
          "small",
          "Decimal precision: " + result.precision
        ));
      }

    } else if (
      finding.tool === "analyze_csv" && result.analysis
    ) {
      const a = result.analysis;

      panel.append(reportElement(
        "h4", result.path + " - E" + finding.evidence_id
      ));

      panel.append(reportElement(
        "p", "Rows analyzed: " + a.row_count
      ));

      const rows = Object.entries(a.numeric || {}).map(
        ([column, stats]) => [
          column,
          stats.count,
          stats.sum,
          stats.minimum,
          stats.maximum
        ]
      );

      if (rows.length) {
        panel.append(reportTable(
          ["Column", "Count", "Sum", "Minimum", "Maximum"],
          rows
        ));
      }

      for (const [category, groups] of Object.entries(
        a.grouped || {}
      )) {
        const groupedRows = [];

        for (const [label, group] of Object.entries(groups)) {
          for (const [column, total] of Object.entries(
            group.totals || {}
          )) {
            groupedRows.push([
              label, column, group.count, total
            ]);
          }
        }

        if (groupedRows.length) {
          const details = document.createElement("details");

          details.append(reportElement(
            "summary", "Grouped totals: " + category
          ));

          details.append(reportTable(
            ["Group", "Column", "Count", "Total"],
            groupedRows
          ));

          panel.append(details);
        }
      }

      panel.append(reportElement(
        "small",
        "Numeric identifiers may not represent meaningful totals. " +
        "See supporting evidence for full statistics and source lines."
      ));

    } else {
      continue;
    }

    computed.append(panel);
  }

  $("computedSection").hidden = !computed.childElementCount;
}


"use strict";
const $ = id => document.getElementById(id);
let current = "", mode = "", busy = false;
const active = ["QUEUED","CLOCKED_IN","WORKING","VERIFYING"];
async function api(path, data) {
  const opts = data === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json","X-Night-Shift":"1"}, body:JSON.stringify(data)};
  const res = await fetch(path, opts);
  const value = await res.json();
  if (!res.ok) throw Error(value.error || "Request failed");
  return value;
}
function showError(e) { $("notice").textContent = e.message; }
let evidenceJob = "";
let renderedReportJob = "";
let renderedReportContent = "";
function draw(job) {
  $("state").textContent = job.state;
  $("state").dataset.state = job.state;
  const notices = {
    READY: "Assignment prepared.",
    QUEUED: "Assignment queued. You can close this tab.",
    CLOCKED_IN: "Night Shift has clocked in.",
    WORKING: "Night Shift is working on your assignment.",
    VERIFYING: "Verifying the report and file integrity.",
    COMPLETED: "Shift complete. Your report is ready.",
    FAILED: "Assignment failed. Review the timeline.",
    CANCELLED: "Assignment cancelled.",
    INTERRUPTED: "Assignment interrupted. Review the timeline."
  };
  $("notice").textContent = notices[job.state] || "";
  $("cancel").hidden = !active.includes(job.state);
  $("timeline").replaceChildren(...job.events.map(event => {
    const li = document.createElement("li"), t = document.createElement("time");
    t.dateTime = event.at;
    t.textContent = new Date(event.at).toLocaleTimeString();
    li.append(t, event.message); return li;
  }));
  const r = job.report;
  $("results").hidden = !r;
  if (!r) {
    renderedReportJob = "";
    renderedReportContent = "";
    return;
  }

  const reportContent = JSON.stringify(r);

  if (
    renderedReportJob === job.id &&
    renderedReportContent === reportContent
  ) return;

  $("summary").textContent = r.summary + "  [" + r.references.map(i=>"E"+i).join(", ") + "]";
  $("scope").textContent = r.scope;
  renderVerification(r);
  $("md").href = "/api/jobs/"+job.id+"/report.md";
  $("json").href = "/api/jobs/"+job.id+"/report.json";
  const expanded = evidenceJob === job.id
    ? new Set(Array.from($("evidence").querySelectorAll("details[open]")).map(d => d.dataset.evidence))
    : new Set();
  evidenceJob = job.id;
  $("evidence").replaceChildren(...r.evidence.map(e => {
    const d = document.createElement("details"), title = document.createElement("summary"), pre = document.createElement("pre");
    d.dataset.evidence = String(e.id);
    d.open = expanded.has(String(e.id));
    title.textContent = "E"+e.id+" · "+e.action.tool;
    pre.textContent = JSON.stringify(e, null, 2); d.append(title,pre); return d;
  }));

  renderedReportJob = job.id;
  renderedReportContent = reportContent;
}
async function refresh() {
  if (busy) return;
  busy = true;
  try {
    const info = await api("/api/jobs");
    mode = info.mode;
    $("mode").textContent = mode === "mock" ? "Mock Mode" : mode === "ollama" ? "Live AI" : "Unknown mode";
    $("mode").dataset.mode = mode;
    $("privacy").textContent = mode === "mock"
      ? "Mock mode uses deterministic processing on the cloud worker. No Ollama inference is requested."
      : mode === "ollama"
      ? "Live assignments send the prompt and relevant file contents to Ollama Cloud. Upload only files you intend to share."
      : "Intelligence mode unavailable.";
    $("consentRow").hidden = mode !== "ollama";
    $("consent").required = mode === "ollama";
    $("start").disabled = submitting;
    if (!info.jobs.length) return;
    if (!info.jobs.some(j=>j.id===current)) current = info.jobs[0].id;
    $("jobs").replaceChildren(...info.jobs.map(j=>new Option(j.assignment.slice(0,64)+" · "+j.state,j.id)));
    $("jobs").value = current;
    const job = await api("/api/jobs/"+current);
    if (job.id===current) draw(job);
  } finally { busy = false; }
}
let submitting = false;
$("jobs").onchange = () => { current = $("jobs").value; refresh().catch(showError); };
$("form").onsubmit = async e => {
  e.preventDefault();
  if (submitting) return;
  submitting = true; $("start").disabled = true; $("notice").textContent = "";
  try {
    const files = Array.from($("files").files);
    if (files.length>12 || files.reduce((n,f)=>n+f.size,0)>4*1024*1024) throw Error("Choose up to 12 files totalling at most 4 MiB.");
    const uploads = [];
    for (const file of files) {
      const data = await new Promise((resolve,reject)=>{
        const r = new FileReader(); r.onload=()=>resolve(r.result.split(",")[1]); r.onerror=()=>reject(Error("File read failed")); r.readAsDataURL(file);
      });
      uploads.push({name:file.name,data});
    }
    const job = await api("/api/jobs",{assignment:$("assignment").value,files:uploads,cloud_consent:$("consent").checked});
    current = job.id; $("form").reset(); $("notice").textContent="Assignment queued. You can close this tab.";
    await refresh();
  } catch(e) { showError(e); } finally { submitting=false; $("start").disabled=!mode; }
};
$("cancel").onclick=async()=>{try {await api("/api/jobs/"+current+"/cancel",{}); await refresh();} catch(e){showError(e);}};
refresh().catch(showError);
setInterval(()=>refresh().catch(showError),1800);
