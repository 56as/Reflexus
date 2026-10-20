const state = {
  ready: false,
  topics: [],
  sources: [],
  topic: null,
  item: null,
  polling: false,
  view: "sources",
  sourcePage: "list",
};

const $ = (id) => document.getElementById(id);

window.addEventListener("pywebviewready", boot);
if (window.pywebview && window.pywebview.api) boot();

async function boot() {
  if (state.ready) return;
  state.ready = true;
  try {
    await start();
  } catch (error) {
    state.ready = false;
    $("boot").hidden = false;
    $("boot").textContent = error.message;
  }
}

async function start() {
  $("boot").hidden = true;
  $("app").hidden = false;
  $("new-topic").addEventListener("submit", createTopic);
  $("save").addEventListener("click", () => saveTopic());
  $("back-sources").addEventListener("click", () => showSourcePage("list"));
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });
  $("bilibili").addEventListener("input", refreshBilibiliCheck);
  $("launch").addEventListener("click", launchBilibili);
  $("import-inbox").addEventListener("click", importInbox);
  $("another").addEventListener("click", pickAnother);
  $("open-url").addEventListener("click", openItemUrl);
  $("ask-item").addEventListener("click", askAboutItem);
  $("chat-form").addEventListener("submit", sendChat);
  document.querySelectorAll("[data-status]").forEach((button) => {
    button.addEventListener("click", () => setReview(button.dataset.status));
  });
  const sourceResult = await api("list_sources");
  state.sources = sourceResult.sources || [];
  renderSourceList();
  renderSource(state.sources.find((source) => source.id === "bilibili"));
  if (sourceResult.errors && sourceResult.errors.length) {
    showSourceError(sourceResult.errors.join(" "));
  }
  await reloadTopics();
}

async function api(name, ...args) {
  const result = await window.pywebview.api[name](...args);
  if (!result.ok) {
    throw new Error(result.error || "操作没有完成");
  }
  return result;
}

async function reloadTopics(selectName) {
  const result = await api("list_topics");
  state.topics = result.topics;
  if (selectName) {
    await openTopic(selectName);
  } else if (state.topic) {
    await openTopic(state.topic.name);
  } else if (state.topics.length) {
    await openTopic(state.topics[0].name);
  } else {
    renderTopics();
    $("empty").hidden = false;
    $("desk").hidden = true;
  }
}

function renderTopics() {
  const nav = $("topics");
  nav.replaceChildren();
  state.topics.forEach((topic) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "topic" + (state.topic && state.topic.name === topic.name ? " active" : "");
    const name = document.createElement("span");
    name.textContent = topic.name;
    const meta = document.createElement("small");
    meta.textContent = topic.unread_count ? `${topic.unread_count} 条未读` : `${topic.item_count} 条材料`;
    button.append(name, meta);
    button.addEventListener("click", () => openTopic(topic.name));
    nav.append(button);
  });
}

async function createTopic(event) {
  event.preventDefault();
  const input = $("topic-name");
  try {
    const result = await api("create_topic", input.value);
    input.value = "";
    state.topics = result.topics;
    await openTopic(result.topic.name);
  } catch (error) {
    input.placeholder = error.message;
  }
}

async function openTopic(name) {
  const result = await api("get_topic", name);
  state.topic = result.topic;
  $("empty").hidden = true;
  $("desk").hidden = false;
  $("topic-title").textContent = result.topic.name;
  $("interest").value = result.topic.interest;
  $("keywords").value = result.topic.keywords;
  $("questions").value = result.topic.questions;
  $("bilibili").value = result.topic.bilibili;
  $("inbox-count").textContent = `收件箱 ${result.topic.inbox_count} 份，已导入 ${result.topic.item_count} 条`;
  refreshBilibiliCheck();
  renderTopics();
  showView("sources");
  showSourcePage("list");
  await Promise.all([loadRun(), loadReview(), loadChat()]);
}

function showView(view) {
  state.view = view;
  $("view-sources").hidden = view !== "sources";
  $("view-review").hidden = view !== "review";
  $("view-chat").hidden = view !== "chat";
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
    button.classList.toggle("ghost", button.dataset.view !== view);
  });
}

function showSourcePage(page) {
  state.sourcePage = page;
  $("source-home").hidden = page !== "list";
  $("bilibili-page").hidden = page !== "bilibili";
}

function renderSourceList() {
  const list = $("source-list");
  list.replaceChildren();
  const known = {
    bilibili: "视频、口播全文和播放地址",
  };
  if (!state.sources.length) {
    const empty = document.createElement("p");
    empty.className = "quiet";
    empty.textContent = "还没有信息源。把清单放到 sources/ 后会出现在这里。";
    list.append(empty);
    return;
  }
  state.sources.forEach((source) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "source-card";
    const title = document.createElement("strong");
    title.textContent = source.label;
    const detail = document.createElement("small");
    detail.textContent = known[source.id] || "进入这个信息源";
    button.append(title, detail);
    button.addEventListener("click", () => showSourcePage(source.id === "bilibili" ? "bilibili" : "list"));
    list.append(button);
  });
}

function fields() {
  return [
    state.topic.name,
    $("interest").value,
    $("keywords").value,
    $("questions").value,
    $("bilibili").value,
  ];
}

async function saveTopic() {
  const result = await api("save_topic", ...fields());
  state.topic = result.topic;
  $("inbox-count").textContent = `收件箱 ${result.topic.inbox_count} 份，已导入 ${result.topic.item_count} 条`;
}

async function refreshBilibiliCheck() {
  const result = await api("check_bilibili", $("bilibili").value);
  $("bilibili-check").textContent = result.summary;
}

function renderSource(source) {
  if (!source) {
    showSourceError("还没有 sources/bilibili.json");
    $("launch").disabled = true;
    return;
  }
  $("source-label").textContent = source.label;
  $("source-command").textContent = source.command.join(" ");
  $("source-cwd").textContent = source.cwd;
  if (!source.cwd_ready) {
    showSourceError("找不到启动目录，按钮已停用");
    $("launch").disabled = true;
  }
}

function showSourceError(message) {
  const node = $("source-missing");
  node.hidden = false;
  node.textContent = message;
}

async function launchBilibili() {
  $("launch").disabled = true;
  try {
    const [name, interest, keywords, questions, bilibili] = fields();
    const result = await api("launch_source", name, "bilibili", interest, keywords, questions, bilibili);
    state.topic = result.topic;
    showRun(result.status);
    pollRun();
  } catch (error) {
    $("run-state").textContent = error.message;
    $("run-state").className = "pill error";
    $("launch").disabled = false;
  }
}

function pollRun() {
  if (state.polling) return;
  state.polling = true;
  const name = state.topic.name;
  const timer = setInterval(async () => {
    try {
      const result = await api("source_status", name, "bilibili");
      const same = state.topic && state.topic.name === name;
      if (same) showRun(result.status);
      if (result.status.state !== "running") {
        clearInterval(timer);
        state.polling = false;
        if (same) {
          state.topic = result.topic;
          $("inbox-count").textContent = `收件箱 ${result.topic.inbox_count} 份，已导入 ${result.topic.item_count} 条`;
          await loadReview();
          renderTopics();
        }
      }
    } catch (error) {
      clearInterval(timer);
      state.polling = false;
      $("run-state").textContent = error.message;
    }
  }, 800);
}

async function loadRun() {
  const result = await api("source_status", state.topic.name, "bilibili");
  showRun(result.status);
  if (result.status.state === "running") pollRun();
}

function showRun(run) {
  const pill = $("run-state");
  pill.textContent = run.message || "还没有运行";
  pill.className = "pill " + (run.state || "idle");
  const lines = [run.tail || "还没有输出。"];
  if (run.errors && run.errors.length) lines.push("", ...run.errors);
  $("run-log").textContent = lines.join("\n");
  const source = state.sources.find((item) => item.id === "bilibili");
  $("launch").disabled = run.state === "running" || !source || !source.cwd_ready;
}

async function importInbox() {
  await saveTopic();
  const result = await api("import_inbox", state.topic.name);
  state.topic = result.topic;
  const taken = result.result.created + result.result.updated;
  $("run-log").textContent = `导入 ${taken} 条。` + (result.result.errors || []).join("\n");
  $("inbox-count").textContent = `收件箱 ${result.topic.inbox_count} 份，已导入 ${result.topic.item_count} 条`;
  renderTopics();
  await loadReview();
}

async function loadReview() {
  const result = await api("pick_item", state.topic.name, "");
  showItem(result.item);
}

async function pickAnother() {
  const current = state.item ? state.item.id : "";
  const result = await api("pick_item", state.topic.name, current);
  showItem(result.item);
}

function showItem(item) {
  state.item = item;
  $("review-empty").hidden = Boolean(item);
  $("review").hidden = !item;
  if (!item) return;
  const labels = { unread: "未读", kept: "采纳", dropped: "丢弃", unsure: "存疑" };
  $("item-source").textContent = item.source + " · " + item.external_id;
  $("item-status").textContent = labels[item.status] || item.status;
  $("item-title").textContent = item.title;
  $("item-summary").textContent = item.summary || "还没有摘要";
  $("item-body").textContent = item.body || "";
  $("judgment").value = item.judgment || "";
}

async function setReview(status) {
  if (!state.item) return;
  const result = await api("review_item", state.topic.name, state.item.id, status, $("judgment").value);
  state.topic = result.topic;
  showItem(result.item);
  renderTopics();
}

async function openItemUrl() {
  if (!state.item) return;
  await api("open_url", state.item.url);
}

function askAboutItem() {
  if (!state.item) return;
  showView("chat");
  $("chat-input").value = `关于「${state.item.title}」，我想确认：`;
  $("chat-input").focus();
}

async function loadChat() {
  const result = await api("read_chat", state.topic.name);
  renderMessages(result.messages);
}

async function sendChat(event) {
  event.preventDefault();
  const input = $("chat-input");
  const result = await api("send_chat", state.topic.name, input.value);
  input.value = "";
  renderMessages(result.messages);
}

function renderMessages(messages) {
  const box = $("messages");
  box.replaceChildren();
  if (!messages.length) {
    const empty = document.createElement("p");
    empty.className = "quiet";
    empty.textContent = "还没有提问。";
    box.append(empty);
    return;
  }
  messages.forEach((message) => {
    const block = document.createElement("div");
    block.className = "message" + (message.role === "user" ? " user" : "");
    const who = document.createElement("small");
    who.textContent = (message.role === "user" ? "我" : "平台") + " · " + message.at;
    const text = document.createElement("p");
    text.textContent = message.text;
    block.append(who, text);
    box.append(block);
  });
  box.scrollTop = box.scrollHeight;
}
