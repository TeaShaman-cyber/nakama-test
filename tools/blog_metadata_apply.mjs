import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import process from "node:process";

const root = process.cwd();
const dryRun = process.argv.includes("--dry-run");
const plan = JSON.parse(
  execFileSync(process.execPath, ["tools/blog_metadata_plan.mjs", "--json"], {
    cwd: root,
    encoding: "utf8",
  }),
);
const metadataPath = join(root, "blogsite/metadata.json");
const metadata = JSON.parse(readFileSync(metadataPath, "utf8"));

if (plan.status !== "draft" || plan.articles.some((article) => article.review_required)) {
  throw new Error("Metadata apply stopped: the plan is not fully reviewed.");
}

for (const article of plan.articles) {
  if (!existsSync(join(root, "journal", article.article))) {
    throw new Error(`Metadata apply stopped: article is missing: ${article.article}`);
  }
  if (!article.candidate_series || article.candidate_series === "needs_review") {
    throw new Error(`Metadata apply stopped: empty series for ${article.article}`);
  }
}

const next = {
  ...metadata,
  articles: { ...metadata.articles },
};
for (const article of plan.articles) {
  next.articles[article.article] = { series: [article.candidate_series] };
}

const output = `${JSON.stringify(next, null, 2)}\n`;
if (dryRun) {
  console.log(`BLOG METADATA APPLY (DRY-RUN): ${plan.articles.length} article series would be updated`);
} else {
  writeFileSync(metadataPath, output, "utf8");
  console.log(`BLOG METADATA APPLY: updated ${plan.articles.length} article series`);
}

console.log("Changed file: blogsite/metadata.json");
console.log("Journal files changed: 0");
