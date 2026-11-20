"""Verify raw UTF-8 references; preserve entities, whitespace and newline bytes."""
import hashlib
import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import relay_artifact as r


class ArtifactTests(unittest.TestCase):
    def test_exact_unicode_entity_and_newline_integrity(self):
        base = 'literal: &amp;\nunicode: café 🏀 → Δ\nline one\nline two'.encode()
        with tempfile.TemporaryDirectory() as tmp:
            for number, raw in enumerate((base, base+b'\n', base.replace(b'\n', b'\r\n'))):
                file = Path(tmp)/str(number)
                result = r.create(file, raw)
                self.assertEqual(result, dict(utf8_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
                self.assertEqual(r.verify(file, result['utf8_bytes'], result['sha256']), raw)
                with self.assertRaises(FileExistsError): r.create(file, raw)
                self.assertEqual(file.read_bytes(), raw)
            self.assertEqual(len({r.fingerprint(raw)['sha256'] for raw in (base, base+b'\n', base.replace(b'\n', b'\r\n'))}), 3)

    def test_private_creation_and_read_only_completion_under_permissive_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'private-order'
            seen = []
            chmod = os.fchmod
            def record_mode(fd, mode):
                seen.append(stat.S_IMODE(os.fstat(fd).st_mode))
                chmod(fd, mode)
            previous = os.umask(0)
            try:
                with patch.object(r.os, 'fchmod', side_effect=record_mode):
                    r.create(file, b'private canonical bytes')
            finally:
                os.umask(previous)
            self.assertEqual(seen, [0o600])
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o400)
            self.assertEqual(file.read_bytes(), b'private canonical bytes')

    def test_count_hash_mismatch_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'message';r.create(file, b'&amp;')
            digest = hashlib.sha256(b'&amp;').hexdigest()
            for count, sha in ((4, digest), (5, '0'*64), (True, digest)):
                with self.assertRaises(ValueError): r.verify(file, count, sha)
            with self.assertRaises(FileNotFoundError): r.verify(Path(tmp)/'absent', 0, '0'*64)
            with self.assertRaises(UnicodeError): r.create(Path(tmp)/'invalid', b'\xff')
            self.assertFalse((Path(tmp)/'invalid').exists())

    def test_cli_error_and_success_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'message';file.write_bytes('café &amp;\r\n'.encode())
            receipt = r.fingerprint(file.read_bytes())
            args = ['verify', str(file), '--bytes', str(receipt['utf8_bytes']), '--sha256', receipt['sha256']]
            with redirect_stdout(io.StringIO()) as output: code = r.main(args)
            self.assertEqual(code, 0);self.assertEqual(json.loads(output.getvalue())['state'], 'verified')
            file.unlink()
            with redirect_stdout(io.StringIO()) as output: code = r.main(args)
            self.assertEqual(code, 2);self.assertEqual(json.loads(output.getvalue())['state'], 'error')


if __name__ == '__main__':
    unittest.main()
