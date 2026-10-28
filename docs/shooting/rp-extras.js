"use strict";
// RENN Prod: contacts, lead form (contact required), meta per locale, scroll reveal.
// Loaded after locales.js and BEFORE app.js so injected {{keys}} are translated by app.js.
(function () {
  // CONFIG: confirm before publishing. Telegram handle and email are shown publicly.
  const RP_CONTACT = {
    telegram: "misharenne",
    email: "mstmisha08@gmail.com",
    briefUrl: "../team/?view=brief",
    leadEndpoint: "" // optional HTTPS endpoint that accepts JSON; empty = hand-off via Telegram/email
  };
  window.RP_CONTACT = RP_CONTACT;

  const add = (ru, en) => {
    Object.assign(window.RP_LOCALES.ru, ru);
    Object.assign(window.RP_LOCALES.en, en);
  };
  add({
    ctaHeader: "Обсудить проект", ctaHero: "Обсудить проект", ctaServices: "Смотреть услуги",
    contactField: "Ваш контакт: Telegram или email", contactPlaceholder: "@username или name@example.com",
    contactHint: "Укажите Telegram или email: так мы сможем вам ответить.",
    contactNeed: "Укажите Telegram или email.",
    briefLink: "Подробный бриф →",
    leadReady: "Заявка подготовлена, но ещё не отправлена. Нажмите кнопку ниже, чтобы она дошла до нас.",
    leadSent: "Заявка отправлена. Мы ответим по указанному контакту.",
    leadError: "Не удалось отправить. Напишите нам в Telegram или на почту.",
    sendTelegram: "Отправить в Telegram", sendEmail: "Написать на почту",
    metaDesc: "RENN Prod — независимый продакшн: съёмка, Reels, реклама, клипы и художественные проекты. Команда под задачу в России и СНГ.",
    ogTitle: "ВАША ИДЕЯ. НАШ КАДР. — RENN Prod",
    contactsLabel: "Контакты",
    copy140: "Подготовить заявку →",
    copy134: "Опишите задачу и оставьте контакт: заявка уйдёт после нажатия кнопки отправки ниже."
  }, {
    ctaHeader: "Discuss a project", ctaHero: "Discuss a project", ctaServices: "See services",
    contactField: "Your contact: Telegram or email", contactPlaceholder: "@username or name@example.com",
    contactHint: "Leave a Telegram handle or an email so we can reply.",
    contactNeed: "Enter a Telegram handle or an email.",
    briefLink: "Full brief →",
    leadReady: "Your request is prepared but not sent yet. Use a button below so it reaches us.",
    leadSent: "Request sent. We will reply using the contact you left.",
    leadError: "Could not send. Please message us on Telegram or by email.",
    sendTelegram: "Send via Telegram", sendEmail: "Send by email",
    metaDesc: "RENN Prod is an independent production company: filming, Reels, commercials, music videos and art projects. A team built for each task in Russia and the CIS.",
    ogTitle: "YOUR IDEA. OUR FRAME. — RENN Prod",
    contactsLabel: "Contacts",
    copy140: "Prepare request →",
    copy134: "Describe your task and leave a contact: the request is sent when you press a send button below."
  });

  // Contact fields + hand-off buttons injected into every brief form (all service pages).
  const form = document.querySelector("#brief-form");
  if (form) {
    const submit = form.querySelector('button[type="submit"]');
    const wrap = document.createElement("div");
    wrap.className = "contact-fields";
    wrap.innerHTML =
      '<label for="lead-contact">{{contactField}}</label><input id="lead-contact" name="contact" autocomplete="email" maxlength="160" required placeholder="{{contactPlaceholder}}">' +
      '<p class="form-note contact-hint">{{contactHint}}</p>' +
      '<a class="brief-link" href="' + RP_CONTACT.briefUrl + '">{{briefLink}}</a>';
    form.insertBefore(wrap, submit);
    const actions = document.createElement("div");
    actions.className = "lead-actions";
    actions.hidden = true;
    actions.innerHTML = '<a class="button" id="lead-telegram-link" target="_blank" rel="noopener">{{sendTelegram}}</a>' +
      '<a class="button" id="lead-email-link">{{sendEmail}}</a>';
    form.appendChild(actions);

    // One field: an address with "@" and a dot is an email, anything else is a Telegram handle.
    const parseContact = raw => {
      const v = raw.trim();
      if (!v) return { telegram: "", email: "" };
      if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return { telegram: "", email: v };
      const tg = v.replace(/^(https?:\/\/)?t\.me\//i, "").replace(/^@+/, "");
      return /^[A-Za-z0-9_]{4,32}$/.test(tg) ? { telegram: tg, email: "" } : { telegram: "", email: "", invalid: true };
    };
    const val = id => form.querySelector(id).value.trim();
    const serviceLabel = () => { const s = form.querySelector("#service"); return s.selectedOptions[0]?.textContent || s.value; };
    const buildText = () => {
      const c = parseContact(val("#lead-contact"));
      const lines = ["RENN Prod: " + serviceLabel(), form.querySelector("#idea").value.trim(),
        "", "Telegram: " + (c.telegram || "—"), "Email: " + (c.email || "—")];
      return lines.join("\n");
    };
    const t = key => (window.RP_LOCALES[document.documentElement.lang] || window.RP_LOCALES.ru)[key] || window.RP_LOCALES.ru[key];
    const setStatus = (key, kind) => {
      const st = document.querySelector("#form-status");
      st.dataset.key = key; st.textContent = t(key); st.dataset.kind = kind || "";
    };
    form.addEventListener("submit", async event => {
      event.preventDefault();
      event.stopImmediatePropagation(); // replaces the draft-only handler in app.js
      if (!form.reportValidity()) return;
      const c = parseContact(val("#lead-contact"));
      const tg = c.telegram, mail = c.email;
      if (!tg && !mail) {
        setStatus("contactNeed", "error");
        form.querySelector("#lead-contact").focus();
        return;
      }
      const lead = { service: form.querySelector("#service").value, idea: val("#idea"), telegram: tg, email: mail, locale: document.documentElement.lang, page: location.pathname, at: new Date().toISOString() };
      if (RP_CONTACT.leadEndpoint) {
        try {
          const res = await fetch(RP_CONTACT.leadEndpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(lead) });
          const body = await res.json().catch(() => null);
          if (!res.ok || !body || body.ok !== true) throw new Error("not confirmed");
          setStatus("leadSent", "ok"); actions.hidden = true; return;
        } catch { setStatus("leadError", "error"); }
      } else { setStatus("leadReady", "info"); }
      const text = buildText();
      form.querySelector("#lead-telegram-link").href = "https://t.me/" + RP_CONTACT.telegram + "?text=" + encodeURIComponent(text);
      form.querySelector("#lead-email-link").href = "mailto:" + RP_CONTACT.email + "?subject=" + encodeURIComponent("RENN Prod: " + serviceLabel()) + "&body=" + encodeURIComponent(text);
      actions.hidden = false;
    }, true);
  }

  // Keep meta description / Open Graph in sync with the selected language.
  document.addEventListener("rp:locale", event => {
    const L = window.RP_LOCALES[event.detail] || window.RP_LOCALES.ru;
    const set = (sel, val) => { const el = document.querySelector(sel); if (el && val) el.setAttribute("content", val); };
    set('meta[name="description"]', L.metaDesc); set('meta[property="og:description"]', L.metaDesc);
    if (document.querySelector("#brief-form") && document.querySelector('meta[property="og:title"]') && document.body.dataset.home === "1") set('meta[property="og:title"]', L.ogTitle);
  });

  // Hide "Backstage" until real material exists (no placeholders in front of clients).
  document.addEventListener("DOMContentLoaded", () => {
    const m = window.RP_MEDIA;
    const grid = document.querySelector("#backstage-grid");
    if (grid && m && Array.isArray(m.backstage) && !m.backstage.some(i => i && i.src)) {
      const section = grid.closest(".media-section");
      if (section) { section.hidden = true; section.setAttribute("data-empty-backstage", ""); }
    }
  });

  // Scroll reveal: only if JS runs and motion is allowed, so content is never hidden otherwise.
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  if (!reduce.matches && "IntersectionObserver" in window) {
    document.documentElement.classList.add("rp-reveal");
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in-view"); io.unobserve(e.target); } });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    // Failsafe: never leave content hidden if the observer does not fire.
    setTimeout(() => document.querySelectorAll(".reveal:not(.in-view)").forEach(el => el.classList.add("in-view")), 4000);
    document.addEventListener("DOMContentLoaded", () => {
      document.querySelectorAll(".service-card, .media-section, .clients, .final-cta, .promise").forEach((el, i) => {
        el.classList.add("reveal"); el.style.setProperty("--reveal-delay", (i % 4) * 70 + "ms"); io.observe(el);
      });
    });
  }
})();
