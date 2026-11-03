const post = (type, data = {}) => parent.postMessage({isStreamlitMessage:true,type,...data},"*");
const action = (name, data = {}) => post("streamlit:setComponentValue", {
 dataType:"json",value:{name,id:crypto.randomUUID(),...data}
});
let state = {rows:[]};
let selected = "";
const byId = id => document.getElementById(id);
function element(tag,text) {
 const node = document.createElement(tag);
 node.textContent = text;
 return node;
}
function button(text,handler) {
 const node = element("button",text);
 node.className = "plain";
 node.onclick = handler;
 return node;
}
function view(key) {
 for (const tab of document.querySelectorAll("[data-view]")) {
  const active = tab.dataset.view === key;
  tab.setAttribute("aria-pressed",String(active));
  byId(tab.dataset.view).hidden = !active;
 }
}
function render() {
 const rows = state.rows;
 byId("case-workspace").hidden = !rows.length;
 byId("case-title").textContent = state.title || "暂无审核任务，请从创作室送审或新建诊断";
 byId("server-status").textContent = state.message || "";
 if (!rows.length) return;
 const row = rows.find(item => item.id === selected) || rows[0];
 selected = row.id;
 const queue = document.querySelector(".queue");
 queue.replaceChildren(element("h2","待核对表述"));
 const checklist = byId("review-list");
 checklist.replaceChildren();
 const select = byId("evidence-claim");
 const selectedClaim = select.value;
 select.replaceChildren();
 for (const item of rows) {
  const open = () => {selected = item.id;view("a");render()};
  const entry = button(item.claim,open);
  entry.append(element("small",item.tag));
  entry.setAttribute("aria-pressed",String(item.id === selected));
  queue.append(entry);
  select.add(new Option(item.claim,item.id));
  const line = element("div","");
  line.className = "check-row";
  line.append(element("strong",item.claim),element("small",summary(item)),button("打开这句",open));
  checklist.append(line);
 }
 select.value = rows.some(item => item.id === selectedClaim) ? selectedClaim : selected;
 for (const field of document.querySelectorAll("[data-field]")) {
  field.textContent = row[field.dataset.field] || "暂无";
 }
 for (const target of [byId("claim-evidence"),byId("evidence-list")]) {
  const claims = target.id === "claim-evidence" ? [row] : rows;
  const files = claims.flatMap(item => item.materials.map(file => ({...file,claim:item.claim})));
  target.replaceChildren(...files.map(file => {
   const block = element("div",file.name);
   block.className = "material";
   block.append(element("small",file.claim+(file.note ? " · "+file.note : "")));
   if (file.excerpt) {
    const detail = element("details", "");
    detail.append(element("summary", "查看材料摘录"), element("p", file.excerpt));
    block.append(detail);
   }
   return block;
  }));
  if (!files.length) target.append(element("p","暂无关联材料"));
 }
 document.querySelector(".review").textContent = row.checked ? "撤回复核标记" : "标记已复核";
 document.querySelector(".status").textContent = "已复核 "+rows.filter(item=>item.checked).length+" / "+rows.length+" 条";
}
function summary(row) {
 return (row.checked?"已复核":"待复核")+" · "+(row.materials.length ? row.materials.length+" 份关联材料" : "暂无关联材料");
}
document.querySelectorAll("[data-view]").forEach(tab => tab.onclick = () => view(tab.dataset.view));
byId("return-studio").onclick = () => action("return");
byId("new-review").onclick = () => action("advanced");
document.querySelector(".review").onclick = () => action("toggle",{claim:selected});
byId("add-evidence").onclick = () => {byId("evidence-claim").value=selected;view("b");byId("evidence-file").focus()};
byId("evidence-form").onsubmit = event => {
 event.preventDefault();
 const file = byId("evidence-file").files[0];
 if (!file) return;
 if (file.size > 10*1024*1024) {
  byId("upload-status").textContent = "请选择 10 MB 以内的文件。";
  return;
 }
 const reader = new FileReader();
 const claim = byId("evidence-claim").value;
 const note = byId("evidence-note").value.trim();
 reader.onerror = () => byId("upload-status").textContent = "文件读取失败。";
 reader.onload = () => {
  action("upload",{claim,fileName:file.name,note,data:reader.result});
  byId("upload-status").textContent = "正在读取材料…";
 };
 reader.readAsDataURL(file);
};
byId("export-review").onclick = () => {
 const lines = [state.title,...state.rows.flatMap(row => [row.claim,summary(row),...row.materials.map(file=>file.name),""])];
 const url = URL.createObjectURL(new Blob([lines.join("\n")],{type:"text/plain;charset=utf-8"}));
 const link = element("a","");
 link.href=url;
 link.download="传播X光复核清单.txt";
 link.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
};
let applied = "";
window.addEventListener("message",event => {
 if(event.source!==parent || event.data?.type!=="streamlit:render") return;
 const next=event.data.args.state;
 if(!next || next.revision===applied) return;
 applied=next.revision;
 state=next;
 byId("upload-status").textContent="";
 if(state.uploaded) byId("evidence-form").reset();
 render();
});
post("streamlit:componentReady",{apiVersion:1});
new ResizeObserver(()=>post("streamlit:setFrameHeight",{height:Math.max(820,document.documentElement.scrollHeight)})).observe(document.body);
