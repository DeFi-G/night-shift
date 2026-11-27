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
  if (!r) return;
  $("summary").textContent = r.summary + "  [" + r.references.map(i=>"E"+i).join(", ") + "]";
  $("scope").textContent = r.scope;
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
