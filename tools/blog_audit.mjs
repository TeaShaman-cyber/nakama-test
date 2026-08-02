import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import process from "node:process";

const root = process.cwd();
const journalDir = join(root, "journal");
const jsonOutput = process.argv.includes("--json");
const metadataPath = join(root, "blogsite", "metadata.json");
const metadata = JSON.parse(readFileSync(metadataPath, "utf8"));
const seriesByFile = metadata.articles ?? {};

function field(text, name) {
  const match = text.match(new RegExp(`^${name}:\\s*(.+)$`, "m"));
  return match?.[1]?.trim() ?? null;
}

function title(text) {
  return text.match(/^# (.+)$/m)?.[1]?.trim() ?? null;
}

function excerpt(text) {
  const body = text
    .replace(/```[\\s\\S]*?```/g, "")
    .split(/\r?\n\r?\n/)
    .map((part) => part.trim())
    .filter((part) => part && !part.startsWith("#") && !part.startsWith(">"))
    .find(Boolean);
  return body ?? "";
}

function words(text) {
  return (text.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu) ?? []).length;
}

const indexText = readFileSync(join(journalDir, "README.md"), "utf8");
const indexLinks = new Set(
  [...indexText.matchAll(/\]\((\d{4}-\d{2}-\d{2}-[^)]+\.md)\)/g)].map(
    (match) => match[1],
  ),
);

const files = readdirSync(journalDir)
  .filter((name) => name !== "README.md" && name.toLowerCase().endsWith(".md"))
  .sort();

const articles = files.map((file) => {
  const text = readFileSync(join(journalDir, file), "utf8");
  const mode = field(text, "Mode");
  const voice = field(text, "Voice");
  const row = {
    file,
    title: title(text),
    date: field(text, "Date"),
    mode,
    voice,
    status: field(text, "Status"),
    origin: field(text, "Origin"),
    series: seriesByFile[file]?.series ?? [],
    words: words(text),
    excerpt: excerpt(text).slice(0, 240),
    in_index: indexLinks.has(file),
    markdown_links: [...text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)].map(
      (match) => match[1],
    ),
    metadata_gaps: [],
  };
  if (!row.title) row.metadata_gaps.push("missing_title");
  if (!row.date) row.metadata_gaps.push("missing_date");
  if (!row.mode) row.metadata_gaps.push("missing_mode");
  if (!row.status) row.metadata_gaps.push("missing_status");
  if (row.mode === "joint note" && !row.voice) row.metadata_gaps.push("joint_note_missing_voice");
  if (!row.in_index) row.metadata_gaps.push("missing_index_link");
  if (row.series.length === 0) row.metadata_gaps.push("missing_series");
  return row;
});

const gapCounts = {};
for (const article of articles) {
  for (const gap of article.metadata_gaps) gapCounts[gap] = (gapCounts[gap] ?? 0) + 1;
}

const report = {
  generated_at: new Date().toISOString(),
  read_only: true,
  repository: "TeaShaman-cyber/nakama-test",
  journal_files: files.length,
  index_links: indexLinks.size,
  index_missing_files: files.filter((file) => !indexLinks.has(file)),
  index_orphans: [...indexLinks].filter((file) => !files.includes(file)),
  total_words: articles.reduce((sum, article) => sum + article.words, 0),
  series_counts: Object.fromEntries(
    [...new Set(articles.flatMap((article) => article.series))].map((series) => [
      series,
      articles.filter((article) => article.series.includes(series)).length,
    ]),
  ),
  gap_counts: gapCounts,
  articles,
};

if (jsonOutput) {
  console.log(JSON.stringify(report, null, 2));
} else {
  console.log("BLOG AUDIT (READ-ONLY)");
  console.log(`articles: ${report.journal_files}`);
  console.log(`index links: ${report.index_links}`);
  console.log(`total words: ${report.total_words}`);
  console.log(`index missing files: ${report.index_missing_files.length}`);
  console.log(`index orphan links: ${report.index_orphans.length}`);
  console.log(`metadata gaps: ${JSON.stringify(report.gap_counts)}`);
  console.log("\nARTICLES");
  for (const article of articles) {
    const gaps = article.metadata_gaps.length ? article.metadata_gaps.join(",") : "OK";
    console.log(`${article.file} | ${article.date ?? "?"} | ${article.mode ?? "?"} | series=${article.series.join(",") || "-"} | ${gaps}`);
  }
}
