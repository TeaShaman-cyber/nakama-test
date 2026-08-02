import { spawnSync } from "node:child_process";

const jsonOutput = process.argv.includes("--json");
const auditProcess = spawnSync(process.execPath, ["tools/blog_audit.mjs", "--json"], {
  encoding: "utf8",
});

if (auditProcess.status !== 0) {
  console.error(auditProcess.stderr || "Blog audit failed.");
  process.exit(auditProcess.status ?? 1);
}

const audit = JSON.parse(auditProcess.stdout);

const series = {
  "Семейный архив": {
    promise: "Люди, память рода, семейные документы и восстановление истории.",
    include_when: "Главное движение текста связано с семейным проектом или сохранением человеческой истории.",
    exclude_when: "Семейный проект только упомянут как фон для инженерной проблемы.",
  },
  "Инженерная метафизика": {
    promise: "Системы, среды, память и границы, рассмотренные через реальные инженерные столкновения.",
    include_when: "Главный предмет — архитектура, runtime, контуры памяти, коннекторы или пределы системы.",
    exclude_when: "Техническая деталь служит только декорацией для самостоятельной истории о голосах или семье.",
  },
  "Лаборатория граблей": {
    promise: "Ошибки, сбои и практические уроки, добытые через сопротивление среды.",
    include_when: "Текст строится вокруг конкретного инцидента и извлечённого из него operational lesson.",
    exclude_when: "Инцидент упомянут мимоходом, а основная тема — идентичность, память или семейная история.",
  },
  "Живые голоса": {
    promise: "Отношения между голосами, ролями и формами присутствия в общем проекте.",
    include_when: "Главный предмет — изменение роли, различие голосов или совместная редакторская практика.",
    exclude_when: "Персонаж или шутка только оформляют технический рассказ.",
  },
  "Садхана инженерии": {
    promise: "Этика, границы, терпение и дисциплина, превращающие инженерную практику в устойчивый способ работы.",
    include_when: "Текст формулирует принцип работы или отношение к сложности, а не только описывает событие.",
    exclude_when: "Нет обобщаемого принципа за пределами конкретного сбоя.",
  },
  "Квантовый чай": {
    promise: "Игровые наблюдения и миниатюры, где бытовое и техническое смотрят друг на друга.",
    include_when: "Текст — самостоятельная игровая миниатюра или сценка с чайной/квантовой рамкой.",
    exclude_when: "Перед читателем полноценный postmortem или инженерный разбор.",
  },
};

const keywordRules = [
  {
    candidate: "Семейный архив",
    terms: ["семейн", "мам", "родослов", "генеалог", "family research"],
    weight: 5,
    label: "family-project terms",
  },
  {
    candidate: "Живые голоса",
    terms: ["шут перестал", "голос", "второй ии", "коллег", "личност"],
    weight: 4,
    label: "identity-and-voices terms",
  },
  {
    candidate: "Садхана инженерии",
    terms: ["принцип", "этик", "границ", "не должна", "цивилизац", "непрерывност"],
    weight: 4,
    label: "engineering-practice terms",
  },
  {
    candidate: "Инженерная метафизика",
    terms: ["памят", "коннектор", "провайдер", "runtime", "архитектур", "среда", "агент", "систем"],
    weight: 4,
    label: "system-and-memory terms",
  },
  {
    candidate: "Лаборатория граблей",
    terms: ["баг", "ошибк", "грабл", "incident", "сбой", "потер", "таймаут", "ключ", "кавычк"],
    weight: 3,
    label: "incident-and-lesson terms",
  },
  {
    candidate: "Квантовый чай",
    terms: ["чай", "квантов", "сарай", "утк", "миниатюр", "сцен"],
    weight: 3,
    label: "playful-miniature terms",
  },
];

function searchable(article) {
  return [article.title, article.status, article.origin, article.excerpt]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function planArticle(article) {
  const text = searchable(article);
  const scores = new Map();
  const evidence = new Map();

  for (const rule of keywordRules) {
    const hits = rule.terms.filter((term) => text.includes(term));
    if (hits.length) {
      scores.set(rule.candidate, (scores.get(rule.candidate) ?? 0) + rule.weight * hits.length);
      evidence.set(rule.candidate, [...(evidence.get(rule.candidate) ?? []), `${rule.label}: ${hits.join(", ")}`]);
    }
  }

  if (article.mode === "Heraclitus") {
    scores.set("Садхана инженерии", (scores.get("Садхана инженерии") ?? 0) + 3);
    evidence.set("Садхана инженерии", [...(evidence.get("Садхана инженерии") ?? []), "mode: Heraclitus"]);
  }
  if (article.origin?.toLowerCase().includes("incident")) {
    scores.set("Лаборатория граблей", (scores.get("Лаборатория граблей") ?? 0) + 2);
    evidence.set("Лаборатория граблей", [...(evidence.get("Лаборатория граблей") ?? []), "origin: incident"]);
  }
  if (article.origin?.toLowerCase().includes("family research")) {
    scores.set("Семейный архив", (scores.get("Семейный архив") ?? 0) + 4);
    evidence.set("Семейный архив", [...(evidence.get("Семейный архив") ?? []), "origin: family research project"]);
  }

  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]);
  const [topCandidate, topScore] = ranked[0] ?? ["needs_review", 0];
  const secondScore = ranked[1]?.[1] ?? 0;
  const confidence = topScore >= 8 && topScore - secondScore >= 3 ? "high" : topScore >= 4 ? "medium" : "low";
  const reviewRequired = topCandidate === "needs_review" || confidence === "low" || topScore - secondScore < 2;

  return {
    article: article.file,
    title: article.title,
    candidate_series: topCandidate,
    confidence,
    evidence: evidence.get(topCandidate) ?? [],
    alternative_series: ranked.slice(1, 3).map(([candidate]) => candidate),
    review_required: reviewRequired,
    rationale: "Draft heuristic from title, status, origin, excerpt and voice mode; no article files changed.",
  };
}

const articles = audit.articles.filter((article) => article.series.length === 0);
const plan = {
  generated_at: new Date().toISOString(),
  read_only: true,
  status: "draft",
  repository: audit.repository,
  source_audit: {
    journal_files: audit.journal_files,
    missing_series: articles.length,
  },
  series,
  articles: articles.map(planArticle),
};

if (jsonOutput) {
  console.log(JSON.stringify(plan, null, 2));
} else {
  console.log("BLOG METADATA PLAN (READ-ONLY DRAFT)");
  console.log(`articles without series: ${plan.articles.length}`);
  console.log(`review required: ${plan.articles.filter((article) => article.review_required).length}`);
  console.log("No journal files were changed.");
  console.log("\nCANDIDATES");
  for (const article of plan.articles) {
    console.log(`${article.article} | ${article.candidate_series} | ${article.confidence} | review=${article.review_required} | ${article.evidence.join("; ") || "no evidence"}`);
  }
}
