import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import process from "node:process";

const root = process.cwd();
const args = process.argv.slice(2);
const action = args[0] ?? "status";

function run(command, commandArgs, options = {}) {
  console.log(`> ${command} ${commandArgs.join(" ")}`);
  return execFileSync(command, commandArgs, {
    cwd: root,
    stdio: "inherit",
    encoding: "utf8",
    ...options,
  });
}

function output(command, commandArgs) {
  return execFileSync(command, commandArgs, {
    cwd: root,
    encoding: "utf8",
  }).trimEnd();
}

function gitStatus() {
  return output("git", ["status", "--porcelain=v1"]);
}

function allowedPath(path) {
  return path === "journal/README.md" || /^journal\/\d{4}-\d{2}-\d{2}-[^/]+\.md$/i.test(path);
}

function changedPaths(status) {
  return status
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => line.slice(3).replaceAll("\\", "/"));
}

function assertPublishScope() {
  const branch = output("git", ["branch", "--show-current"]);
  if (branch !== "main") {
    throw new Error(`Publish stopped: expected branch main, got ${branch || "detached HEAD"}.`);
  }
  const status = gitStatus();
  if (!status) {
    throw new Error("No local journal changes to publish.");
  }
  const paths = changedPaths(status);
  const unexpected = paths.filter((path) => !allowedPath(path));
  if (unexpected.length > 0) {
    throw new Error(
      `Publish stopped: unexpected changed paths:\n${unexpected.join("\n")}`,
    );
  }
  if (paths.some((path) => /(^|\/)(\.env|\.env\.|.*\.pem$|.*\.key$)/i.test(path))) {
    throw new Error("Publish stopped: secret-like file in the publish scope.");
  }
  return paths;
}

function verify() {
  run("ruff", ["check", "blogsite"]);
  run("ruff", ["format", "--check", "blogsite"]);
  run("python", ["-m", "unittest", "discover", "-s", "blogsite/tests", "-v"]);
  run("python", ["-m", "blogsite.build", "--repo-root", ".", "--output", "public", "--base-path", "/nakama-test/"]);
  run("git", ["diff", "--check"]);
}

function publish() {
  const paths = assertPublishScope();
  verify();
  run("git", ["add", "--", ...paths]);
  run("git", ["diff", "--cached", "--check"]);
  run("git", ["diff", "--cached", "--name-only"]);
  run("git", ["commit", "-m", "journal: publish local Pages update"]);
  run("git", ["push", "origin", "main"]);
}

function status() {
  run("git", ["status", "--short", "--branch"]);
  run("git", ["log", "-1", "--oneline"]);
  run("git", ["ls-remote", "origin", "refs/heads/main"]);
}

if (!existsSync(`${root}/.git`)) {
  throw new Error("This task must run from the blog Git checkout.");
}

if (action === "verify") verify();
else if (action === "publish") publish();
else if (action === "status") status();
else throw new Error(`Unknown Pages task: ${action}`);
