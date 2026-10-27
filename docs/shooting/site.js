"use strict";
// Passive pointer events preserve native touch scrolling. No permission or motion sensor needed.
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
function followPointer(event) {
  if (reducedMotion.matches) return;
  const camera = document.querySelector(".camera-art");
  if (!camera) return;
  const bounds = camera.getBoundingClientRect();
  const clamp = value => Math.max(-1, Math.min(1, value));
  const x = clamp((event.clientX - bounds.left - bounds.width/2) / (bounds.width/2));
  const y = clamp((event.clientY - bounds.top - bounds.height/2) / (bounds.height/2));
  camera.style.setProperty("--eye-x", `${x*10}px`);
  camera.style.setProperty("--eye-y", `${y*7}px`);
  camera.style.setProperty("--camera-x", `${x*4}px`);
  camera.style.setProperty("--camera-y", `${y*4}px`);
}
document.addEventListener("pointermove", followPointer, {passive:true});
document.addEventListener("pointerdown", followPointer, {passive:true});
const mediaDialog = document.querySelector("#media-dialog");
const manifest = window.RP_MEDIA || {work:[],backstage:[]};
let mediaOpener;
function allowedSource(value, embed = false) {
  if (typeof value !== "string" || !value) return null;
  try {
    const url = new URL(value, location.href);
    if (!["https:","http:"].includes(url.protocol)) return null;
    if (url.origin !== location.origin && url.protocol !== "https:") return null;
    if (embed && !["www.youtube.com","www.youtube-nocookie.com","rutube.ru","player.vimeo.com"].includes(url.hostname)) return null;
    return url.href;
  } catch { return null; }
}
function openMedia(item, button) {
  mediaOpener=button;
  const stage=document.querySelector("#media-stage");
  const state=document.querySelector("#media-state");
  stage.replaceChildren();
  document.querySelector("#media-title").textContent=item.title[locale] || item.title.ru;
  const source=allowedSource(item.src,item.type==="embed");
  state.textContent=source ? "" : translate("mediaEmpty");
  if (source) {
    const element=document.createElement(item.type==="image"?"img":item.type==="embed"?"iframe":"video");
    if (element.tagName==="VIDEO") {element.controls=true;element.playsInline=true;element.preload="none";const poster=allowedSource(item.poster);if(poster) element.poster=poster;}
    if (element.tagName==="IMG") element.alt=item.title[locale] || item.title.ru;
    if (element.tagName==="IFRAME") {element.title=item.title[locale] || item.title.ru;element.allowFullscreen=true;element.referrerPolicy="no-referrer";element.allow="fullscreen; picture-in-picture";}
    element.src=source;
    element.addEventListener("error",()=>{state.textContent=translate("mediaEmpty");});
    stage.append(element);
  }
  mediaDialog.showModal();
}
function renderMedia() {
  if (!mediaDialog) return;
  for (const [key,id] of [["work","work-rail"],["backstage","backstage-grid"]]) {
    const rail=document.getElementById(id);
    rail.replaceChildren();
    for (const item of manifest[key]) {
      const button=document.createElement("button");
      button.className="media-tile";button.type="button";
      const poster=allowedSource(item.poster || (item.type==="image"?item.src:null));
      if (poster) {const img=document.createElement("img");img.src=poster;img.alt="";img.loading="lazy";button.append(img);}
      const title=document.createElement("strong");title.textContent=item.title[locale] || item.title.ru;
      const note=document.createElement("span");note.textContent=item.src ? "↗" : translate("mediaSoon");
      button.append(title,note);button.addEventListener("click",()=>openMedia(item,button));rail.append(button);
    }
  }
}
if (mediaDialog) {
  document.querySelector("#close-media").addEventListener("click",()=>mediaDialog.close());
  mediaDialog.addEventListener("close",()=>{document.querySelector("#media-stage").replaceChildren();mediaOpener?.focus();});
  document.querySelectorAll("[data-slide]").forEach(button=>button.addEventListener("click",()=>{const rail=document.querySelector("#work-rail");rail.scrollBy({left:Number(button.dataset.slide)*rail.clientWidth*.8,behavior:reducedMotion.matches?"instant":"smooth"});}));
  document.addEventListener("rp:locale",renderMedia);
  renderMedia();
}
