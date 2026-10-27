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
const DRAFT_KEY = "renn-prod-shooting-demo-v1";
function showStatus(key) {status.dataset.key=key;status.textContent=translate(key);}
form.addEventListener("submit", event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({version:1,service:service.value,idea:document.querySelector("#idea").value.trim(),locale}));
    showStatus("draftSaved");
  } catch {showStatus("draftError");}
});
document.querySelector("#restore-draft").addEventListener("click",()=>{
  try {
    const raw=localStorage.getItem(DRAFT_KEY);
    if (!raw) {showStatus("draftMissing");return;}
    const draft=JSON.parse(raw);
    if (draft.version!==1 || !["professional","reels","commercial","art","editing","graphics","ai"].includes(draft.service) || typeof draft.idea!=="string" || draft.idea.length>1200) throw new Error("Invalid draft");
    service.value=draft.service;
    document.querySelector("#idea").value=draft.idea;
    showStatus("draftRestored");
  } catch {showStatus("draftError");}
});
document.querySelector("#clear-draft").addEventListener("click",()=>{
  try {localStorage.removeItem(DRAFT_KEY);form.reset();showStatus("draftCleared");}
  catch {showStatus("draftError");}
});
applyLocale("ru");

// Preserve the selected language when navigating service pages.
document.querySelectorAll("[data-locale]").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll('a[href$=".html"],a[href*=".html?lang="]').forEach(a=>{const url=new URL(a.href);url.searchParams.set("lang",locale);a.href=url.href;});}));
const pageLanguage=new URLSearchParams(location.search).get("lang");
if (["ru","en"].includes(pageLanguage)) {applyLocale(pageLanguage);document.querySelectorAll('a[href$=".html"]').forEach(a=>{const url=new URL(a.href);url.searchParams.set("lang",pageLanguage);a.href=url.href;});}
