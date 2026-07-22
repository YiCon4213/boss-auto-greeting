const state = {
  batch: null,
  activeIndex: 0,
  timer: null,
  busy: false,
};

const batchForm = document.querySelector("#batch-form");
const batchIdInput = document.querySelector("#batch-id");
const batchHeading = document.querySelector("#batch-heading");
const batchSummary = document.querySelector("#batch-summary");
const analyzeButton = document.querySelector("#analyze-button");
const notice = document.querySelector("#notice");
const jobList = document.querySelector("#job-list");
const queueCount = document.querySelector("#queue-count");
const emptyState = document.querySelector("#empty-state");
const detailContent = document.querySelector("#detail-content");
const detailCompany = document.querySelector("#detail-company");
const detailTitle = document.querySelector("#detail-title");
const detailSelected = document.querySelector("#detail-selected");
const targetScore = document.querySelector("#target-score");
const personalScore = document.querySelector("#personal-score");
const recommendation = document.querySelector("#recommendation");
const jobDescription = document.querySelector("#job-description");
const matchReasons = document.querySelector("#match-reasons");
const cautions = document.querySelector("#cautions");
const greetingEditor = document.querySelector("#greeting-editor");
const greetingCount = document.querySelector("#greeting-count");
const saveButton = document.querySelector("#save-button");
const approveButton = document.querySelector("#approve-button");

function showNotice(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle("error", isError);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      if (body.detail) message = body.detail;
    } catch (_error) {
      // Keep the status-only message when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

function appendList(container, values, fallback) {
  container.replaceChildren();
  const items = values && values.length ? values : [fallback];
  for (const value of items) {
    const item = document.createElement("li");
    item.textContent = value;
    container.append(item);
  }
}

function statusLabel(status) {
  const labels = {
    collected: "等待分析",
    analyzing: "分析中",
    awaiting_approval: "等待人工审批",
    approved: "已批准并冻结",
  };
  return labels[status] || status || "未知";
}

function currentItem() {
  return state.batch && state.batch.items[state.activeIndex];
}

function updateApprovalState() {
  const reviewReady = state.batch && state.batch.status === "awaiting_approval";
  const blocked = reviewReady
    ? state.batch.items.some((item) => item.selected && !item.approvable)
    : true;
  const invalidText = reviewReady
    ? state.batch.items.some((item) => {
        const greeting = (item.greeting || "").trim();
        return item.selected && (greeting.length < 20 || greeting.length > 500);
      })
    : true;
  approveButton.disabled = state.busy || !reviewReady || blocked || invalidText;
  saveButton.disabled = state.busy || !reviewReady || !currentItem();
}

function renderQueue() {
  jobList.replaceChildren();
  const items = state.batch ? state.batch.items : [];
  queueCount.textContent = String(items.length);
  items.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `job-card${index === state.activeIndex ? " active" : ""}`;

    const top = document.createElement("div");
    top.className = "job-card-top";
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.snapshot.title || "未命名岗位";
    const company = document.createElement("p");
    company.textContent = item.snapshot.company || "未知公司";
    const score = document.createElement("span");
    score.className = "job-card-score";
    score.textContent = item.analysis.target_score == null ? "—" : String(item.analysis.target_score);
    copy.append(title, company);
    top.append(copy, score);

    const selection = document.createElement("p");
    selection.textContent = item.selected ? "已选择" : "未选择";
    button.append(top, selection);
    button.addEventListener("click", () => {
      state.activeIndex = index;
      render();
    });
    jobList.append(button);
  });
}

function renderDetail() {
  const item = currentItem();
  emptyState.hidden = Boolean(item);
  detailContent.hidden = !item;
  if (!item) return;

  detailCompany.textContent = item.snapshot.company || "未知公司";
  detailTitle.textContent = item.snapshot.title || "未命名岗位";
  detailSelected.checked = Boolean(item.selected);
  detailSelected.disabled = state.batch.status !== "awaiting_approval";
  targetScore.textContent = item.analysis.target_score == null ? "—" : String(item.analysis.target_score);
  personalScore.textContent = item.analysis.personal_score == null ? "—" : String(item.analysis.personal_score);
  recommendation.textContent = item.analysis.recommendation || "—";
  jobDescription.textContent = item.snapshot.description || "暂无职位描述";
  appendList(matchReasons, item.analysis.target_reasons, "暂无可展示的匹配依据");
  appendList(cautions, item.analysis.cautions, "暂无风险提示");
  greetingEditor.value = item.greeting || "";
  greetingEditor.disabled = state.batch.status !== "awaiting_approval";
  greetingCount.textContent = `${greetingEditor.value.length} / 500`;
}

function render() {
  if (!state.batch) {
    batchHeading.textContent = "加载需要审批的批次";
    batchSummary.textContent = "输入批次 ID 后读取冻结快照。";
  } else {
    batchHeading.textContent = statusLabel(state.batch.status);
    const selected = state.batch.items.filter((item) => item.selected).length;
    batchSummary.textContent = `${state.batch.items.length} 个岗位，当前选择 ${selected} 个`;
  }
  renderQueue();
  renderDetail();
  updateApprovalState();
}

function stopPolling() {
  if (state.timer) window.clearInterval(state.timer);
  state.timer = null;
}

function startPolling() {
  stopPolling();
  state.timer = window.setInterval(() => loadReview(true), 2000);
}

async function loadReview(silent = false) {
  const batchId = batchIdInput.value.trim();
  if (!batchId) return;
  try {
    const batch = await api(`/api/v1/batches/${encodeURIComponent(batchId)}/review`);
    state.batch = batch;
    state.activeIndex = Math.min(state.activeIndex, Math.max(0, batch.items.length - 1));
    render();
    if (batch.status === "awaiting_approval" || batch.status === "approved") {
      stopPolling();
    }
    if (!silent) showNotice("批次已加载。", false);
  } catch (error) {
    if (!silent) showNotice(error.message, true);
  }
}

batchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const batchId = batchIdInput.value.trim();
  window.history.replaceState(null, "", `?batch=${encodeURIComponent(batchId)}`);
  await loadReview();
});

analyzeButton.addEventListener("click", async () => {
  const batchId = batchIdInput.value.trim();
  if (!batchId || state.busy) return;
  state.busy = true;
  updateApprovalState();
  try {
    await api(`/api/v1/batches/${encodeURIComponent(batchId)}/analyze`, { method: "POST" });
    showNotice("分析任务已启动，正在等待结构化结果。", false);
    startPolling();
    await loadReview(true);
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.busy = false;
    updateApprovalState();
  }
});

detailSelected.addEventListener("change", () => {
  const item = currentItem();
  if (!item) return;
  item.selected = detailSelected.checked;
  renderQueue();
  updateApprovalState();
});

greetingEditor.addEventListener("input", () => {
  const item = currentItem();
  if (!item) return;
  item.greeting = greetingEditor.value;
  greetingCount.textContent = `${greetingEditor.value.length} / 500`;
  updateApprovalState();
});

saveButton.addEventListener("click", async () => {
  const item = currentItem();
  if (!item || state.busy) return;
  state.busy = true;
  updateApprovalState();
  try {
    const saved = await api(
      `/api/v1/batches/${encodeURIComponent(state.batch.batch_id)}/drafts/${encodeURIComponent(item.snapshot_id)}`,
      {
        method: "PATCH",
        body: JSON.stringify({ selected: item.selected, greeting: item.greeting }),
      },
    );
    item.selected = saved.selected;
    item.greeting = saved.greeting;
    showNotice("本项草稿已保存。", false);
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.busy = false;
    render();
  }
});

approveButton.addEventListener("click", async () => {
  if (!state.batch || approveButton.disabled) return;
  state.busy = true;
  updateApprovalState();
  try {
    await api(`/api/v1/batches/${encodeURIComponent(state.batch.batch_id)}/approve`, {
      method: "POST",
      body: JSON.stringify({
        items: state.batch.items.map((item) => ({
          snapshot_id: item.snapshot_id,
          selected: item.selected,
          greeting: item.greeting || "",
        })),
      }),
    });
    state.batch.status = "approved";
    showNotice("已批准，等待用户在 Phase 4 显式开始执行", false);
    stopPolling();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.busy = false;
    render();
  }
});

const initialBatch = new URLSearchParams(window.location.search).get("batch");
if (initialBatch) {
  batchIdInput.value = initialBatch;
  loadReview();
} else {
  render();
}
