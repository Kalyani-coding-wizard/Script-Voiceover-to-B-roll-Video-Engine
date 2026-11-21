const form = document.querySelector("#job-form");
const submit = document.querySelector("#submit");
const jobPanel = document.querySelector("#job");
const empty = document.querySelector("#empty");
const progress = document.querySelector("#progress");
const state = document.querySelector("#state");
const jobId = document.querySelector("#job-id");
const errorPanel = document.querySelector("#error");
const downloads = document.querySelector("#downloads");
const health = document.querySelector("#health");

async function checkHealth() {
  try {
    const res = await fetch("/ready");
    health.textContent = res.ok ? "API ready" : "API unavailable";
    health.className = `health ${res.ok ? "ok" : "bad"}`;
  } catch {
    health.textContent = "API unavailable";
    health.className = "health bad";
  }
}

function showError(error) {
  errorPanel.hidden = false;
  errorPanel.textContent = error?.message || "Generation failed.";
}

function showDownloads(result) {
  downloads.innerHTML = "";
  if (!result) return;
  const links = [
    ...Object.entries(result.videos || {}).map(([ratio, url]) => [ratio, url]),
    ["Captions (SRT)", result.captions_srt],
    ["Timeline JSON", result.timeline_url],
    ["Manifest JSON", result.manifest_url],
  ].filter(([, url]) => url);
  links.forEach(([label, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = label;
    downloads.appendChild(link);
  });
  downloads.hidden = links.length === 0;
}

async function poll(jobIdValue) {
  while (true) {
    const res = await fetch(`/api/v1/jobs/${jobIdValue}`);
    if (!res.ok) throw new Error(`Status request failed (${res.status})`);
    const data = await res.json();
    progress.style.width = `${data.progress}%`;
    state.textContent = `${data.status.charAt(0).toUpperCase()}${data.status.slice(1)} · ${data.progress}%`;

    if (data.status === "succeeded") {
      showDownloads(data.result);
      errorPanel.hidden = true;
      return;
    }
    if (data.status === "failed") {
      showError(data.error);
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  submit.disabled = true;
  submit.textContent = "Queuing...";
  empty.hidden = true;
  jobPanel.hidden = false;
  errorPanel.hidden = true;
  downloads.hidden = true;
  downloads.innerHTML = "";
  progress.style.width = "0";

  const payload = {
    script: document.querySelector("#script").value.trim(),
    voice: document.querySelector("#voice").value,
    language: "auto",
    aspect_ratios: [document.querySelector("#aspect").value],
    style: document.querySelector("#style").value.trim(),
    captions: { burn_in: true, srt: true },
  };

  try {
    const res = await fetch("/api/v1/broll/jobs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `web-${crypto.randomUUID()}`,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json();
      throw new Error(body?.error?.message || `Job submission failed (${res.status})`);
    }
    const data = await res.json();
    jobId.textContent = data.job_id;
    state.textContent = "Queued · 0%";
    await poll(data.job_id);
  } catch (error) {
    showError(error);
  } finally {
    submit.disabled = false;
    submit.textContent = "Generate video";
  }
});

checkHealth();
