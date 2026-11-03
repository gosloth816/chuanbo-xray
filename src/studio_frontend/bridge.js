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
const applyProductLocally = form.onsubmit;
form.onsubmit = async event => {
  event.preventDefault();
  const file = new FormData(form).get("photo");
  try {
    const photo = await imageData(file);
    if (!productValues().f0) return;
    applyProductLocally(event);
    sendAction("product", {product: productValues(), photo});
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
window.addEventListener("message", event => {
  if (event.source !== window.parent || event.data?.type !== "streamlit:render") return;
  const {state, product, items, atlas} = event.data.args;
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
    leaveDemo();
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
});
streamlitMessage("streamlit:componentReady", {apiVersion: 1});
const size = () => streamlitMessage("streamlit:setFrameHeight", {height: Math.max(940, document.documentElement.scrollHeight)});
new ResizeObserver(size).observe(document.body);
size();
