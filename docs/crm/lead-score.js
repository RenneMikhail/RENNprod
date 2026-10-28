"use strict";
// Lead scoring for the RENN Prod CRM (proposal: thresholds need owner approval).
// Input: {urgency:"asap"|"soon"|"month"|"later" (used when no deadline), budget:number|null (RUB), deadline:"YYYY-MM-DD"|null, service, contact:string, idea:string, hasReferences:boolean, now:Date}
// Output: {score:0..100, tier:"hot"|"warm"|"cold", reasons:string[]}
(function (root) {
  const SERVICE_POINTS = { professional: 10, commercial: 10, art: 10, reels: 8, editing: 6, graphics: 6, ai: 6 };
  function validContact(raw) {
    const v = String(raw || "").trim();
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) || /^@?[A-Za-z0-9_]{5,32}$/.test(v.replace(/^(https?:\/\/)?t\.me\//i, ""));
  }
  function scoreLead(lead) {
    const reasons = [];
    let score = 0;
    const now = lead.now instanceof Date ? lead.now : new Date();
    const budget = Number(lead.budget);
    if (Number.isFinite(budget) && budget > 0) {
      const pts = budget >= 100000 ? 40 : budget >= 40000 ? 30 : budget >= 20000 ? 20 : 10;
      score += pts; reasons.push(`бюджет ${budget} ₽: +${pts}`);
    } else reasons.push("бюджет не указан: +0");
    const URGENCY = { asap: [25, "срочно (до 7 дней)"], soon: [18, "скоро (до 3 недель)"], month: [10, "в течение 1-2 месяцев"], later: [4, "не срочно"] };
    if (lead.urgency && URGENCY[lead.urgency] && !lead.deadline) {
      const [pts, label] = URGENCY[lead.urgency]; score += pts; reasons.push(`срочность ${label}: +${pts}`);
    } else if (lead.deadline) {
      const days = Math.ceil((new Date(lead.deadline + "T00:00:00") - now) / 86400000);
      if (Number.isNaN(days)) reasons.push("срок не распознан: +0");
      else if (days < 0) reasons.push("срок уже в прошлом: +0");
      else { const pts = days <= 7 ? 25 : days <= 21 ? 18 : days <= 60 ? 10 : 4; score += pts; reasons.push(`срок через ${days} дн.: +${pts}`); }
    } else reasons.push("срок не указан: +0");
    if (validContact(lead.contact)) { score += 10; reasons.push("есть рабочий контакт: +10"); } else reasons.push("контакт не распознан: +0");
    if (String(lead.idea || "").trim().length >= 80) { score += 10; reasons.push("подробное описание: +10"); }
    if (lead.hasReferences) { score += 5; reasons.push("есть референсы: +5"); }
    const sp = SERVICE_POINTS[lead.service] || 0;
    if (sp) { score += sp; reasons.push(`услуга ${lead.service}: +${sp}`); }
    score = Math.min(100, score);
    const tier = score >= 70 ? "hot" : score >= 40 ? "warm" : "cold";
    return { score, tier, reasons };
  }
  const api = { scoreLead, validContact };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.RPLeadScore = api;
})(typeof window !== "undefined" ? window : globalThis);
