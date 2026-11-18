async function readResponse(res) {
  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { detail: text || res.statusText };
  }
  if (!res.ok) {
    return {
      error: true,
      status: res.status,
      statusText: res.statusText,
      body,
    };
  }
  return body;
}

function badge(label, value) {
  const span = document.createElement("span");
  span.className = `badge ${value === "ok" || value === "grounded" ? "good" : value === "blocked" ? "bad" : "warn"}`;
  span.textContent = `${label}: ${value}`;
  return span;
}

function renderDiff(box, data) {
  box.replaceChildren();
  const documents = data.documents || {};
  const paths = Object.keys(documents);
  if (paths.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Нет изменений для показа.";
    box.appendChild(empty);
    return;
  }
  paths.forEach((path) => {
    const title = document.createElement("h3");
    title.textContent = path;
    box.appendChild(title);
    if (documents[path].truncated) {
      const note = document.createElement("p");
      note.className = "muted";
      note.textContent = "Документ обрезан для просмотра.";
      box.appendChild(note);
    }
    const pre = document.createElement("pre");
    pre.className = "diff-body";
    (data.diff?.[path] || []).forEach((line) => {
      const row = document.createElement("span");
      row.className = "diff-line";
      if (line.startsWith("+") && !line.startsWith("+++")) {
        row.classList.add("add");
      } else if (line.startsWith("-") && !line.startsWith("---")) {
        row.classList.add("del");
      }
      row.textContent = line || " ";
      pre.appendChild(row);
    });
    box.appendChild(pre);
  });
}

function renderClaims(box, claims, validations) {
  box.replaceChildren();
  if (!claims || claims.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Нет claims в этом run.";
    box.appendChild(empty);
    return;
  }
  claims.forEach((claim, i) => {
    const card = document.createElement("div");
    card.className = "claim";
    const title = document.createElement("strong");
    title.textContent = `#${i + 1} ${claim.path || "без path"}`;
    card.appendChild(title);

    const text = document.createElement("p");
    text.className = "claim-text";
    text.textContent = claim.text;
    card.appendChild(text);

    const quote = document.createElement("blockquote");
    quote.textContent = claim.quote;
    card.appendChild(quote);

    const validation = (validations || [])[i] || {};
    const badges = document.createElement("div");
    badges.className = "badges";
    badges.appendChild(badge("evidence", validation.evidence || "skipped"));
    badges.appendChild(badge("binding", validation.binding || "skipped"));
    badges.appendChild(badge("support", validation.support || "skipped"));
    badges.appendChild(badge("status", validation.status || "unknown"));
    card.appendChild(badges);

    if (validation.reason) {
      const reason = document.createElement("p");
      reason.className = "muted";
      reason.textContent = validation.reason;
      card.appendChild(reason);
    }
    box.appendChild(card);
  });
}

let currentRun = null;

async function loadRun() {
  const id = document.getElementById("runId").value.trim();
  if (!id) {
    return;
  }
  const res = await fetch(`/runs/${id}`);
  const data = await readResponse(res);
  if (data.error) {
    document.getElementById("status").textContent = data.statusText || "ошибка загрузки";
    document.getElementById("diff").replaceChildren();
    document.getElementById("claims").replaceChildren();
    return;
  }
  currentRun = data;
  document.getElementById("status").textContent =
    `status: ${data.status}, draft: ${data.draft_id || "-"}, base: ${data.expected_head || "genesis"}`;
  renderDiff(document.getElementById("diff"), data);
  renderClaims(document.getElementById("claims"), data.claims || [], data.validations || []);
  const closed = ["blocked", "published", "rejected"].includes(data.status);
  document.getElementById("acceptBtn").disabled = closed;
  document.getElementById("rejectBtn").disabled = closed;
}

async function verdict(v) {
  const id = document.getElementById("runId").value.trim();
  const key = `hitl-${id}-${v}`;
  const payload = { verdict: v, message: "hitl ui" };
  if (currentRun && currentRun.expected_head) {
    payload.expected_head = currentRun.expected_head;
  }
  const res = await fetch(`/runs/${id}/verdicts`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify(payload),
  });
  const data = await readResponse(res);
  document.getElementById("result").textContent = JSON.stringify(data, null, 2);
  if (!data.error) {
    await loadRun();
  }
}

document.getElementById("loadBtn").onclick = loadRun;
document.getElementById("acceptBtn").onclick = () => verdict("accept");
document.getElementById("rejectBtn").onclick = () => verdict("reject");
