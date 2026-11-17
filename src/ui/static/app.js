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

function renderClaims(box, claims) {
  box.replaceChildren();
  claims.forEach((claim, i) => {
    const card = document.createElement("div");
    card.className = "claim";
    const title = document.createElement("strong");
    title.textContent = `#${i + 1}`;
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(claim, null, 2);
    card.appendChild(title);
    card.appendChild(pre);
    box.appendChild(card);
  });
}

async function loadRun() {
  const id = document.getElementById("runId").value.trim();
  const res = await fetch(`/runs/${id}`);
  const data = await readResponse(res);
  document.getElementById("status").textContent = JSON.stringify(data, null, 2);
  if (data.error) {
    document.getElementById("claims").replaceChildren();
    return;
  }
  renderClaims(document.getElementById("claims"), data.claims || []);
}

async function verdict(v) {
  const id = document.getElementById("runId").value.trim();
  const key = `hitl-${id}-${v}`;
  const res = await fetch(`/runs/${id}/verdicts`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify({ verdict: v, message: "hitl ui" }),
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