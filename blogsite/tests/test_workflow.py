import unittest
from pathlib import Path


class WorkflowTests(unittest.TestCase):
    def test_pages_workflow_has_separate_build_and_deploy_jobs(self):
        workflow = Path(".github/workflows/pages.yml")
        self.assertTrue(workflow.exists(), "missing Pages workflow")
        text = workflow.read_text(encoding="utf-8")
        required = [
            "actions/checkout@v6",
            "actions/setup-python@v6",
            "actions/configure-pages@v5",
            "actions/upload-pages-artifact@v4",
            "actions/deploy-pages@v4",
            "needs: build",
            "name: github-pages",
            "pages: write",
            "id-token: write",
            'python-version: "3.13"',
            "path: public",
            "./tools/dev/check public",
        ]
        for fragment in required:
            self.assertIn(fragment, text)

    def test_build_job_does_not_receive_deploy_permissions(self):
        text = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
        build = text.split("  deploy:", 1)[0]
        self.assertIn("contents: read", build)
        self.assertNotIn("pages: write", build)
        self.assertNotIn("id-token: write", build)

    def test_article_advisory_workflow_is_read_only_pinned_and_receipt_driven(self):
        path = Path(".github/workflows/article-advisory.yml")
        self.assertTrue(path.exists(), "missing article advisory workflow")
        text = path.read_text(encoding="utf-8")
        required = [
            "permissions:\n  contents: read",
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",
            "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            'node-version: "24.20.0"',
            "continue-on-error: true",
            "persist-credentials: false",
            "github.event.pull_request.head.repo.full_name == github.repository",
            "tools/article_network_qa.py",
            "receipts/article-network",
        ]
        for fragment in required:
            self.assertIn(fragment, text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("contents: write", text)

    def test_network_advisory_uses_pinned_public_mcporter_routes(self):
        package = Path("mcp/package.json").read_text(encoding="utf-8")
        config = Path("mcp/config.ci.json").read_text(encoding="utf-8")
        manifest = Path("qa/network/article-advisory.json").read_text(encoding="utf-8")
        self.assertIn('"mcporter": "0.13.8"', package)
        self.assertIn("https://agenttools.wolfram.com/mcp", config)
        self.assertIn("https://mcp.exa.ai/mcp", config)
        self.assertIn("https://search.parallel.ai/mcp", config)
        self.assertIn("raw.githubusercontent.com/github/docs/main", manifest)

    def test_article_mutation_reuses_current_cookbook_runner(self):
        path = Path(".github/workflows/article-mutation.yml")
        self.assertTrue(path.exists(), "missing article mutation workflow")
        text = path.read_text(encoding="utf-8")
        required = [
            "permissions:\n  contents: read",
            "reusable-mutation-test.yml@db03f5b1234f8a12244a0f513ed84dd976eb4051",
            "requirements/ci-article-mutation.txt",
            "tools/ci/article-mutation-test",
        ]
        for fragment in required:
            self.assertIn(fragment, text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("contents: write", text)
