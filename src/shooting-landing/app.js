"use strict";
const dialog = document.querySelector("#brief-dialog");
const form = document.querySelector("#brief-form");
const service = document.querySelector("#service");
const status = document.querySelector("#form-status");
const textBindings = [];
const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
while (walker.nextNode()) {
  const node = walker.currentNode;
  if (/\{\{[A-Za-z0-9_]+\}\}/.test(node.nodeValue)) textBindings.push({node, template: node.nodeValue});
}
const attributeBindings = [];
document.querySelectorAll("*").forEach(node => {
  [...node.attributes].forEach(attr => {
    if (/\{\{[A-Za-z0-9_]+\}\}/.test(attr.value)) attributeBindings.push({node, name:attr.name, template:attr.value});
  });
});
let locale = "ru";
function translate(key) { return window.RP_LOCALES[locale][key] ?? window.RP_LOCALES.ru[key] ?? key; }
function applyLocale(nextLocale) {
  if (!window.RP_LOCALES[nextLocale]) return;
  locale = nextLocale;
  const render = template => template.replace(/\{\{([A-Za-z0-9_]+)\}\}/g, (_, key) => translate(key));
  textBindings.forEach(binding => {binding.node.nodeValue = render(binding.template);});
  attributeBindings.forEach(binding => binding.node.setAttribute(binding.name,render(binding.template)));
  document.documentElement.lang = locale;
  document.title = (document.querySelector("h1")?.textContent.trim().replace(/\s+/g," ") || "RENN Prod") + " — RENN Prod";
  if(document.querySelector("[data-nav-copy=team]")) document.querySelector("[data-nav-copy=team]").textContent = translate("navTeam");
  document.querySelectorAll("[data-locale]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.locale === locale)));
  document.dispatchEvent(new CustomEvent("rp:locale", {detail:locale}));
  if (status.dataset.key) status.textContent = translate(status.dataset.key) + (status.dataset.id || "");
}
document.querySelectorAll("[data-locale]").forEach(button => button.addEventListener("click", () => applyLocale(button.dataset.locale)));

let opener;
document.querySelectorAll("[data-service]").forEach(button => {
  button.addEventListener("click", () => {
    opener = button;
    form.reset();
    status.textContent = "";
    delete status.dataset.key;
    delete status.dataset.id;
    service.value = button.dataset.service;
    dialog.showModal();
    (service.value ? document.querySelector("#idea") : service).focus();
  });
});
document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", event => {
  if (event.target !== dialog) return;
  const bounds = dialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
});
dialog.addEventListener("close", () => {
  form.reset();
  status.textContent = "";
    delete status.dataset.key;
    delete status.dataset.id;
  opener?.focus();
});
let submitting = false;
function showStatus(key, id = "") {
  status.dataset.key = key;
  status.dataset.id = id;
  status.textContent = translate(key) + id;
}
form.addEventListener("submit", async event => {
  event.preventDefault();
  if (submitting || !form.reportValidity()) return;
  const token = document.querySelector('meta[name="rp-local-session"]')?.content;
  if (location.origin !== "http://127.0.0.1:8766" || !location.pathname.startsWith("/shooting") || !token || token === "__SESSION__") {
    showStatus("offline");
    const draft = new URLSearchParams({service:service.value,idea:document.querySelector("#idea").value,lang:locale});
    const link = document.createElement("a");
    link.href = "http://127.0.0.1:8766/shooting/#brief=" + encodeURIComponent(draft.toString());
    link.textContent = locale === "en" ? " Open working form with this text →" : " Открыть рабочую форму с этим текстом →";
    link.style.textDecoration = "underline";
    status.append(link);
    return;
  }
  const submit = form.querySelector('[type="submit"]');
  submitting = true;
  submit.disabled = true;
  showStatus("sending");
  const idea = document.querySelector("#idea").value.trim();
  try {
    const response = await fetch("/api/intake", {
      method: "POST",
      headers: {"Content-Type":"application/json", "X-Local-Session":token},
      credentials: "same-origin",
      signal: AbortSignal.timeout(10000),
      body: JSON.stringify({kind:"client",source:"shooting-landing",service:service.value,locale,idea,test:/\b(?:TEST|DEMO)\b/i.test(idea)})
    });
    if (!response.ok) throw new Error("Rejected");
    const result = await response.json();
    if (result.status !== "saved" || typeof result.id !== "string" || !result.id) {
      showStatus("invalidResponse");
      return;
    }
    showStatus("saved", result.id);
    document.querySelector("#idea").value = "";
  } catch {
    showStatus("failure");
  } finally {
    submitting = false;
    submit.disabled = false;
  }
});
applyLocale("ru");

// Recover a form opened from a standalone preview, without sending the draft in HTTP URLs.
if (location.origin === "http://127.0.0.1:8766" && location.hash.startsWith("#brief=")) {
  try {
    const draft = new URLSearchParams(decodeURIComponent(location.hash.slice(7)));
    applyLocale(draft.get("lang") || "ru");
    service.value = draft.get("service") || "";
    document.querySelector("#idea").value = draft.get("idea") || "";
    history.replaceState(null,"",location.pathname + location.search);
    dialog.showModal();
    document.querySelector("#idea").focus();
  } catch { showStatus("offline"); }
}

// Preserve the selected language when navigating service pages.
document.querySelectorAll("[data-locale]").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll('a[href$=".html"],a[href*=".html?lang="]').forEach(a=>{const url=new URL(a.href);url.searchParams.set("lang",locale);a.href=url.href;});}));
const pageLanguage=new URLSearchParams(location.search).get("lang");
if (["ru","en"].includes(pageLanguage)) {applyLocale(pageLanguage);document.querySelectorAll('a[href$=".html"]').forEach(a=>{const url=new URL(a.href);url.searchParams.set("lang",pageLanguage);a.href=url.href;});}
