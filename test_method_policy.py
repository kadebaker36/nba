"""Protect workbook state when regenerating policy and provenance."""
import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from io import BytesIO

from export_method import build_requests
from method_policy import sheet_rows, metadata


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

    def test_declared_commit_alone_cannot_certify_downloaded_content(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'METHOD.md'
            path.write_text('Changed policy')
            with patch.dict(os.environ, {'BBB_METHOD_COMMIT': 'a'*40}):
                info = metadata(path)
                self.assertFalse(info['method_committed'])
                with self.assertRaises(ValueError):
                    build_requests(123, info)
                with patch('method_policy.urllib.request.urlopen', return_value=BytesIO(b'Original policy')):
                    with self.assertRaises(ValueError):
                        metadata(path, verify_remote=True)
                with patch('method_policy.urllib.request.urlopen', return_value=BytesIO(b'Changed policy')):
                    self.assertTrue(metadata(path, verify_remote=True)['method_committed'])

    def test_policy_cannot_overwrite_a_snapshot_row(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'METHOD.md'
            path.write_text('## Coverage\n<!-- sheet-row: 8 -->\n\nAccidental overwrite\n')
            with self.assertRaises(ValueError):
                sheet_rows(path)


if __name__ == "__main__":
    unittest.main()
