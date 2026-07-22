from pathlib import Path
import unittest


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
        ]
        for fragment in required:
            self.assertIn(fragment, text)

    def test_build_job_does_not_receive_deploy_permissions(self):
        text = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
        build = text.split("  deploy:", 1)[0]
        self.assertIn("contents: read", build)
        self.assertNotIn("pages: write", build)
        self.assertNotIn("id-token: write", build)
