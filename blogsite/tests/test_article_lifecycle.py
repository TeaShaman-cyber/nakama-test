import copy
import unittest

from tools.article_lifecycle import (
    ARTICLE_STATES,
    FORUM_STATES,
    forum_payload,
    load_receipt,
    publication_state,
    resolve_article,
    status_payload,
    validate,
)


ARTICLE = "2026-09-22-readme-byl-velikolepen-sistema-ne-rabotala"


class ArticleLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.article = resolve_article(ARTICLE)
        self.receipt = load_receipt(self.article)

    def test_current_specimen_has_consistent_publication_contract(self):
        self.assertIn(publication_state(self.article), ARTICLE_STATES)
        self.assertEqual(validate(self.article, self.receipt), [])
        status = status_payload(self.article)
        self.assertEqual(status["qa"]["state"], "PASS")
        self.assertIn(
            status["next_action"],
            {
                "editorial_review",
                "explicit_promote_to_published",
                "verify_pages",
                "forum_companion_review",
                "explicit_forum_publish",
                "reconcile_forum_receipt",
                "complete",
            },
        )

    def test_forum_payload_is_bound_to_canonical_pages_url(self):
        payload = forum_payload(self.article)
        pages = self.receipt["surfaces"]["pages"]
        self.assertEqual(payload["url"], pages["expected_url"])
        self.assertIn(payload["status"], FORUM_STATES)
        self.assertTrue(payload["title"])
        self.assertIn("observation pipeline", payload["body"])

    def test_mismatched_pages_url_fails_validation(self):
        broken = copy.deepcopy(self.receipt)
        broken["surfaces"]["pages"]["expected_url"] = "https://example.invalid/wrong/"
        errors = validate(self.article, broken)
        self.assertIn("pages expected_url does not match article slug", errors)
