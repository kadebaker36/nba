"""Protect workbook state when regenerating policy and provenance."""
import unittest

from export_method import build_requests
from method_policy import sheet_rows


class MethodMirrorTests(unittest.TestCase):
    def test_policy_mirror_never_writes_snapshot_or_pick_rows(self):
        revision = {"method_committed": True, "method_commit": "a" * 40,
                    "method_source": "https://example.invalid/METHOD.md", "method_sha256": "b" * 64}
        requests = build_requests(123, revision)
        policy = {r[0] for r in sheet_rows()}
        touched = set()
        for request in requests:
            update = request["updateCells"]
            target = update["range"]
            self.assertEqual(target["sheetId"], 123)
            self.assertEqual(update["fields"], "userEnteredValue")
            touched.update(range(target["startRowIndex"] + 1, target["endRowIndex"] + 1))
        self.assertEqual(touched, policy | {54, 55, 56})
        self.assertTrue(touched.isdisjoint({6, 8, 21, 27, 28, 29, 30}))

    def test_uncommitted_method_cannot_be_exported_as_authoritative(self):
        with self.assertRaises(ValueError):
            build_requests(123, {"method_committed": False, "method_commit": None})


if __name__ == "__main__":
    unittest.main()
