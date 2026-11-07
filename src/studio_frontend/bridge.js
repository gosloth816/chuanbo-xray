const streamlitMessage = (type, data = {}) => {
  window.parent.postMessage({isStreamlitMessage: true, type, ...data}, "*");
};
const sendAction = (action, values = {}) => {
  streamlitMessage("streamlit:setComponentValue", {
    dataType: "json", value: {action, ...values, id: crypto.randomUUID()}
  });
};
const channelKeys = {"朋友圈": "moments", "商品详情页": "detail", "短视频口播": "script"};
const form = document.getElementById("product-form");
function productValues() {
  return Object.fromEntries(["f0", "f1", "f2", "f3", "f4", "intro"].map(name => [name, form.elements[name].value.trim()]));
}
function imageData(file) {
  if (!file.size) return Promise.resolve("");
  if (file.size > 10 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    return Promise.reject(new Error("请选择 10 MB 以内的 JPG、PNG 或 WEBP 图片。"));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("读取商品图片失败。"));
    reader.readAsDataURL(file);
  });
}
async function sendProduct(action) {
  try {
    sendAction(action, {product: productValues(), photo: await imageData(new FormData(form).get("photo"))});
  } catch (error) {
    showToast(error.message);
  }
}
function startNewProduct() {
  form.reset();
  productDialog.showModal();
}
document.getElementById("add-product").onclick = startNewProduct;
form.onsubmit = async event => {
  event.preventDefault();
  const file = new FormData(form).get("photo");
  try {
    const photo = await imageData(file);
    if (!productValues().f0) return;
    sendAction("product", {product: productValues(), photo, history_id: crypto.randomUUID()});
    productDialog.close();
  } catch (error) {
    showToast(error.message);
  }
};
document.getElementById("extract-product").onclick = () => {
  if (!document.getElementById("allow-extract").checked) return showToast("请先确认允许发送图片和介绍。");
  sendProduct("extract");
};
const generateButton = document.getElementById("generate-copy");
const generationStatus = document.createElement("p");
generationStatus.className = "notice";
generationStatus.setAttribute("role", "status");
generateButton.after(generationStatus);
let generationTimer;
function finishGeneration(message) {
  clearTimeout(generationTimer);
  generateButton.disabled = false;
  generateButton.textContent = "生成文案";
  generationStatus.textContent = message;
}
generateButton.onclick = () => {
  if (!document.getElementById("allow-generate").checked) {
    generationStatus.textContent = "请先确认允许发送商品资料。";
    return;
  }
  generateButton.disabled = true;
  generateButton.textContent = "生成中…";
  generationStatus.textContent = "已提交生成请求，请稍候。";
  generationTimer = setTimeout(() => finishGeneration("等待响应超时。请检查连接后再试。"), 125000);
  sendAction("generate", {audience: document.getElementById("b-audience").value, tone: document.getElementById("b-tone").value, direction: document.getElementById("creative-direction").value.trim(),
    focus: [...document.querySelectorAll(".inspector-facts input:checked")].map(input => input.value)});
};
function currentEdits() {
  stashDraft();
  return Object.fromEntries(Object.entries(draftEdits).map(([key, value]) => [samples[key].label, value]));
}
document.getElementById("open-workbench").onclick = () => sendAction("open_review");
document.getElementById("review-copy").onclick = () => sendAction("review", {edits: currentEdits()});
window.savePreview = () => sendAction("save", {edits: currentEdits()});
let applied = "";
let hydrated = false;
function leaveDemo() {
  document.body.classList.add("merchant-product");
  document.querySelectorAll("[data-demo-only], #sample-disclaimer").forEach(node => node.hidden = true);
  const direction = document.getElementById("creative-direction");
  if (direction.value === direction.defaultValue) direction.value = "";
}
function renderFocus(product) {
  const group = document.querySelector(".inspector-facts");
  group.replaceChildren();
  for (const [index, field] of [[1, "产地"], [2, "规格"], [3, "价格"], [4, "特点"]]) {
    const value = product?.["f" + index];
    if (!value) continue;
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = "F" + (index + 1);
    label.append(checkbox, document.createTextNode(field + "：" + value));
    group.append(label);
  }
  if (!group.children.length) group.textContent = "补充商品事实后可选择主推信息。";
}
function restoreProduct(product) {
  leaveDemo();
  renderFocus(product);
  for (const key of ["f0", "f1", "f2", "f3", "f4", "intro"]) {
    form.elements[key].value = product[key] || "";
  }
  productSource.querySelector("h3").textContent = product.f0;
  productSource.querySelectorAll("dd").forEach((field, index) => {
    field.textContent = product["f" + (index + 1)] || "未填写";
  });
  productSource.querySelector(".notice").textContent = product.intro || "商品资料已确认。";
  const image = productSource.querySelector("img");
  image.hidden = !product.photo;
  productPhotoUrl = product.photo || undefined;
  if (product.photo) {
    image.src = product.photo;
    image.alt = product.f0 + "的上传图片";
  }
  document.getElementById("origin-name").textContent = product.f1 || "未填写";
  document.querySelector(".b-toolbar h1").textContent = product.f0;
}

const historyPage = document.getElementById("history-page");
const historyList = document.getElementById("history-list");
const historyEntry = document.getElementById("open-history");
let historyDatabase;
function openHistoryDatabase() {
  historyDatabase ||= new Promise((resolve, reject) => {
    const request = indexedDB.open("qilu-product-history", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("products", {keyPath: "id"});
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  return historyDatabase;
}

async function rememberProduct(product, draft) {
  try {
    const db = await openHistoryDatabase();
    const transaction = db.transaction("products", "readwrite");
    transaction.onabort = () => showToast("浏览器未能保存商品历史，请检查存储空间或隐私设置。");
    transaction.objectStore("products").put({id: product.history_id, product, draft, updated: Date.now()});
  } catch {
    showToast("浏览器未能保存商品历史，请检查存储空间或隐私设置。");
  }
}

let account = null;
let accountWorks = [];
let temporaryAccounts = false;

function renderHistory(records) {
  historyList.replaceChildren();
  if (!records.length) {
    historyList.append(textElement("p", "还没有商品记录。录入并保存一件商品后，它就会出现在这里。", "history-empty"));
  }
  for (const record of records) {
    const row = textElement("div", "", "history-row");
    const photo = document.createElement(record.product.photo ? "img" : "span");
    photo.className = "history-photo";
    if (record.product.photo) {
      photo.src = record.product.photo;
      photo.alt = "";
      photo.loading = "lazy";
    }
    const info = document.createElement("div");
    info.append(textElement("strong", record.product.f0), textElement("p",
      [record.product.f1, record.draft ? "已有文案" : "待生成", new Date(record.updated).toLocaleDateString("zh-CN")]
        .filter(Boolean).join(" · "), "history-meta"));
    const open = textElement("button", "打开商品", "text-button");
    open.type = "button";
    open.setAttribute("aria-label", "打开商品 " + record.product.f0);
    open.onclick = () => {
      if (record.workId) {
        sendAction("restore_account_product", {work_id: record.workId});
      } else {
        const {photo, history_id, ...product} = record.product;
        sendAction("restore_product", {product, photo, history_id, draft: record.draft});
      }
    };
    row.append(photo, info, open);
    historyList.append(row);
  }
}

function showHistory(show) {
  document.body.classList.toggle("history-open", show);
  historyPage.hidden = !show;
  if (!show) return;
  document.getElementById("history-title").focus({preventScroll: true});
  const description = document.getElementById("history-description");
  if (account) {
    description.textContent = temporaryAccounts
      ? "这里只显示当前账号的作品。服务更新或重启后，体验版记录可能清空。"
      : "这里只显示当前账号的作品。";
    renderHistory(accountWorks.map(work => ({workId: work.work_id, product: {f0: work.name, f1: work.origin},
      draft: work.has_draft, updated: work.updated * 1000})));
    return;
  }
  description.textContent = "找回已录入的商品，继续生成或编辑文案。访客记录保存在当前浏览器。";
  historyList.textContent = "正在读取商品…";
  openHistoryDatabase().then(db => {
    const request = db.transaction("products").objectStore("products").getAll();
    request.onerror = () => { historyList.textContent = "暂时无法读取商品记录，请重试。"; };
    request.onsuccess = () => {
      if (!account) renderHistory(request.result.sort((a, b) => b.updated - a.updated));
    };
  }).catch(() => { historyList.textContent = "浏览器未开放本地存储，请检查隐私设置后重试。"; });
}
historyEntry.onclick = () => showHistory(true);
document.getElementById("back-to-studio").onclick = () => { showHistory(false); historyEntry.focus(); };
document.querySelector(".nav-links .current").onclick = () => showHistory(false);
document.getElementById("new-history-product").onclick = startNewProduct;

const accountDialog = document.getElementById("account-dialog");
const logoutDialog = document.getElementById("logout-dialog");
const accountEntry = document.getElementById("account-entry");
const accountForm = document.getElementById("account-form");
const accountStatus = document.getElementById("account-status");
const accountSubmit = document.getElementById("account-submit");
const nameInput = accountForm.elements.username;
const passwordInput = accountForm.elements.password;
const captchaInput = accountForm.elements.captcha;
let registering = false;

function accountMode(register) {
  registering = register;
  document.getElementById("account-title").textContent = register ? "注册新用户" : "登录";
  document.getElementById("account-description").textContent = register
    ? "创建账号后，即可保存自己的商品和文案。" : "登录后可查看自己账号下的作品。";
  document.getElementById("account-mode").textContent = register ? "返回登录" : "注册新用户";
  document.getElementById("account-storage-note").hidden = !register || !temporaryAccounts;
  accountSubmit.textContent = register ? "创建账号" : "登录";
  for (const [input, hint, limit] of [[nameInput, "account-name-hint", 32], [passwordInput, "account-password-hint", 128]]) {
    document.getElementById(hint).hidden = !register;
    input.maxLength = register ? 20 : limit;
    if (register) input.setAttribute("aria-describedby", hint);
    else input.removeAttribute("aria-describedby");
    input.removeAttribute("aria-invalid");
  }
  passwordInput.autocomplete = register ? "new-password" : "current-password";
  passwordInput.value = "";
  accountStatus.textContent = "";
}

accountEntry.onclick = () => {
  if (account) {
    document.getElementById("logout-description").textContent =
      "你正在使用账号 " + account.username + "。退出后将返回访客工作台。";
    logoutDialog.returnValue = "";
    logoutDialog.showModal();
  } else {
    accountMode(false);
    accountDialog.showModal();
  }
};
logoutDialog.addEventListener("close", () => {
  if (logoutDialog.returnValue === "logout") sendAction("logout");
});
document.getElementById("close-account").onclick = () => accountDialog.close();
document.getElementById("account-mode").onclick = () => accountMode(!registering);
document.getElementById("refresh-captcha").onclick = () => {
  captchaInput.value = "";
  sendAction("refresh_captcha");
};
accountForm.onsubmit = event => {
  event.preventDefault();
  const username = nameInput.value.trim();
  const password = passwordInput.value;
  nameInput.removeAttribute("aria-invalid");
  passwordInput.removeAttribute("aria-invalid");
  if (registering) {
    const groups = [/[A-Za-z]/, /[0-9]/, /_/].filter(rule => rule.test(username));
    if (!/^[A-Za-z0-9_]{3,20}$/.test(username) || groups.length < 2) {
      accountStatus.textContent = document.getElementById("account-name-hint").textContent;
      nameInput.setAttribute("aria-invalid", "true");
      nameInput.focus();
      return;
    }
    const length = [...password].length;
    if (length < 8 || length > 20 || !/[A-Za-z]/.test(password) || !/[0-9]/.test(password)
        || !/[\p{P}\p{S}]/u.test(password) || /[\s\p{C}]/u.test(password)) {
      accountStatus.textContent = document.getElementById("account-password-hint").textContent;
      passwordInput.setAttribute("aria-invalid", "true");
      passwordInput.focus();
      return;
    }
  }
  accountSubmit.disabled = true;
  sendAction(registering ? "register" : "login", {username, password, captcha: captchaInput.value});
  passwordInput.value = "";
  captchaInput.value = "";
  accountStatus.textContent = "正在提交…";
};

window.addEventListener("message", event => {
  if (event.source !== window.parent || event.data?.type !== "streamlit:render") return;
  const {state, product, items, atlas, draft, captcha} = event.data.args;
  account = event.data.args.account || null;
  accountWorks = event.data.args.account_works || [];
  temporaryAccounts = event.data.args.temporary_accounts;
  accountEntry.textContent = account ? account.username + " · 退出" : "登录";
  accountEntry.title = account ? "退出账号 " + account.username : "登录";
  const captchaImage = document.getElementById("captcha-image");
  if (captcha && captchaImage.getAttribute("src") !== captcha) captchaImage.src = captcha;
  if (!hydrated) {
    hydrated = true;
    if (product) {
      restoreProduct(product);
      const map = document.getElementById("unified-atlas");
      map.innerHTML = atlas || "";
      map.hidden = !atlas;
      for (const sample of Object.values(samples)) {
        sample.title = "";
        sample.body = "";
      }
      for (const item of items || []) {
        const sample = samples[channelKeys[item.channel]];
        if (sample) Object.assign(sample, {title: item.title, body: item.body});
      }
      document.getElementById("b-title").textContent = "";
      document.getElementById("b-copy").textContent = "";
      setBChannel(bChannel);
    }
  }
  if (!state || state.id === applied) return;
  applied = state.id;
  if (state.action === "login" || state.action === "register") {
    accountSubmit.disabled = false;
    if (state.registered) accountMode(false);
    accountStatus.textContent = state.message || "";
    if (state.signedIn) {
      accountDialog.close();
      accountForm.reset();
      if (!historyPage.hidden) showHistory(true);
      showToast(state.message);
    }
    return;
  }
  if (state.action === "logout" && sessionStorage.getItem("studio-last-logout") !== state.id) {
    sessionStorage.setItem("studio-last-logout", state.id);
    location.reload();
    return;
  }
  if (state.action === "generate") finishGeneration(state.message);
  else if (state.message) showToast(state.message);
  if (state.extracted) {
    for (const [key, value] of Object.entries(state.extracted)) form.elements[key].value = value;
  }
  if (state.atlas !== undefined) {
    const atlas = document.getElementById("unified-atlas");
    atlas.innerHTML = state.atlas;
    atlas.hidden = !state.atlas;
  }
  if (state.resetDraft) {
    if (product) restoreProduct(product);
    showHistory(false);
    for (const key of Object.keys(samples)) {
      samples[key].title = "";
      samples[key].body = "";
      delete draftEdits[key];
    }
    document.getElementById("b-title").textContent = "";
    document.getElementById("b-copy").textContent = "";
    document.querySelector(".b-toolbar h1").textContent = state.productName;
    renderFocus(product);
    document.querySelector(".b-source .notice").textContent = state.intro || "商品资料已确认。";
    setBChannel(bChannel);
  }
  if (state.items) {
    for (const item of state.items) {
      const key = channelKeys[item.channel];
      if (!key) continue;
      samples[key].title = item.title;
      samples[key].body = item.body;
      delete draftEdits[key];
    }
    document.getElementById("b-title").textContent = "";
    document.getElementById("b-copy").textContent = "";
    setBChannel(bChannel);
  }
  if (!account && product?.history_id && (state.action === "product" && state.resetDraft ||
      state.action === "generate" && state.items || state.action === "save" && state.saved)) {
    rememberProduct(product, draft);
  }
});
streamlitMessage("streamlit:componentReady", {apiVersion: 1});
const size = () => streamlitMessage("streamlit:setFrameHeight", {height: Math.max(940, document.documentElement.scrollHeight)});
new ResizeObserver(size).observe(document.body);
size();
