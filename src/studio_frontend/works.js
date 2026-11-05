const accountDialog = document.getElementById("account-dialog");
const accountForm = document.getElementById("account-form");
const accountEntry = document.getElementById("account-entry");
const accountStatus = document.getElementById("account-status");
const worksPage = document.getElementById("works-page");
const worksList = document.getElementById("works-list");
let account = null;
let works = [];
let registering = false;
let pendingWorks = false;
let lastAccountResponse;
function accountMode(register) {
  registering = register;
  const title = register ? "新建用户" : "登录";
  document.getElementById("account-title").textContent = title;
  document.getElementById("account-submit").textContent = title;
  document.getElementById("account-mode").textContent = register ? "返回登录" : "注册新用户";
  accountForm.elements.password.autocomplete = register ? "new-password" : "current-password";
  accountStatus.textContent = "";
}
function openLogin() {
  accountMode(false);
  if (!accountDialog.open) accountDialog.showModal();
}
function showWorks(show) {
  document.body.classList.toggle("works-mode", show);
  worksPage.hidden = !show;
  if (!show) { size(); return; }
  worksList.replaceChildren();
  if (!works.length) worksList.textContent = "还没有作品。生成文案后点击「保存到我的作品」。";
  for (const work of works) {
    const row = document.createElement("div");
    row.className = "work-row";
    const info = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = work.name;
    const time = document.createElement("small");
    time.textContent = new Date(work.updated * 1000).toLocaleString("zh-CN");
    info.append(title, time);
    const open = document.createElement("button");
    open.className = "text-button";
    open.textContent = "打开作品";
    open.onclick = () => {
      sendAction("restore", {work_id: work.work_id});
      showWorks(false);
    };
    row.append(info, open);
    worksList.append(row);
  }
  size();
}
accountEntry.onclick = () => {
  if (!account) openLogin();
  else if (confirm("退出当前账号？")) sendAction("logout");
};
document.getElementById("close-account").onclick = () => {pendingWorks = false; accountDialog.close()};
document.getElementById("account-mode").onclick = () => accountMode(!registering);
document.getElementById("refresh-captcha").onclick = () => {
  accountForm.elements.captcha.value = "";
  sendAction("refresh_captcha");
};
accountForm.onsubmit = event => {
  event.preventDefault();
  sendAction(registering ? "register" : "login", Object.fromEntries(new FormData(accountForm)));
  accountForm.elements.password.value = "";
  accountForm.elements.captcha.value = "";
  accountStatus.textContent = "正在提交…";
};
document.getElementById("my-works").onclick = () => {
  if (account) showWorks(true);
  else { pendingWorks = true; openLogin(); }
};
document.getElementById("back-studio").onclick = () => showWorks(false);
document.querySelector(".nav-links .current").onclick = () => showWorks(false);
window.addEventListener("message", event => {
  if (event.source !== parent || event.data?.type !== "streamlit:render") return;
  const args = event.data.args;
  for (const note of document.querySelectorAll(".account-storage-note")) {
    note.hidden = !args.temporary_storage;
  }
  account = args.account;
  works = args.works || [];
  accountEntry.textContent = account ? account.username + " · 退出" : "登录";
  document.getElementById("captcha-image").src = args.captcha || "";
  const state = args.state;
  if (!state?.id || state.id === lastAccountResponse) return;
  lastAccountResponse = state.id;
  if (state.registered) accountMode(false);
  if (["login", "register"].includes(state.action)) accountStatus.textContent = state.message;
  if (state.loginRequired) openLogin();
  if (state.signedIn) {
    accountDialog.close();
    if (pendingWorks) showWorks(true);
    pendingWorks = false;
  }
  if (state.action === "logout") location.reload();
});
