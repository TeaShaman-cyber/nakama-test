import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const publicDir = join(root, "public");
const metadata = JSON.parse(readFileSync(join(root, "blogsite/metadata.json"), "utf8"));
const seriesNames = [...new Set(Object.values(metadata.articles ?? {}).flatMap((row) => row.series ?? []))].sort();
const seriesDirs = existsSync(join(publicDir, "series"))
  ? readdirSync(join(publicDir, "series"), { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort()
  : [];
const home = readFileSync(join(publicDir, "index.html"), "utf8");
const journal = readFileSync(join(publicDir, "journal/index.html"), "utf8");
const articleFiles = [];
function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) walk(path);
    else if (
      entry.name === "index.html" &&
      path.includes(`${join("public", "journal")}`) &&
      path !== join(publicDir, "journal", "index.html")
    ) articleFiles.push(path);
  }
}
walk(publicDir);

const articleSeriesLinkCount = articleFiles.filter((path) => /href="[^"]*\/series\/[^"]+"/.test(readFileSync(path, "utf8"))).length;
const indexSeriesLinkCount = [home, journal].reduce((count, html) => count + (html.match(/href="[^"]*\/series\/[^"]+"/g) ?? []).length, 0);
const seriesPages = seriesDirs.map((dir) => ({
  directory: dir,
  exists: existsSync(join(publicDir, "series", dir, "index.html")),
  cards: existsSync(join(publicDir, "series", dir, "index.html"))
    ? (readFileSync(join(publicDir, "series", dir, "index.html"), "utf8").match(/class="entry-card"/g) ?? []).length
    : 0,
}));

const report = {
  read_only: true,
  article_pages: articleFiles.length,
  metadata_series: seriesNames.length,
  generated_series_pages: seriesPages.length,
  series_pages: seriesPages,
  article_pages_with_series_links: articleSeriesLinkCount,
  index_series_links: indexSeriesLinkCount,
  gaps: [],
};
if (seriesNames.length !== seriesDirs.length) report.gaps.push("metadata_and_generated_series_count_differ");
if (seriesPages.some((page) => !page.exists)) report.gaps.push("missing_series_page");
if (seriesPages.some((page) => page.cards === 0)) report.gaps.push("empty_series_page");
if (indexSeriesLinkCount === 0) report.gaps.push("home_and_journal_cards_do_not_link_to_series");
if (articleSeriesLinkCount !== articleFiles.length) report.gaps.push("some_article_pages_do_not_link_to_series");

console.log("BLOG NAVIGATION AUDIT (READ-ONLY)");
console.log(`article pages: ${report.article_pages}`);
console.log(`metadata series: ${report.metadata_series}`);
console.log(`generated series pages: ${report.generated_series_pages}`);
console.log(`article pages with series links: ${report.article_pages_with_series_links}/${report.article_pages}`);
console.log(`series links on home + journal indexes: ${report.index_series_links}`);
console.log(`gaps: ${report.gaps.length ? report.gaps.join(", ") : "none"}`);
for (const page of report.series_pages) console.log(`series/${page.directory}: ${page.cards} cards`);
