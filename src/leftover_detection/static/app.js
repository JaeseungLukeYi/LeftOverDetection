const form = document.getElementById("upload-form");
const filesInput = document.getElementById("files");
const statusBox = document.getElementById("status");
const resultsBox = document.getElementById("results");
const reportBox = document.getElementById("report");
const reportRangeBox = document.getElementById("report-range");
const submitBtn = document.getElementById("submit-btn");

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderResultCard(item) {
  const cls = item.status === "ok" ? "result-card" : "result-card error";
  const header = `<div class="result-header"><strong>${escapeHtml(item.file || "(unknown)")}</strong><span>${escapeHtml(item.status)}</span></div>`;

  if (item.status !== "ok") {
    return `<article class="${cls}">${header}<div>${escapeHtml(item.error || "Unknown error")}</div></article>`;
  }

  if (item.type === "reference") {
    return `<article class="${cls}">${header}<div>Reference registered for date: <strong>${escapeHtml(item.served_date || "")}</strong></div></article>`;
  }

  const foods = (item.foods || [])
    .map(
      (f) =>
        `<li>${escapeHtml(f.food_item)}: ${f.leftover_percent}% <em>(${escapeHtml(f.category)})</em></li>`,
    )
    .join("");

  return `
    <article class="${cls}">
      ${header}
      <div>Plate: <strong>${escapeHtml(item.plate_id)}</strong> | Date: ${escapeHtml(item.served_date)}</div>
      <div>Reference: ${escapeHtml(item.reference_used || "none")}</div>
      <ul>${foods || "<li>No leftovers detected.</li>"}</ul>
    </article>
  `;
}

function renderReport(report) {
  if (!report) {
    reportBox.innerHTML = "<p>No report generated.</p>";
    reportRangeBox.textContent = "";
    return;
  }

  const findings = (report.key_findings || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("");
  const recommendations = (report.recommendations || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("");

  reportBox.innerHTML = `
    <h3>Overview</h3>
    <p>${escapeHtml(report.overview || "")}</p>
    <h3>Key Findings</h3>
    <ul>${findings || "<li>No findings.</li>"}</ul>
    <h3>Recommendations</h3>
    <ul>${recommendations || "<li>No recommendations.</li>"}</ul>
  `;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!filesInput.files.length) {
    statusBox.textContent = "Select at least one image file.";
    return;
  }

  const body = new FormData();
  for (const file of filesInput.files) {
    body.append("files", file);
  }

  submitBtn.disabled = true;
  statusBox.textContent = "Analyzing images...";
  resultsBox.innerHTML = "";
  reportBox.innerHTML = "";
  reportRangeBox.textContent = "";

  try {
    const response = await fetch("/api/analyze", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Request failed");
    }

    const results = data.results || [];
    statusBox.textContent = `Processed ${results.length} file(s).`;
    resultsBox.innerHTML = results.map(renderResultCard).join("");

    if (data.report_range) {
      reportRangeBox.textContent = `Range: ${data.report_range.start_date} to ${data.report_range.end_date}`;
    }
    renderReport(data.report);
  } catch (error) {
    statusBox.textContent = `Error: ${error.message}`;
  } finally {
    submitBtn.disabled = false;
  }
});
