import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))

from tools.log_aggregator import JSONLogParser, TextLogParser, NginxLogParser


class TestJSONLogParser(unittest.TestCase):

    def setUp(self):
        self.parser = JSONLogParser()

    def test_independent_json_fixture(self):
        line = (FIXTURES / "json.log").read_text(encoding="utf-8").strip()

        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], "2026-09-19T14:30:00Z")
        self.assertEqual(result["level"], "ERROR")
        self.assertEqual(result["service"], "payments")
        self.assertEqual(result["message"], "Database connection failed")
        self.assertEqual(result["format"], "json")
        self.assertEqual(result["fields"]["request_id"], "req-123")

    def test_malformed_json_does_not_crash(self):
        line = (FIXTURES / "json-malformed.log").read_text(encoding="utf-8").strip()

        result = self.parser.parse(line)

        self.assertIsNone(result)


class TestTextLogParser(unittest.TestCase):

    def setUp(self):
        self.parser = TextLogParser()

    def test_independent_text_fixture(self):
        line = (FIXTURES / "text.log").read_text(encoding="utf-8").strip()

        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828200)
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["service"], "payments")
        self.assertEqual(result["format"], "text")
        self.assertEqual(result["message"], line)

    def test_unknown_level_is_supported(self):
        line = "2026-09-19 14:31:00 [payments] Connection attempt"

        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828260)
        self.assertEqual(result["level"], "unknown")
        self.assertEqual(result["service"], "payments")


class TestNginxLogParser(unittest.TestCase):

    def setUp(self):
        self.parser = NginxLogParser()

    def test_successful_request(self):
        line = (FIXTURES / "nginx.log").read_text(encoding="utf-8").strip()

        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828222)
        self.assertEqual(result["format"], "nginx")
        self.assertEqual(result["service"], "nginx")
        self.assertEqual(result["level"], "info")
        self.assertEqual(result["fields"]["status"], 200)
        self.assertEqual(
            result["fields"]["request"],
            "GET /api/users HTTP/1.1",
        )

    def test_client_error_is_warning(self):
        line = (
            '203.0.113.10 - - '
            '[19/Sep/2026:14:31:22 +0000] '
            '"GET /missing HTTP/1.1" '
            '404 512 "-" "Mozilla/5.0"'
        )

        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828282)
        self.assertEqual(result["level"], "warn")
        self.assertEqual(result["service"], "nginx")
        self.assertEqual(result["format"], "nginx")
        self.assertEqual(result["fields"]["status"], 404)

    def test_server_error_is_error(self):
        line = (
            '203.0.113.10 - - '
            '[19/Sep/2026:14:32:22 +0000] '
            '"GET /api/health HTTP/1.1" '
            '500 256 "-" "Mozilla/5.0"'
        )

        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828342)
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["service"], "nginx")
        self.assertEqual(result["format"], "nginx")
        self.assertEqual(result["fields"]["status"], 500)

    def test_malformed_nginx_line_does_not_crash(self):
        line = (FIXTURES / "nginx-malformed.log").read_text(encoding="utf-8").strip()

        result = self.parser.parse(line)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
