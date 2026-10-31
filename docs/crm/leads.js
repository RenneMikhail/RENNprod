"use strict";
// Воронка лидов для CRM RENN Prod. Самодостаточный модуль: подключается после lead-score.js,
// app.js и dashboard.js не трогает. Данные только демонстрационные, лежат в localStorage.
// Чистые функции экспортируются в window.RPLeads и module.exports (для тестов).
(function (root) {
  const STORAGE_KEY = "renn-crm-leads-demo-v1";
  const BACKUP_KEY = STORAGE_KEY + "-unreadable-backup";
  const STAGES = [
    { id: "new", label: "Новая" },
    { id: "contacted", label: "Связались" },
    { id: "brief", label: "Бриф получен" },
    { id: "estimate", label: "Смета отправлена" },
    { id: "approved", label: "Согласовано" },
    { id: "lost", label: "Проиграно" }
  ];
  const SOURCES = [
    { id: "site", label: "Сайт" },
    { id: "telegram", label: "Telegram" },
    { id: "referral", label: "Рекомендация" },
    { id: "social", label: "Соцсети" },
    { id: "other", label: "Другое" }
  ];
  const URGENCIES = [
    { id: "asap", label: "Срочно (до 7 дней)" },
    { id: "soon", label: "Скоро (до 3 недель)" },
    { id: "month", label: "1–2 месяца" },
    { id: "later", label: "Не срочно" }
  ];
  const SERVICES = [
    { id: "professional", label: "Профессиональная съёмка" },
    { id: "commercial", label: "Коммерческая съёмка" },
    { id: "art", label: "Арт-проект" },
    { id: "reels", label: "Reels" },
    { id: "editing", label: "Монтаж" },
    { id: "graphics", label: "Графика" },
    { id: "ai", label: "AI-видео" }
  ];
  const TIERS = { hot: "Горячий", warm: "Тёплый", cold: "Холодный" };
  // Закрытая стадия — только «Проиграно». «Согласовано» не закрыта: после согласования остаются шаги (договор, старт),
  // и их просрочка должна отмечаться.
  const CLOSED = ["lost"];
  // storedChars — предел размера строки из localStorage до JSON.parse. Он не задан числом «на глаз», а вычисляется
  // worstCaseStoredChars(): берётся лид с полями максимальной длины, где каждый символ — самый дорогой из допустимых
  // (кавычка, JSON-экранирование удваивает его; управляющие символы и одиночные суррогаты валидацией запрещены),
  // сериализуется настоящим JSON.stringify и умножается на LIMITS.leads (плюс запятые и скобки массива). Поэтому
  // валидный набор из LIMITS.leads лидов всегда укладывается в предел и модуль не создаёт данные, которые не сможет прочитать.
  // save() дополнительно не пишет строку длиннее предела (сообщая об этом) — защитная проверка на случай нарушения контракта.
  const LIMITS = { title: 120, contact: 120, nextStep: 200, comment: 1000, lostReason: 200, budget: 1e9, leads: 500, storedChars: 0 };
  function worstCaseStoredChars() {
    const q = (n) => '"'.repeat(n);
    const lead = {
      id: "a".repeat(64), title: q(LIMITS.title), contact: q(LIMITS.contact), service: "professional", source: "referral",
      budget: LIMITS.budget, urgency: "month", nextStep: q(LIMITS.nextStep), nextStepDate: "9999-12-31", comment: q(LIMITS.comment),
      stage: "estimate", lostReason: q(LIMITS.lostReason), demo: true, createdAt: "9999-12-31", updatedAt: "9999-12-31"
    };
    return JSON.stringify(lead).length * LIMITS.leads + (LIMITS.leads - 1) + 2;
  }
  LIMITS.storedChars = worstCaseStoredChars();
  const ids = (list) => list.map((x) => x.id);
  const labelOf = (list, id) => (list.find((x) => x.id === id) || { label: "—" }).label;
  const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  const ID_RE = /^[A-Za-z0-9_-]{1,64}$/;
  // Одиночные суррогаты JSON.stringify записывает как \uXXXX (6 символов), что ломало бы оценку размера записи, — их отклоняем.
  const LONE = "|[\\uD800-\\uDBFF](?![\\uDC00-\\uDFFF])|(?<![\\uD800-\\uDBFF])[\\uDC00-\\uDFFF]";
  const CTRL_RE = new RegExp("[\\u0000-\\u001F\\u007F]" + LONE);
  const CTRL_ML_RE = new RegExp("[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F\\u007F]" + LONE);
  // Консервативный формат email: локальная часть из ASCII-символов без точки в начале/конце и без «..»,
  // домен из меток через точку, последняя метка — буквы (≥2). Существование адреса не проверяется.
  const EMAIL_RE = /^[A-Za-z0-9_%+-]+(\.[A-Za-z0-9_%+-]+)*@[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$/;

  // ---------- чистые функции ----------
  function pad(n) { return String(n).padStart(2, "0"); }
  function dateStr(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function addDays(now, n) { const d = new Date(now.getTime()); d.setDate(d.getDate() + n); return dateStr(d); }
  // Допустимые контакты: email, Telegram @имя (5–32 символа после @ (правило Telegram)) или ссылка t.me/имя.
  // Имя без @ и без t.me не принимается — поле честно обещает «Telegram, телефон или email».
  function validContact(raw) {
    if (typeof raw !== "string" || CTRL_RE.test(raw)) return false;
    const v = raw.trim();
    if (v.length > LIMITS.contact) return false;
    if (EMAIL_RE.test(v)) return true;
    if (/^\+?[0-9][0-9 () .-]*$/.test(v) && v.replace(/\D/g, "").length >= 7 && v.replace(/\D/g, "").length <= 15) return true;
    return /^@[A-Za-z0-9_]{5,32}$/.test(v) || /^(https?:\/\/)?t\.me\/[A-Za-z0-9_]{5,32}\/?$/i.test(v);
  }
  function validDate(s) {
    if (typeof s !== "string" || !DATE_RE.test(s)) return false;
    const d = new Date(s + "T00:00:00");
    return !Number.isNaN(d.getTime()) && dateStr(d) === s;
  }
  // Идентификатор: время + случайная часть (crypto, если есть). Счётчик в памяти вкладки не используется,
  // поэтому параллельные вкладки не порождают одинаковых id; taken — уже занятые id (массив или Set).
  function randomPart() {
    const c = root.crypto;
    if (c && typeof c.getRandomValues === "function") {
      const a = new Uint32Array(2);
      c.getRandomValues(a);
      return a[0].toString(36) + a[1].toString(36);
    }
    return Math.random().toString(36).slice(2, 12);
  }
  function newId(now, taken) {
    const has = (id) => (taken ? (taken.has ? taken.has(id) : taken.includes(id)) : false);
    // Число попыток ограничено: при исчерпанном генераторе (или подставленных в тестах now/randomPart) — контролируемая ошибка.
    for (let i = 0; i < 50; i += 1) {
      const id = "lead-" + now.getTime().toString(36) + "-" + randomPart();
      if (!has(id)) return id;
    }
    throw new Error("RPLeads: не удалось подобрать уникальный идентификатор лида.");
  }
  const present = (v) => v != null && v !== "";
  // Нормализация только обрезает пробелы: значения не усекаются и не «чинятся» — проверку делает validateLead.
  // Нестроковые значения сохраняются как есть, чтобы валидация их отклонила.
  const norm = (v) => (v == null ? "" : typeof v === "string" ? v.trim() : v);

  function createLead(input, opts) {
    const o = opts || {};
    const now = o.now instanceof Date ? o.now : new Date();
    const src = input || {};
    let budget = null;
    if (present(src.budget)) {
      budget = typeof src.budget === "string" ? (src.budget.trim() ? Number(src.budget) : null) : src.budget;
    }
    const wantedId = present(src.id) ? src.id : o.id;
    return {
      id: present(wantedId) ? wantedId : newId(now, o.taken),
      title: norm(src.title),
      contact: norm(src.contact),
      service: present(src.service) ? src.service : "professional",
      source: present(src.source) ? src.source : "site",
      budget,
      urgency: present(src.urgency) ? src.urgency : "later",
      nextStep: norm(src.nextStep),
      nextStepDate: norm(src.nextStepDate),
      comment: norm(src.comment),
      stage: present(src.stage) ? src.stage : "new",
      lostReason: norm(src.lostReason),
      demo: src.demo === true,
      createdAt: present(src.createdAt) ? src.createdAt : dateStr(now),
      updatedAt: present(src.updatedAt) ? src.updatedAt : dateStr(now)
    };
  }

  // Единое место правил: используется и интерфейсом, и прямыми вызовами API. opts.others — остальные лиды
  // (для проверки уникальности id; при редактировании сам лид в них не входит);
  // opts.ids — Set занятых id (быстрая замена others при массовой проверке).
  function validateLead(lead, opts) {
    const errors = {};
    const l = lead || {};
    const others = (opts && opts.others) || [];
    const val = (k) => (l[k] == null ? "" : l[k]);
    // Проверка текстового поля: тип, длина (до обрезки пробелов уже выполнена), управляющие символы.
    const textErr = (k, max, multiline) => {
      const v = val(k);
      if (typeof v !== "string") return "Недопустимое значение.";
      if (v.trim().length > max) return "Не длиннее " + max + " символов.";
      if ((multiline ? CTRL_ML_RE : CTRL_RE).test(v)) return "Недопустимые управляющие символы.";
      return "";
    };
    const title = val("title");
    if (typeof title !== "string" || !title.trim()) errors.title = "Укажите название или клиента.";
    else if (textErr("title", LIMITS.title)) errors.title = textErr("title", LIMITS.title);
    const contact = val("contact");
    if (typeof contact !== "string" || !contact.trim()) errors.contact = "Укажите контакт: Telegram, телефон или email.";
    else if (contact.trim().length > LIMITS.contact) errors.contact = "Контакт не длиннее " + LIMITS.contact + " символов.";
    else if (CTRL_RE.test(contact)) errors.contact = "Контакт содержит недопустимые управляющие символы.";
    else if (!validContact(contact)) errors.contact = "Контакт не распознан: нужен Telegram (@имя или t.me/имя), телефон или email.";
    if (!ids(SERVICES).includes(l.service)) errors.service = "Выберите услугу.";
    if (!ids(SOURCES).includes(l.source)) errors.source = "Выберите источник.";
    if (!ids(URGENCIES).includes(l.urgency)) errors.urgency = "Выберите срочность.";
    if (!ids(STAGES).includes(l.stage)) errors.stage = "Выберите стадию.";
    if (l.budget != null && l.budget !== "") {
      const b = typeof l.budget === "string" ? Number(l.budget) : l.budget;
      if (!(typeof b === "number" && Number.isInteger(b) && b >= 0 && b <= LIMITS.budget)) errors.budget = "Бюджет — целое число рублей от 0 до 1 000 000 000.";
    }
    const step = val("nextStep");
    const stepErr = textErr("nextStep", LIMITS.nextStep);
    if (stepErr) errors.nextStep = stepErr;
    if (present(l.nextStepDate)) {
      if (!validDate(l.nextStepDate)) errors.nextStepDate = "Дата в формате ГГГГ-ММ-ДД.";
      else if (!errors.nextStep && !String(step).trim()) errors.nextStep = "Опишите следующий шаг для этой даты.";
    }
    const commentErr = textErr("comment", LIMITS.comment, true);
    if (commentErr) errors.comment = commentErr;
    const reasonErr = textErr("lostReason", LIMITS.lostReason);
    if (reasonErr) errors.lostReason = reasonErr;
    else if (l.stage === "lost" && !String(val("lostReason")).trim()) errors.lostReason = "Для стадии «Проиграно» нужна причина.";
    if (present(l.id)) {
      if (typeof l.id !== "string" || !ID_RE.test(l.id)) errors.id = "Недопустимый идентификатор лида.";
      else if (opts && opts.ids ? opts.ids.has(l.id) : others.some((o) => o && o.id === l.id)) errors.id = "Лид с таким идентификатором уже существует.";
    }
    if (present(l.createdAt) && !validDate(l.createdAt)) errors.createdAt = "Недопустимая дата создания.";
    if (present(l.updatedAt) && !validDate(l.updatedAt)) errors.updatedAt = "Недопустимая дата изменения.";
    return { valid: Object.keys(errors).length === 0, errors };
  }

  // Контракт: итоговый лид целиком проходит validateLead (id, поля, стадия, причина); невалидный вход даёт ok:false,
  // а не «успех» над некорректным объектом. Остальные правила «Проиграно»: явно переданная opts.reason заменяет прежнюю причину (повторный вызов для уже проигранного
  // лида её обновляет); без opts.reason сохраняется прежняя, но только допустимая. При уходе из «Проиграно» причина очищается,
  // поэтому прежняя причина бывает только у лида, который уже в «Проиграно». Интерфейс в этом случае не меняет стадию.
  function changeStage(lead, stage, opts) {
    const o = opts || {};
    const now = o.now instanceof Date ? o.now : new Date();
    if (!lead || typeof lead !== "object" || Array.isArray(lead)) return { ok: false, error: "Не передан лид.", lead: null };
    if (!ids(STAGES).includes(stage)) return { ok: false, error: "Неизвестная стадия.", lead };
    let reason = "";
    if (stage === "lost") {
      if (o.reason != null && typeof o.reason !== "string") return { ok: false, error: "Причина должна быть строкой.", lead };
      // Управляющие символы проверяются по исходной строке (до trim), как в validateLead: trim не должен скрывать их по краям.
      const rawGiven = o.reason == null ? "" : o.reason;
      if (CTRL_RE.test(rawGiven)) return { ok: false, error: "Причина содержит недопустимые управляющие символы.", lead };
      const given = rawGiven.trim();
      if (given.length > LIMITS.lostReason) return { ok: false, error: "Причина не длиннее " + LIMITS.lostReason + " символов.", lead };
      const rawKept = typeof lead.lostReason === "string" ? lead.lostReason : "";
      const kept = rawKept.trim();
      reason = given || (kept.length <= LIMITS.lostReason && !CTRL_RE.test(rawKept) ? kept : "");
      if (!reason) return { ok: false, error: "Для стадии «Проиграно» нужна причина.", lead };
    }
    const next = Object.assign({}, lead, { stage, lostReason: reason, updatedAt: dateStr(now) });
    const v = validateLead(next);
    if (!v.valid) {
      const first = v.errors[Object.keys(v.errors)[0]];
      return { ok: false, error: "Лид не прошёл проверку: " + first, lead };
    }
    return { ok: true, error: "", lead: next };
  }

  // Оценку даёт только согласованный модуль RPLeadScore. Запасных порогов нет: нет модуля — нет оценки.
  function scorer() {
    if (root.RPLeadScore && typeof root.RPLeadScore.scoreLead === "function") return root.RPLeadScore.scoreLead;
    if (typeof require === "function") {
      try { const m = require("./lead-score.js"); if (m && typeof m.scoreLead === "function") return m.scoreLead; } catch (e) { /* модуль не найден */ }
    }
    return null;
  }
  // reason: "missing" — модуль не загружен, "error" — scoreLead выбросил ошибку, "invalid" — ответ неверного формата.
  const unavailable = (reason) => ({ score: null, tier: null, reasons: [], unavailable: true, reason: reason || "missing" });
  const UNAVAILABLE_TEXT = {
    missing: "Модуль оценки RPLeadScore не загружен.",
    error: "Модуль оценки RPLeadScore выбросил ошибку при расчёте.",
    invalid: "Модуль оценки RPLeadScore вернул ответ неверного формата (нет числовой оценки)."
  };

  function scoreOf(lead, now) {
    const fn = scorer();
    if (!fn) return unavailable("missing");
    try {
      const res = fn({
        urgency: lead.urgency, budget: lead.budget, deadline: null, service: lead.service,
        contact: lead.contact, idea: lead.comment, hasReferences: false,
        now: now instanceof Date ? now : new Date()
      });
      // null/undefined/строки — не оценка: Number(null) дал бы 0 и скрыл отсутствие оценки.
      const n = res && typeof res.score === "number" ? res.score : NaN;
      if (!Number.isFinite(n)) return unavailable("invalid");
      const score = Math.max(0, Math.min(100, n));
      return { score, tier: tierOf(score), reasons: Array.isArray(res.reasons) ? res.reasons.slice() : [], unavailable: false };
    } catch (e) {
      return unavailable("error");
    }
  }
  function tierOf(score) { return score >= 70 ? "hot" : score >= 40 ? "warm" : "cold"; }

  function isOverdue(lead, now) {
    if (!lead || CLOSED.includes(lead.stage) || !validDate(lead.nextStepDate)) return false;
    return lead.nextStepDate < dateStr(now instanceof Date ? now : new Date());
  }

  // Контракт сортировки: элементы { lead, sc } из scoreLeads; оценка считается там ровно один раз на лид.
  // Порядок: оценка по убыванию; записи с недоступной оценкой (score не число) всегда идут ПОСЛЕ оценённых
  // (-1 ниже любой оценки 0–100); оценка вне диапазона 0–100 тоже считается недоступной. Если оценки недоступны у всех, порядок определяют только createdAt (новее выше) и id.
  // Внутри группы с равной оценкой (или без неё) — тоже createdAt, затем id.
  function scoreLeads(list, now) { return list.map((lead) => ({ lead, sc: scoreOf(lead, now) })); }
  function sortScored(items) {
    // Элементы без sc или lead не роняют сортировку: оценка считается недоступной, поля пустыми.
    const s = (x) => (x && x.sc && typeof x.sc.score === "number" && Number.isFinite(x.sc.score) && x.sc.score >= 0 && x.sc.score <= 100 ? x.sc.score : -1);
    const f = (x, k) => String((x && x.lead && x.lead[k]) || "");
    // Даты ISO и id сравниваются напрямую (без localeCompare): порядок кодовых единиц стабилен и дёшев.
    const cmp = (x, y) => (x < y ? -1 : x > y ? 1 : 0);
    return (Array.isArray(items) ? items : []).slice().sort((a, b) =>
      s(b) - s(a) || cmp(f(b, "createdAt"), f(a, "createdAt")) || cmp(f(a, "id"), f(b, "id")));
  }
  function sortByScore(list, now) { return sortScored(scoreLeads(list, now)).map((x) => x.lead); }

  function demoLeads(now) {
    const mk = (id, o) => createLead(Object.assign({ id, demo: true, createdAt: addDays(now, o.age || -5) }, o), { now });
    return [
      mk("demo-1", { title: "Студия «Пример-1»", contact: "@demo_studio_one", service: "commercial", source: "site", budget: 150000, urgency: "asap", stage: "estimate", nextStep: "Позвонить по смете", nextStepDate: addDays(now, -2), comment: "Демо-лид: коммерческий ролик, ждём ответ по смете." }),
      mk("demo-2", { title: "Бренд «Пример-2»", contact: "demo2@example.invalid", service: "reels", source: "telegram", budget: 45000, urgency: "soon", stage: "brief", nextStep: "Согласовать референсы", nextStepDate: addDays(now, 2), comment: "Демо-лид: серия Reels." }),
      mk("demo-3", { title: "Проект «Пример-3»", contact: "@demo_project_three", service: "art", source: "referral", budget: 80000, urgency: "month", stage: "contacted", nextStep: "Назначить встречу", nextStepDate: addDays(now, 4), comment: "Демо-лид: арт-проект, пришёл по рекомендации." }),
      mk("demo-4", { title: "Клиент «Пример-4»", contact: "@demo_client_four", service: "editing", source: "social", budget: 15000, urgency: "later", stage: "new", nextStep: "Написать первым", nextStepDate: addDays(now, 1), comment: "Демо-лид: монтаж, бюджет небольшой." }),
      mk("demo-5", { title: "Компания «Пример-5»", contact: "demo5@example.invalid", service: "professional", source: "other", budget: 120000, urgency: "soon", stage: "approved", nextStep: "Подписать договор", nextStepDate: addDays(now, 3), comment: "Демо-лид: условия согласованы." }),
      mk("demo-6", { title: "Агентство «Пример-6»", contact: "@demo_agency_six", service: "graphics", source: "site", budget: 30000, urgency: "month", stage: "lost", lostReason: "Выбрали другую студию (демо-причина)", comment: "Демо-лид: проигран." })
    ];
  }

  // Структура исходной записи проверяется ДО createLead, чтобы подстановка значений по умолчанию
  // не превращала неполную или изменённую запись в валидную.
  const REQ_STR = ["id", "title", "contact", "service", "source", "urgency", "stage", "createdAt", "updatedAt"];
  const OPT_STR = ["nextStep", "nextStepDate", "comment", "lostReason"];
  function rawShapeOk(x) {
    if (!x || typeof x !== "object" || Array.isArray(x)) return false;
    if (!REQ_STR.every((k) => typeof x[k] === "string" && x[k] !== "")) return false;
    if (!OPT_STR.every((k) => x[k] === undefined || typeof x[k] === "string")) return false;
    if (x.budget != null && typeof x.budget !== "number") return false;
    if (x.demo !== undefined && typeof x.demo !== "boolean") return false;
    return true;
  }

  // Предел чтения: строка до storedChars символов (худший случай для LIMITS.leads лидов) разбирается целиком, а записи сверх LIMITS.leads
  // отбрасываются после разбора и учитываются в dropped. Для локального демо это приемлемо (разбор в пределах 2–3 МБ — миллисекунды);
  // потоковый разбор без внешних библиотек не оправдан.
  // Строгое чтение сохранённых данных: размер строки ограничен до JSON.parse; запись принимается только если
  // исходные значения (без усечения и подстановок) проходят validateLead, id и даты заданы явно и не повторяются.
  // Иначе запись отбрасывается. dropped — сколько записей пропущено; error: "size" | "json" | "shape" | "".
  function readStored(raw) {
    if (typeof raw !== "string") return { leads: null, dropped: 0, error: "shape" };
    if (raw.length > LIMITS.storedChars) return { leads: null, dropped: 0, error: "size" };
    let data;
    try { data = JSON.parse(raw); } catch (e) { return { leads: null, dropped: 0, error: "json" }; }
    if (!Array.isArray(data)) return { leads: null, dropped: 0, error: "shape" };
    const out = [];
    const seen = new Set();
    let dropped = Math.max(0, data.length - LIMITS.leads);
    data.slice(0, LIMITS.leads).forEach((x) => {
      if (!rawShapeOk(x)) { dropped += 1; return; }
      const lead = createLead(x);
      if (!validateLead(lead, { ids: seen }).valid) { dropped += 1; return; }
      seen.add(lead.id);
      out.push(lead);
    });
    return { leads: out, dropped, error: "" };
  }
  function parseStored(raw) {
    const r = readStored(raw);
    return r.leads;
  }

  const api = {
    STORAGE_KEY, BACKUP_KEY, STAGES, SOURCES, URGENCIES, SERVICES, TIERS, LIMITS,
    worstCaseStoredChars, createLead, validateLead, changeStage, scoreOf, scoreLeads, sortScored, tierOf, isOverdue, sortByScore, demoLeads, validContact, parseStored, readStored, newId, dateStr, addDays
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.RPLeads = api;
  if (typeof document === "undefined") return;

  // ---------- интерфейс ----------
  // Все правила привязаны к #rp-leads-panel (диалоги живут внутри панели), чтобы не задевать стили CRM.
  const P = "#rp-leads-panel";
  const RULES = [
    ["&", "color:#f1efe9;font:inherit;padding:8px 0 40px"],
    ["&[hidden]", "display:none"],
    ["*", "box-sizing:border-box"],
    [".rpl-head", "display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:16px"],
    [".rpl-head h1", "margin:0;font-size:28px"],
    [".rpl-head p", "margin:4px 0 0;color:#b4b0a6;font-size:14px"],
    [".rpl-note", "margin:0 0 12px;padding:10px 12px;border-radius:12px;border:1px solid #ffad29;background:rgba(255,173,41,.1);color:#f1efe9;font-size:13px"],
    [".rpl-note[hidden]", "display:none"],
    [".rpl-actions", "display:flex;gap:8px;flex-wrap:wrap"],
    [".rpl-btn", "min-height:44px;min-width:44px;max-width:100%;padding:8px 16px;line-height:1.25;border-radius:12px;border:1px solid rgba(255,255,255,.18);background:#1b1e21;color:#f1efe9;font:inherit;cursor:pointer"],
    [".rpl-btn:hover", "border-color:#ffad29"],
    [".rpl-btn.primary", "background:#ffad29;color:#101214;border-color:#ffad29;font-weight:600"],
    [".rpl-btn.danger", "border-color:#ff6b6b;color:#ffd0d0"],
    [":focus-visible", "outline:3px solid #ffad29;outline-offset:2px"],
    [".rpl-board", "display:grid;grid-auto-flow:column;grid-auto-columns:minmax(270px,1fr);gap:12px;overflow-x:auto;padding-bottom:12px;align-items:start"],
    [".rpl-col", "min-width:0;background:rgba(27,30,33,.82);border:1px solid rgba(255,255,255,.09);border-radius:16px;padding:10px;backdrop-filter:blur(10px)"],
    [".rpl-col h2", "margin:2px 4px 10px;font-size:15px;display:flex;justify-content:space-between;gap:8px"],
    [".rpl-col h2 span", "color:#b4b0a6;font-weight:400"],
    [".rpl-list", "list-style:none;margin:0;padding:0"],
    [".rpl-card", "background:#101214;border:1px solid rgba(255,255,255,.1);border-left:5px solid #5c6670;border-radius:12px;padding:12px;margin-bottom:10px"],
    [".rpl-card.hot", "border-left-color:#ffad29;background:linear-gradient(135deg,rgba(255,173,41,.16),#101214 60%);box-shadow:0 0 0 1px rgba(255,173,41,.35)"],
    [".rpl-card.warm", "border-left-color:#c9a45c"],
    [".rpl-card.cold", "border-left-color:#5c6670"],
    [".rpl-card.none", "border-left-color:#8a8f96;border-left-style:dashed"],
    [".rpl-card h3", "margin:0 0 6px;font-size:16px;overflow-wrap:anywhere"],
    [".rpl-row", "display:flex;flex-wrap:wrap;gap:6px;margin:6px 0;align-items:center"],
    [".rpl-tag", "display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid rgba(255,255,255,.22);font-size:12px;color:#d8d5cc"],
    [".rpl-tag.hot", "background:#ffad29;color:#101214;border-color:#ffad29;font-weight:700"],
    [".rpl-tag.warm", "border-color:#c9a45c;color:#e6c98a"],
    [".rpl-tag.cold", "color:#aeb6bf"],
    [".rpl-tag.none", "border-style:dashed;color:#d8d5cc"],
    [".rpl-tag.overdue", "background:#7a1f1f;border-color:#ff6b6b;color:#ffecec;font-weight:600"],
    [".rpl-tag.demo", "border-style:dashed;color:#ffad29;border-color:#ffad29"],
    [".rpl-meta", "font-size:13px;color:#b4b0a6;margin:4px 0;overflow-wrap:anywhere"],
    [".rpl-brief", "border:1px solid #555;padding:12px;border-radius:8px;white-space:pre-wrap"],
    [".rpl-meta b", "color:#f1efe9;font-weight:600"],
    [".rpl-card details", "margin:6px 0;font-size:13px;color:#b4b0a6"],
    [".rpl-card summary", "cursor:pointer;min-height:44px;display:flex;align-items:center"],
    [".rpl-card ul", "margin:0 0 6px;padding-left:18px"],
    [".rpl-card label", "display:block;font-size:12px;color:#b4b0a6;margin-top:6px"],
    [".rpl-field select,.rpl-field input,.rpl-field textarea,.rpl-card select", "width:100%;min-height:44px;padding:8px 10px;border-radius:10px;border:1px solid rgba(255,255,255,.2);background:#101214;color:#f1efe9;font:inherit"],
    [".rpl-field [aria-invalid=true]", "border-color:#ff9d9d"],
    [".rpl-field textarea", "min-height:88px"],
    [".rpl-ack", "display:flex;gap:10px;align-items:flex-start;min-height:44px;margin:0 0 10px;font-size:13px;color:#d8d5cc"],
    [".rpl-ack input", "width:24px;height:24px;min-width:24px;margin:0"],
    [".rpl-btn:disabled,.rpl-card select:disabled", "opacity:.45;cursor:not-allowed"],
    [".rpl-empty", "color:#7f7c74;font-size:13px;padding:6px 4px"],
    [".rpl-dialog", "background:#1b1e21;color:#f1efe9;border:1px solid rgba(255,173,41,.4);border-radius:16px;padding:20px;width:min(520px,calc(100vw - 24px));max-height:calc(100vh - 24px);overflow:auto"],
    [".rpl-dialog::backdrop", "background:rgba(0,0,0,.65)"],
    [".rpl-dialog h2", "margin:0 0 12px;font-size:20px"],
    [".rpl-dialog p", "margin:0 0 8px;font-size:14px;color:#d8d5cc"],
    [".rpl-field", "margin-bottom:10px"],
    [".rpl-field>span", "display:block;font-size:13px;color:#b4b0a6;margin-bottom:4px"],
    [".rpl-err", "color:#ff9d9d;font-size:13px;margin-top:4px"],
    [".rpl-dialog .rpl-actions", "justify-content:flex-end;margin-top:12px"],
    [".rpl-live", "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)"]
  ];
  const scope = (sel) => sel.split(",").map((s) => (s[0] === "&" ? P + s.slice(1) : P + " " + s.trim())).join(",");
  const css = RULES.map((r) => scope(r[0]) + "{" + r[1] + "}").join("\n") + "\n" +
    "body.rp-leads-on main>[data-rpl-hid]{display:none!important}\n" +
    "@media (prefers-reduced-motion:no-preference){" + scope(".rpl-btn,.rpl-card") + "{transition:border-color .15s,background .15s}}\n" +
    "@media (prefers-reduced-motion:reduce){" + scope("*") + "{transition:none!important;animation:none!important;scroll-behavior:auto!important}}\n" +
    "@media (max-width:640px){" + scope(".rpl-board") + "{grid-auto-flow:row;grid-auto-columns:unset;grid-template-columns:minmax(0,1fr);overflow-x:visible}}\n";

  function el(tag, attrs, kids) {
    const n = document.createElement(tag);
    if (attrs) for (const k of Object.keys(attrs)) {
      const v = attrs[k];
      if (v == null || v === false) continue;
      if (k === "text") n.textContent = v;
      else if (k === "class") n.className = v;
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    (kids || []).forEach((c) => { if (c != null) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  const money = (n) => (n == null ? "не указан" : Number(n).toLocaleString("ru-RU") + " ₽");
  const dateRu = (s) => (validDate(s) ? s.slice(8) + "." + s.slice(5, 7) + "." + s.slice(0, 4) : "");
  const tierLabel = (sc) => (sc.unavailable ? "Оценка недоступна" : TIERS[sc.tier]);

  let leads = [];
  let panel = null;
  let board = null;
  let live = null;
  let note = null;
  let scoreNote = null;
  let navBtn = null;
  let prevActive = null;
  let saveFailed = false;
  // Карты элементов для возврата фокуса после перерисовки (без обхода DOM).
  let refs = { edit: new Map(), stage: new Map() };

  function setNote(msg) {
    if (!note) return;
    note.textContent = msg || "";
    note.hidden = !msg;
  }
  function announce(msg) { if (live) live.textContent = msg; }

  // loadedRaw — снимок строки хранилища при последнем чтении/записи: по нему save() замечает правки из другой вкладки.
  // Это best-effort проверка перед setItem, а не атомарная блокировка: между getItem и setItem другая вкладка может успеть записать.
  // saveBlocked — запись запрещена, пока прежние данные нельзя ни прочитать, ни сохранить отдельно.
  let loadedRaw = null;
  let saveBlocked = false;
  let saveError = "";
  // resumable — часть записей пропущена, но копия сделана: запись включается только явным подтверждением.
  let resumable = false;
  // backupKey — ключ, под которым сохранена исходная строка в текущем load() (BACKUP_KEY или с меткой времени).
  let backupKey = BACKUP_KEY;
  // contactAck — пользователь уже подтвердил, что хранилище демонстрационное и не защищает контакты.
  let contactAck = false;
  let addBtn = null;
  let resumeBtn = null;

  function load() {
    saveBlocked = false;
    resumable = false;
    let raw = null;
    try { raw = localStorage.getItem(STORAGE_KEY); } catch (e) {
      leads = demoLeads(new Date());
      loadedRaw = null;
      saveBlocked = true;
      setNote("Хранилище браузера недоступно для чтения: показаны демо-лиды, сохранение отключено, чтобы не затереть прежние данные. Кнопка «Заменить демо-данными…» включит запись явно.");
      return;
    }
    loadedRaw = raw;
    if (raw == null) {
      leads = demoLeads(new Date());
      setNote("Показаны демонстрационные лиды (первый запуск). Это локальное демо-хранилище браузера: не вводите реальные контактные данные.");
      return;
    }
    // Нечитаемые или частично пропущенные данные сначала сохраняем отдельной копией для восстановления.
    // Прежняя копия не затирается: если под BACKUP_KEY уже лежит другое значение, пишем в новый ключ с меткой времени.
    const backup = () => {
      try {
        backupKey = BACKUP_KEY;
        const prev = localStorage.getItem(BACKUP_KEY);
        if (prev != null && prev !== raw) backupKey = BACKUP_KEY + "-" + Date.now();
        if (prev !== raw) localStorage.setItem(backupKey, raw);
        return true;
      } catch (e) { return false; }
    };
    const r = readStored(raw);
    if (!r.leads) {
      leads = demoLeads(new Date());
      const what = r.error === "size" ? "превышают допустимый размер" : "повреждены";
      if (backup()) {
        saveBlocked = true;
        setNote("Сохранённые данные " + what + " и не прочитаны. Копия исходной строки сделана в localStorage под ключом " + backupKey + " (best effort, без гарантии сохранности; модуль не умеет восстанавливать из неё — только вручную средствами браузера). Демо-лиды показаны только для просмотра: изменения отключены, пока вы не выберете «Заменить демо-данными…» (основная запись будет перезаписана).");
      } else {
        saveBlocked = true;
        setNote("Сохранённые данные " + what + " и не прочитаны, копию сделать не удалось. Показаны демо-лиды, сохранение отключено, чтобы не затереть данные. Кнопка «Заменить демо-данными…» включит запись явно.");
      }
      return;
    }
    leads = r.leads;
    if (r.dropped) {
      // Пропущенные записи (в том числе сверх лимита) не теряем молча: без копии запись блокируем.
      if (backup()) {
        saveBlocked = true;
        resumable = true;
        setNote("Записей в хранилище пропущено (некорректные или сверх лимита " + LIMITS.leads + "): " + r.dropped + ". Копия исходной строки сделана под ключом " + backupKey + " (best effort, без гарантии сохранности), но первое изменение перезапишет основное хранилище только принятыми лидами. Восстановления пропущенных записей в модуле нет: вернуть их можно только вручную вне модуля (DevTools браузера), на свой риск. Изменения отключены, пока вы не нажмёте «Разрешить перезапись принятыми лидами…» и не подтвердите перезапись.");
      } else {
        saveBlocked = true;
        setNote("Записей в хранилище пропущено (некорректные или сверх лимита " + LIMITS.leads + "): " + r.dropped + ". Копию исходных данных сделать не удалось, поэтому сохранение отключено, чтобы не потерять их. Кнопка «Заменить демо-данными…» включит запись явно.");
      }
    } else setNote("");
  }
  // Сначала запись, потом смена состояния: при ошибке список в памяти остаётся прежним (откат не нужен).
  // force — только для подтверждённой замены демо-данными: снимает блокировку и пропускает проверку снимка.
  function save(next, force) {
    saveError = "";
    try {
      if (saveBlocked && !force) throw new Error("blocked");
      if (!force && localStorage.getItem(STORAGE_KEY) !== loadedRaw) {
        saveError = "Данные изменены в другой вкладке. Список обновлён из хранилища, изменение не применено — повторите его.";
        load();
        setNote(saveError);
        announce(saveError);
        render();
        return false;
      }
      const str = JSON.stringify(next);
      if (str.length > LIMITS.storedChars) throw new Error("size");
      localStorage.setItem(STORAGE_KEY, str);
      loadedRaw = str;
      saveBlocked = false;
      resumable = false;
      if (saveFailed) { saveFailed = false; setNote(""); }
      return true;
    } catch (e) {
      saveFailed = true;
      saveError = saveBlocked ? "Сохранение отключено: прежние данные хранилища не прочитаны или замена не подтверждена."
        : e && e.message === "size" ? "Данные превысят допустимый размер хранилища (" + LIMITS.storedChars + " символов): изменение не применено, сократите тексты или удалите лишние лиды."
          : "Не удалось сохранить в браузере: изменение не применено.";
      setNote(saveError);
      announce(saveError);
      return false;
    }
  }

  function focusTarget(spec) {
    if (!spec) return;
    const add = document.getElementById("rpl-add");
    const t = spec === "add" ? add : (refs[spec[0]] && refs[spec[0]].get(spec[1])) || add;
    if (t) t.focus();
  }

  // Уникальный DOM-id карточки не зависит от id записи: счётчик сбрасывается при каждой перерисовке доски.
  let domSeq = 0;
  function card(lead, sc, now, open) {
    const dom = "rpl-" + (domSeq += 1);
    const overdue = isOverdue(lead, now);
    const label = tierLabel(sc);
    const scoreText = sc.unavailable ? label : label + ", " + sc.score + " из 100";
    const tag = sc.unavailable ? label : label + " · " + sc.score;
    const stageSel = el("select", { id: dom + "-st", "data-stage": lead.id, "aria-label": "Стадия лида " + lead.title, disabled: saveBlocked, onchange: (e) => onStage(lead, e.target.value) },
      STAGES.map((s) => el("option", { value: s.id, text: s.label, selected: s.id === lead.stage })));
    const editBtn = el("button", { type: "button", class: "rpl-btn", "data-edit": lead.id, "aria-label": "Редактировать: " + lead.title, text: "Редактировать", disabled: saveBlocked, onclick: (e) => openForm(lead, e.currentTarget) });
    refs.stage.set(lead.id, stageSel);
    refs.edit.set(lead.id, editBtn);
    return el("article", { class: "rpl-card " + (sc.unavailable ? "none" : sc.tier), "data-lead": lead.id, "aria-labelledby": dom + "-h" }, [
      el("h3", { id: dom + "-h", text: lead.title }),
      el("div", { class: "rpl-row" }, [
        el("span", { class: "rpl-tag " + (sc.unavailable ? "none" : sc.tier), title: scoreText, text: tag }),
        overdue ? el("span", { class: "rpl-tag overdue", text: "Следующий шаг просрочен" }) : null,
        lead.demo ? el("span", { class: "rpl-tag demo", text: "ДЕМО" }) : null
      ]),
      el("div", { class: "rpl-meta" }, [el("b", { text: "Бюджет: " }), money(lead.budget)]),
      el("div", { class: "rpl-meta" }, [el("b", { text: "Срочность: " }), labelOf(URGENCIES, lead.urgency)]),
      el("div", { class: "rpl-meta" }, [el("b", { text: "Источник: " }), labelOf(SOURCES, lead.source)]),
      el("div", { class: "rpl-meta" }, [el("b", { text: "Услуга: " }), labelOf(SERVICES, lead.service)]),
      el("div", { class: "rpl-meta" }, [el("b", { text: "Контакт: " }), lead.contact]),
      el("div", { class: "rpl-meta" }, [el("b", { text: "Следующий шаг: " }), lead.nextStep ? lead.nextStep + (lead.nextStepDate ? " — " + dateRu(lead.nextStepDate) : "") : "не задан"]),
      lead.stage === "lost" ? el("div", { class: "rpl-meta" }, [el("b", { text: "Причина: " }), lead.lostReason]) : null,
      lead.comment ? el("div", { class: "rpl-meta rpl-brief", text: lead.comment }) : null,
      el("label", { for: dom + "-st", text: "Стадия" }),
      stageSel,
      el("div", { class: "rpl-row" }, [
        editBtn,
        el("button", { type: "button", class: "rpl-btn danger", "aria-label": "Удалить: " + lead.title, text: "Удалить", disabled: saveBlocked, onclick: (e) => onDelete(lead, e.currentTarget) })
      ])
    ]);
  }

  function render(focus) {
    if (!board) return;
    if (addBtn) addBtn.disabled = saveBlocked;
    if (resumeBtn) resumeBtn.hidden = !resumable;
    const now = new Date();
    // Сохраняем состояние доски: раскрытые причины и горизонтальную прокрутку.
    const open = new Set();
    board.querySelectorAll("details[open]").forEach((d) => { const a = d.closest("[data-lead]"); if (a) open.add(a.getAttribute("data-lead")); });
    const left = board.scrollLeft;
    // Оценка считается один раз на лид, сортировка — одна на всю доску; колонки сохраняют этот порядок.
    const scored = sortScored(scoreLeads(leads, now));
    if (scoreNote) {
      const bad = scored.find((x) => x.sc.unavailable);
      scoreNote.textContent = bad ? "Оценка лидов недоступна. " + (UNAVAILABLE_TEXT[bad.sc.reason] || UNAVAILABLE_TEXT.missing) + " Метки Горячий/Тёплый/Холодный не показываются; карточки без оценки идут после оценённых и упорядочены по дате создания." : "";
      scoreNote.hidden = !bad;
    }
    refs = { edit: new Map(), stage: new Map() };
    domSeq = 0;
    board.textContent = "";
    const byStage = new Map(STAGES.map((st) => [st.id, []]));
    scored.forEach((x) => { const g = byStage.get(x.lead.stage); if (g) g.push(x); });
    STAGES.forEach((st) => {
      const items = byStage.get(st.id);
      const hid = "rpl-col-" + st.id;
      board.appendChild(el("section", { class: "rpl-col", "aria-labelledby": hid }, [
        el("h2", { id: hid }, [st.label, el("span", { text: String(items.length) })]),
        items.length
          ? el("ul", { class: "rpl-list", role: "list", "aria-label": st.label + ", карточек: " + items.length },
            items.map((x) => el("li", null, [card(x.lead, x.sc, now, open.has(x.lead.id))])))
          : el("div", { class: "rpl-empty", text: "Пусто" })
      ]));
    });
    board.scrollLeft = left;
    focusTarget(focus);
  }

  function openDialog(d) { if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", ""); }
  function closeDialog(d, restoreFocus) {
    if (d.rplClosed) return;
    d.rplClosed = true;
    if (typeof d.close === "function") { try { d.close(); } catch (e) { d.removeAttribute("open"); } } else d.removeAttribute("open");
    d.remove();
    const back = d.rplOpener;
    if (restoreFocus !== false && back && back.isConnected) back.focus();
  }
  // Escape и Tab обрабатываются сами: в браузерах без showModal нет ни события cancel, ни ловушки фокуса.
  function mountDialog(dlg, opener, onCancel) {
    dlg.rplOpener = opener || null;
    dlg.setAttribute("aria-modal", "true");
    dlg.addEventListener("cancel", (e) => { e.preventDefault(); onCancel(); });
    dlg.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onCancel(); return; }
      if (e.key !== "Tab") return;
      const items = Array.prototype.filter.call(
        dlg.querySelectorAll("button,input,select,textarea,summary,[tabindex]"),
        (n) => !n.disabled && n.tabIndex >= 0 && !n.closest("[hidden]"));
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      const cur = document.activeElement;
      if (!dlg.contains(cur)) { e.preventDefault(); first.focus(); }
      else if (e.shiftKey && cur === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && cur === last) { e.preventDefault(); first.focus(); }
    });
    (panel || document.body).appendChild(dlg);
    openDialog(dlg);
  }

  function field(label, id, control, err) {
    if (err) { control.setAttribute("aria-invalid", "true"); control.setAttribute("aria-describedby", "rpl-err-" + id); }
    return el("div", { class: "rpl-field" }, [
      el("span", null, [el("label", { for: id, text: label })]),
      control,
      err ? el("div", { class: "rpl-err", id: "rpl-err-" + id, text: err }) : null
    ]);
  }
  function select(id, list, value) {
    return el("select", { id, name: id }, list.map((o) => el("option", { value: o.id, text: o.label, selected: o.id === value })));
  }
  function input(id, type, value, extra) {
    return el("input", Object.assign({ id, name: id, type, value: value == null ? "" : String(value) }, extra || {}));
  }

  function confirmBox(title, msg, okLabel, onOk, opener) {
    const dlg = el("dialog", { class: "rpl-dialog", role: "dialog", "aria-labelledby": "rpl-c-title", "aria-describedby": "rpl-c-text" }, [
      el("h2", { id: "rpl-c-title", text: title }),
      el("p", { id: "rpl-c-text", text: msg }),
      el("div", { class: "rpl-actions" }, [
        el("button", { type: "button", class: "rpl-btn", id: "rpl-c-cancel", text: "Отмена", onclick: () => closeDialog(dlg) }),
        el("button", { type: "button", class: "rpl-btn danger", text: okLabel, onclick: () => { closeDialog(dlg, false); onOk(); } })
      ])
    ]);
    // Клик по затемнению равен «Отмене» (только в подтверждениях; формы с введёнными данными так не закрываются).
    dlg.addEventListener("click", (e) => {
      if (e.target !== dlg) return;
      const r = dlg.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeDialog(dlg);
    });
    mountDialog(dlg, opener, () => closeDialog(dlg));
    dlg.querySelector("#rpl-c-cancel").focus();
  }

  function openForm(existing, opener) {
    const isNew = !existing;
    // Работаем с копией: отменённое или невалидное редактирование не должно менять лид в списке.
    const base = Object.assign({}, existing || createLead({}, { taken: ids(leads) }));
    let errors = {};
    let ackChecked = contactAck;
    const dlg = el("dialog", { class: "rpl-dialog", role: "dialog", "aria-labelledby": "rpl-form-title" });
    function draw() {
      dlg.textContent = "";
      const e = errors;
      const formErr = e.form || e.id || e.createdAt || e.updatedAt;
      const stageSel = select("rpl-f-stage", STAGES, base.stage);
      const lostWrap = el("div", { id: "rpl-lost-wrap" }, [
        field("Причина проигрыша (обязательна)", "rpl-f-lost", input("rpl-f-lost", "text", base.lostReason, { maxlength: String(LIMITS.lostReason) }), e.lostReason)
      ]);
      const sync = () => { lostWrap.hidden = stageSel.value !== "lost"; };
      stageSel.addEventListener("change", sync);
      const form = el("form", { novalidate: true }, [
        el("h2", { id: "rpl-form-title", text: isNew ? "Новый лид" : "Редактирование лида" }),
        formErr ? el("div", { class: "rpl-err", role: "alert", id: "rpl-form-err", text: formErr }) : null,
        field("Название / клиент", "rpl-f-title", input("rpl-f-title", "text", base.title, { required: true, maxlength: String(LIMITS.title) }), e.title),
        field("Контакт (телефон, Telegram или email)", "rpl-f-contact", input("rpl-f-contact", "text", base.contact, { required: true, maxlength: String(LIMITS.contact), autocomplete: "off" }), e.contact),
        contactAck ? null : el("div", { class: "rpl-field" }, [
          el("label", { class: "rpl-ack", for: "rpl-f-ack" }, [
            el("input", { type: "checkbox", id: "rpl-f-ack", name: "rpl-f-ack", checked: ackChecked, "aria-invalid": e.ack ? "true" : null, "aria-describedby": e.ack ? "rpl-err-rpl-f-ack" : null }),
            el("span", { text: "Понимаю: это демо-хранилище браузера без защиты, оно доступно скриптам сайта. Реальные контакты клиентов я не вношу." })
          ]),
          e.ack ? el("div", { class: "rpl-err", id: "rpl-err-rpl-f-ack", text: e.ack }) : null
        ]),
        field("Услуга", "rpl-f-service", select("rpl-f-service", SERVICES, base.service), e.service),
        field("Источник", "rpl-f-source", select("rpl-f-source", SOURCES, base.source), e.source),
        field("Бюджет, ₽ (целое число)", "rpl-f-budget", input("rpl-f-budget", "number", base.budget, { min: "0", max: String(LIMITS.budget), step: "1", inputmode: "numeric" }), e.budget),
        field("Срочность", "rpl-f-urgency", select("rpl-f-urgency", URGENCIES, base.urgency), e.urgency),
        field("Следующий шаг", "rpl-f-next", input("rpl-f-next", "text", base.nextStep, { maxlength: String(LIMITS.nextStep) }), e.nextStep),
        field("Дата следующего шага", "rpl-f-date", input("rpl-f-date", "date", base.nextStepDate), e.nextStepDate),
        el("div", { hidden: isNew }, [field("Стадия", "rpl-f-stage", stageSel, e.stage)]),
        lostWrap,
        field("Комментарий", "rpl-f-comment", el("textarea", { id: "rpl-f-comment", name: "rpl-f-comment", maxlength: String(LIMITS.comment), text: base.comment }), e.comment),
        el("div", { class: "rpl-actions" }, [
          el("button", { type: "button", class: "rpl-btn", text: "Отмена", onclick: () => closeDialog(dlg) }),
          el("button", { type: "submit", class: "rpl-btn primary", id: "rpl-f-submit", text: "Сохранить" })
        ])
      ]);
      sync();
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const g = (id) => form.querySelector("#" + id).value;
        const stage = g("rpl-f-stage");
        const reasonRaw = g("rpl-f-lost");
        const draft = createLead({
          id: base.id, title: g("rpl-f-title"), contact: g("rpl-f-contact"), service: g("rpl-f-service"), source: g("rpl-f-source"),
          budget: g("rpl-f-budget"), urgency: g("rpl-f-urgency"), nextStep: g("rpl-f-next"), nextStepDate: g("rpl-f-date"),
          comment: g("rpl-f-comment"), stage, lostReason: stage === "lost" ? reasonRaw : "",
          // createdAt берётся только из исходной записи и не меняется; updatedAt ставится явно при каждом сохранении.
          demo: base.demo, createdAt: base.createdAt, updatedAt: dateStr(new Date())
        });
        const retry = (errs) => {
          errors = errs; Object.assign(base, draft, { lostReason: reasonRaw }); draw();
          const first = dlg.querySelector("[aria-invalid=\"true\"]") || dlg.querySelector("#rpl-f-submit");
          if (first) first.focus();
        };
        // Для нового лида проверяем id против всего списка, для существующего — против остальных.
        const v = validateLead(draft, { others: isNew ? leads : leads.filter((l) => l.id !== base.id) });
        const ackEl = form.querySelector("#rpl-f-ack");
        if (ackEl) ackChecked = ackEl.checked;
        const errs = Object.assign({}, v.errors);
        if (!contactAck && !ackChecked) errs.ack = "Подтвердите, что хранилище демонстрационное.";
        if (Object.keys(errs).length) { retry(errs); return; }
        const exists = leads.some((l) => l.id === draft.id);
        if (!exists && leads.length >= LIMITS.leads) { retry({ form: "Достигнут предел лидов: " + LIMITS.leads + "." }); return; }
        const next = exists ? leads.map((l) => (l.id === draft.id ? draft : l)) : leads.concat([draft]);
        if (!save(next)) { retry({ form: saveError + " Лид " + (isNew ? "не добавлен" : "не изменён") + ", данные в форме сохранены." }); return; }
        leads = next;
        contactAck = true;
        closeDialog(dlg, false);
        render(["edit", draft.id]);
        announce(isNew ? "Лид добавлен" : "Лид сохранён");
      });
      dlg.appendChild(form);
    }
    draw();
    mountDialog(dlg, opener || document.getElementById("rpl-add"), () => closeDialog(dlg));
    const f = dlg.querySelector("#rpl-f-title"); if (f) f.focus();
  }

  function askReason(lead, done) {
    const dlg = el("dialog", { class: "rpl-dialog", role: "dialog", "aria-labelledby": "rpl-lost-title" });
    let err = "";
    let finished = false;
    const finish = (value) => { if (finished) return; finished = true; closeDialog(dlg, false); done(value); };
    function draw(val) {
      dlg.textContent = "";
      const inp = input("rpl-r-reason", "text", val || "", { maxlength: String(LIMITS.lostReason), required: true });
      const form = el("form", { novalidate: true }, [
        el("h2", { id: "rpl-lost-title", text: "Причина проигрыша" }),
        field("Почему лид проигран? (обязательно)", "rpl-r-reason", inp, err),
        el("div", { class: "rpl-actions" }, [
          el("button", { type: "button", class: "rpl-btn", text: "Отмена", onclick: () => finish(null) }),
          el("button", { type: "submit", class: "rpl-btn primary", text: "Перевести в «Проиграно»" })
        ])
      ]);
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const v = inp.value.trim();
        if (CTRL_RE.test(inp.value)) { err = "Недопустимые управляющие символы."; draw(""); dlg.querySelector("input").focus(); return; }
        if (!v) { err = "Причина обязательна."; draw(""); dlg.querySelector("input").focus(); return; }
        if (v.length > LIMITS.lostReason) { err = "Причина не длиннее " + LIMITS.lostReason + " символов."; draw(v); dlg.querySelector("input").focus(); return; }
        finish(v);
      });
      dlg.appendChild(form);
    }
    draw(String(lead.lostReason || ""));
    mountDialog(dlg, null, () => finish(null));
    dlg.querySelector("input").focus();
  }

  function onStage(lead, stage) {
    const back = ["stage", lead.id];
    const apply = (reason) => {
      // Отмена: перерисовка возвращает select к сохранённой стадии.
      if (reason === null) { render(back); return; }
      const cur = leads.find((l) => l.id === lead.id);
      if (!cur) { render("add"); return; }
      const r = changeStage(cur, stage, { reason });
      if (!r.ok) { announce(r.error); render(back); return; }
      const next = leads.map((l) => (l.id === cur.id ? r.lead : l));
      const saved = save(next);
      if (saved) leads = next;
      render(back);
      announce(saved ? "Стадия лида «" + cur.title + "»: " + labelOf(STAGES, stage) : saveError + " Стадия лида «" + cur.title + "» не изменена.");
    };
    if (stage === "lost") {
      // Допустимая прежняя причина используется без повторного ввода; иначе запрашиваем новую.
      const keptRaw = String(lead.lostReason || "");
      const kept = keptRaw.trim();
      // Тем же правилом, что и changeStage/validateLead: длина и отсутствие управляющих символов в исходной строке.
      if (kept && kept.length <= LIMITS.lostReason && !CTRL_RE.test(keptRaw)) apply(""); else askReason({ lostReason: "" }, apply);
    } else apply("");
  }

  function onDelete(lead, opener) {
    confirmBox("Удалить лид?", "Лид «" + lead.title + "» будет удалён из списка в этом браузере. Действие нельзя отменить.", "Удалить", () => {
      const next = leads.filter((l) => l.id !== lead.id);
      if (!save(next)) { render(["edit", lead.id]); return; }
      leads = next;
      render("add");
      announce("Лид удалён");
    }, opener);
  }

  function onResume(opener) {
    confirmBox("Перезаписать хранилище принятыми лидами?", "Первое же изменение заменит основное хранилище только принятыми лидами; пропущенные записи останутся лишь в копии под ключом " + backupKey + ". Модуль не умеет импортировать копию и не проверяет её: вернуть эти записи можно только вручную средствами браузера (DevTools), на свой риск. Действие нельзя отменить.", "Да, разрешить перезапись", () => {
      // Режим продолжения: снимок перепроверяется прямо сейчас. Если за время диалога данные изменила другая
      // вкладка, перезапись не включаем — иначе затёрли бы её правки; список перечитывается заново.
      let current;
      try { current = localStorage.getItem(STORAGE_KEY); } catch (e) { current = undefined; }
      if (current !== loadedRaw) {
        load();
        render("add");
        const msg = "Данные в хранилище изменились, пока шло подтверждение. Список перечитан, перезапись не включена.";
        setNote(msg);
        announce(msg);
        return;
      }
      saveBlocked = false;
      resumable = false;
      setNote("Перезапись разрешена. Пропущенные записи остались только в копии " + backupKey + ". Модуль не восстанавливает их автоматически и не проверяет копию.");
      render("add");
      announce("Запись включена");
    }, opener);
  }

  function onReset(opener) {
    confirmBox("Заменить лиды демо-данными?", "Все ваши лиды, правки и новые записи будут заменены вымышленными демо-лидами. Действие нельзя отменить.", "Заменить", () => {
      const next = demoLeads(new Date());
      if (!save(next, true)) { render("add"); return; }
      leads = next;
      resumable = false;
      setNote("Показаны демонстрационные лиды.");
      render("add");
      announce("Демо-лиды восстановлены");
    }, opener);
  }

  // Клик по другому пункту меню закрывает панель. Слушатель стоит на window в фазе capture: она идёт раньше
  // document-capture обработчика dashboard.js, который вызывает stopImmediatePropagation. Событие не гасим,
  // поэтому приложение затем обрабатывает клик как обычно.
  // dashboard.js скрывает меню (hidden) для роли без доступа: «Лиды» тогда не открываем, а открытую панель закрываем.
  // Это проверка состояния DOM, а не авторизация: модуль не является средством контроля доступа, в localStorage лежат
  // только несекретные демо-данные. Роль напрямую не читается — её меню скрывает dashboard.js; скрытие отслеживает observer ниже.
  // Доступ проверяется при КАЖДОМ открытии панели (show) и на каждом клике; отсоединённое от DOM меню тоже считается запретом.
  function accessDenied() { return !navBtn || !navBtn.isConnected || !!navBtn.closest("[hidden]"); }
  let hideObserver = null;
  // Если меню скрыли без клика (смена роли), открытая панель закрывается сразу, а не при следующем клике.
  // Наблюдение ограничено цепочкой предков самого пункта меню (без subtree по всему документу): `hidden` может стоять
  // на nav или любом его предке, несвязанные изменения DOM observer не будят. Цепочка переопределяется при каждом открытии.
  function watchHidden() {
    if (typeof MutationObserver !== "function" || !navBtn || !navBtn.isConnected) return;
    if (!hideObserver) hideObserver = new MutationObserver(() => { if (panel && !panel.hidden && accessDenied()) show(false); });
    for (let n = navBtn.parentNode; n && n.nodeType === 1; n = n.parentNode) {
      hideObserver.observe(n, { attributes: true, attributeFilter: ["hidden"] });
    }
  }
  function onNavClick(e) {
    if (!panel || panel.hidden || !navBtn || !navBtn.parentNode) return;
    if (accessDenied()) { show(false); return; }
    const t = e.target;
    const b = t && t.closest ? t.closest("button") : null;
    if (!b || b === navBtn || !navBtn.parentNode.contains(b)) return;
    show(false, b);
  }
  root.addEventListener("click", onNavClick, true);

  // Полная очистка: слушатели, пункт меню, панель и стили. Нужна при пересборке CRM и повторной инициализации.
  function destroy() {
    root.removeEventListener("click", onNavClick, true);
    if (hideObserver) { hideObserver.disconnect(); hideObserver = null; }
    if (panel && panel.isConnected && !panel.hidden) show(false);
    if (navBtn) navBtn.remove();
    if (panel) panel.remove();
    document.querySelectorAll("[data-rpl-hid]").forEach((n) => n.removeAttribute("data-rpl-hid"));
    const st = document.getElementById("rp-leads-style");
    if (st) st.remove();
    document.body.classList.remove("rp-leads-on");
    panel = board = live = note = scoreNote = navBtn = prevActive = addBtn = resumeBtn = null;
    refs = { edit: new Map(), stage: new Map() };
  }

  function build() {
    const main = document.querySelector("main");
    const nav = document.querySelector(".sidebar nav") || document.querySelector("aside nav");
    if (panel && panel.isConnected) {
      // Уже собрано: при необходимости вернуть пункт меню и привязать обработчик к актуальному nav, дублей не создаём.
      if (nav && navBtn && !navBtn.isConnected) nav.appendChild(navBtn);
      root.addEventListener("click", onNavClick, true); // повторная привязка той же функции игнорируется
      return;
    }
    if (panel) destroy(); // устаревшие ссылки на отсоединённые узлы
    if (document.getElementById("rp-leads-panel")) return;
    if (!main || !nav) {
      if (root.console && root.console.warn) root.console.warn("RPLeads: не найдены main или боковое меню — модуль не запущен.");
      return;
    }
    const style = document.createElement("style");
    style.id = "rp-leads-style";
    style.textContent = css;
    document.head.appendChild(style);
    live = el("div", { class: "rpl-live", role: "status", "aria-live": "polite" });
    note = el("div", { class: "rpl-note", role: "status", hidden: true });
    scoreNote = el("div", { class: "rpl-note", role: "status", hidden: true });
    board = el("div", { class: "rpl-board", role: "region", tabindex: "0", "aria-label": "Воронка лидов по стадиям" });
    panel = el("section", { id: "rp-leads-panel", "aria-label": "Лиды", hidden: true }, [
      el("div", { class: "rpl-head" }, [
        el("div", null, [
          el("h1", { id: "rpl-title", tabindex: "-1", text: "Лиды" }),
          el("p", { text: "Воронка · внутри колонок лиды отсортированы по оценке. Это локальное демо-хранилище браузера (localStorage): оно не защищает данные и доступно скриптам этого сайта, поэтому не вводите реальные контакты клиентов. Одновременная правка в двух вкладках не гарантирует защиты от потери изменений (проверка best-effort): работайте с лидами в одной вкладке. Для настоящей CRM нужны серверная авторизация и контроль доступа." })
        ]),
        el("div", { class: "rpl-actions" }, [
          el("button", { type: "button", class: "rpl-btn primary", id: "rpl-add", text: "+ Новый лид", onclick: (e) => openForm(null, e.currentTarget) }),
          el("button", { type: "button", class: "rpl-btn", id: "rpl-resume", text: "Разрешить перезапись принятыми лидами…", hidden: true, onclick: (e) => onResume(e.currentTarget) }),
          el("button", { type: "button", class: "rpl-btn", id: "rpl-reset", text: "Заменить демо-данными…", onclick: (e) => onReset(e.currentTarget) })
        ])
      ]),
      note, scoreNote, board, live
    ]);
    main.appendChild(panel);
    addBtn = panel.querySelector("#rpl-add");
    resumeBtn = panel.querySelector("#rpl-resume");
    load();
    render();
    navBtn = el("button", { type: "button", "data-rp": "leads" }, [el("span", { text: "◈" }), " Лиды"]);
    // Скрытое меню: панель не открываем, а уже открытую закрываем в самом обработчике клика, не дожидаясь observer.
    navBtn.addEventListener("click", (e) => { e.stopPropagation(); show(!accessDenied()); });
    root.addEventListener("click", onNavClick, true);
    nav.appendChild(navBtn);
    watchHidden();
  }

  function setMainHidden(on) {
    if (!panel || !panel.parentNode) return;
    Array.prototype.forEach.call(panel.parentNode.children, (c) => {
      if (c === panel) return;
      if (on) c.setAttribute("data-rpl-hid", ""); else c.removeAttribute("data-rpl-hid");
    });
  }

  function show(on, clicked) {
    if (!panel || !navBtn) return;
    const wasOn = !panel.hidden;
    // Запрещённый доступ: закрытую панель не открываем; уже открытую закрываем обычным путём ниже.
    if (on && accessDenied()) { if (!wasOn) return; on = false; clicked = null; }
    if (on) watchHidden();
    const buttons = navBtn.parentNode ? navBtn.parentNode.querySelectorAll("button") : [];
    if (on) {
      if (!wasOn) {
        prevActive = null;
        buttons.forEach((b) => { if (b !== navBtn && b.classList.contains("active")) prevActive = b; });
      }
      buttons.forEach((b) => { if (b !== navBtn) b.classList.remove("active"); });
      setMainHidden(true);
      document.body.classList.add("rp-leads-on");
      panel.hidden = false;
      navBtn.classList.add("active");
      navBtn.setAttribute("aria-current", "page");
      render();
      const h = document.getElementById("rpl-title"); if (h) h.focus();
    } else {
      // Открытые диалоги закрываем при уходе: их кнопки-открыватели скрываются вместе с панелью.
      panel.querySelectorAll("dialog.rpl-dialog").forEach((d) => closeDialog(d, false));
      document.body.classList.remove("rp-leads-on");
      setMainHidden(false);
      panel.hidden = true;
      navBtn.classList.remove("active");
      navBtn.removeAttribute("aria-current");
      // Восстанавливаем активный пункт: нажатый или тот, что был активен до открытия «Лидов».
      const target = clicked || prevActive;
      if (target) target.classList.add("active");
      if (clicked && clicked.isConnected) clicked.focus();
    }
  }

  api.init = build;
  api.destroy = destroy;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
})(typeof window !== "undefined" ? window : globalThis);
