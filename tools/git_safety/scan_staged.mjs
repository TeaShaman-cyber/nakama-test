import { execFileSync } from "node:child_process";
import { basename } from "node:path";

function git(args, options = {}) {
  return execFileSync("git", args, { encoding: "utf8", ...options });
}

const names = git(["diff", "--cached", "--name-only", "-z"])
  .split("\0")
  .filter(Boolean);

const forbiddenName = /(^|\/)(\.env(?:\..*)?|.*\.(?:pem|key|p12|pfx)|.*(?:secret|credential|password).*)$/i;
const secretPatterns = [
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
  /(?:ghp|github_pat)_[A-Za-z0-9_]{20,}/,
  /sk-[A-Za-z0-9_-]{20,}/,
  /Bearer\s+[A-Za-z0-9._-]{24,}/i,
  /(?:password|passwd|secret)\s*[:=]\s*["']?[^\s"']{8,}/i,
];

const failures = [];
for (const name of names) {
  if (forbiddenName.test(name)) {
    failures.push(`${name}: forbidden secret-like filename`);
    continue;
  }

  let content;
  try {
    content = git(["show", `:${name}`], { maxBuffer: 2 * 1024 * 1024 });
  } catch {
    failures.push(`${name}: unable to read staged content`);
    continue;
  }

  for (const pattern of secretPatterns) {
    if (pattern.test(content)) {
      failures.push(`${name}: matched ${pattern}`);
    }
  }
}

if (failures.length > 0) {
  console.error("STAGED SAFETY CHECK: FAILED");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`STAGED SAFETY CHECK: PASS (${names.length} file${names.length === 1 ? "" : "s"})`);
