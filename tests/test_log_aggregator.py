import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))

from tools.log_aggregator import (
    JSONLogParser,
    TextLogParser,
    NginxLogParser,
    LogAggregator,
)


class TestJSONLogParser(unittest.TestCase):

    def setUp(self):
        self.parser = JSONLogParser()

    def test_standard_timestamp_and_level(self):
        line = '{"timestamp":"2026-09-19T14:30:00Z","level":"ERROR","service":"payments","message":"Database connection failed","request_id":"req-123"}'
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828200)
        self.assertEqual(result["level"], "ERROR")
        self.assertEqual(result["service"], "payments")
        self.assertEqual(result["message"], "Database connection failed")
        self.assertEqual(result["format"], "json")
        self.assertEqual(result["fields"]["request_id"], "req-123")

    def test_time_field_and_msg(self):
        line = '{"time":"2026-09-19T14:31:00+00:00","level":"INFO","service":"auth","msg":"User login successful","user_id":"u-456"}'
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828260)
        self.assertEqual(result["level"], "INFO")
        self.assertEqual(result["service"], "auth")
        self.assertEqual(result["message"], "User login successful")
        self.assertIn("user_id", result["fields"])

    def test_timestamp_field_and_severity(self):
        line = '{"@timestamp":"2026-09-19T14:32:00Z","severity":"WARN","logger":"cache","message":"Cache miss for key session_789","ttl":300}'
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828320)
        self.assertEqual(result["level"], "WARN")
        self.assertEqual(result["service"], "cache")
        self.assertEqual(result["format"], "json")

    def test_malformed_json_returns_none(self):
        malformed = (FIXTURES / "json-malformed.log").read_text(encoding="utf-8")
        for line in malformed.strip().splitlines():
            result = self.parser.parse(line.strip())
            self.assertIsNone(result, f"Expected None for malformed line: {line!r}")

    def test_empty_json_returns_none(self):
        self.assertIsNone(self.parser.parse(""))
        self.assertIsNone(self.parser.parse("   "))

    def test_non_dict_json_returns_none(self):
        self.assertIsNone(self.parser.parse("[1, 2, 3]"))
        self.assertIsNone(self.parser.parse('"just a string"'))
        self.assertIsNone(self.parser.parse("42"))


class TestTextLogParser(unittest.TestCase):

    def setUp(self):
        self.parser = TextLogParser()

    def test_standard_timestamp_error_level(self):
        line = "2026-09-19 14:30:00 ERROR [payments] Database connection failed"
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828200)
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["service"], "payments")
        self.assertEqual(result["format"], "text")
        self.assertEqual(result["message"], line)

    def test_info_level(self):
        line = "2026-09-19 14:31:00 INFO [auth] User login successful"
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828260)
        self.assertEqual(result["level"], "info")
        self.assertEqual(result["service"], "auth")

    def test_warning_level(self):
        line = "2026-09-19 14:32:00 WARNING [cache] Cache miss for key session_789"
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["level"], "warn")
        self.assertEqual(result["service"], "cache")

    def test_unknown_level_is_supported(self):
        line = "2026-09-19 14:33:00 NOTICE [db] Connection pool refreshed"
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["level"], "info")

    def test_no_timestamp_returns_none_ts(self):
        line = "[payments] Something happened"
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertIsNone(result["timestamp"])

    def test_empty_line_returns_none(self):
        self.assertIsNone(self.parser.parse(""))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(self.parser.parse("   \t  "))

    def test_malformed_text_does_not_crash(self):
        malformed = (FIXTURES / "text-malformed.log").read_text(encoding="utf-8")
        for line in malformed.strip().splitlines():
            stripped = line.strip()
            if stripped:
                result = self.parser.parse(stripped)
                self.assertIsNotNone(result)


class TestNginxLogParser(unittest.TestCase):

    def setUp(self):
        self.parser = NginxLogParser()

    def test_successful_request(self):
        line = '203.0.113.10 - - [19/Sep/2026:14:30:22 +0000] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"'
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828222)
        self.assertEqual(result["format"], "nginx")
        self.assertEqual(result["service"], "nginx")
        self.assertEqual(result["level"], "info")
        self.assertEqual(result["fields"]["status"], 200)
        self.assertEqual(result["fields"]["request"], "GET /api/users HTTP/1.1")
        self.assertEqual(result["fields"]["remote_addr"], "203.0.113.10")
        self.assertEqual(result["fields"]["remote_user"], "-")
        self.assertEqual(result["fields"]["body_bytes"], "1234")
        self.assertEqual(result["fields"]["referer"], "-")
        self.assertEqual(result["fields"]["user_agent"], "Mozilla/5.0")

    def test_post_request_with_user(self):
        line = '198.51.100.5 - admin [19/Sep/2026:14:31:22 +0000] "POST /api/orders HTTP/1.1" 201 567 "https://shop.example.com" "curl/7.68.0"'
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828282)
        self.assertEqual(result["level"], "info")
        self.assertEqual(result["fields"]["status"], 201)
        self.assertEqual(result["fields"]["remote_user"], "admin")
        self.assertEqual(result["fields"]["request"], "POST /api/orders HTTP/1.1")
        self.assertEqual(result["fields"]["body_bytes"], "567")
        self.assertEqual(result["fields"]["referer"], "https://shop.example.com")

    def test_server_error_is_error(self):
        line = '10.0.0.1 - - [19/Sep/2026:14:32:22 +0000] "GET /api/health HTTP/1.1" 500 256 "-" "monitoring/1.0"'
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828342)
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["fields"]["status"], 500)

    def test_client_error_is_warning(self):
        line = '203.0.113.10 - - [19/Sep/2026:14:33:22 +0000] "GET /missing HTTP/1.1" 404 512 "-" "Mozilla/5.0"'
        result = self.parser.parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["timestamp"], 1789828402)
        self.assertEqual(result["level"], "warn")
        self.assertEqual(result["fields"]["status"], 404)

    def test_malformed_nginx_returns_none(self):
        malformed = (FIXTURES / "nginx-malformed.log").read_text(encoding="utf-8")
        for line in malformed.strip().splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            result = self.parser.parse(stripped)
            if stripped.startswith(("this ", "---")):
                self.assertIsNone(result, f"Expected None for malformed line: {stripped!r}")
            elif "invalid-date" in stripped:
                self.assertIsNotNone(result)
                self.assertIsNone(result["timestamp"])

    def test_empty_line_returns_none(self):
        self.assertIsNone(self.parser.parse(""))

    def test_non_nginx_returns_none(self):
        self.assertIsNone(self.parser.parse("plain text without nginx format"))


class TestAggregatorIntegration(unittest.TestCase):

    def test_all_fixtures_parse_without_crash(self):
        agg = LogAggregator()
        fixture_files = list(FIXTURES.glob("*.log"))
        self.assertGreater(len(fixture_files), 0)

        for f in fixture_files:
            count = agg.process_file(str(f))
            self.assertIsInstance(count, int)

        summary = agg.get_summary()
        self.assertIn("total_entries", summary)
        self.assertIn("by_level", summary)
        self.assertIn("by_service", summary)
        self.assertIn("error_rate", summary)

    def test_aggregator_exports_json(self):
        agg = LogAggregator()
        agg.process_file(str(FIXTURES / "json.log"))
        agg.process_file(str(FIXTURES / "text.log"))
        agg.process_file(str(FIXTURES / "nginx.log"))

        out = ROOT / "tests" / "test_report_output.json"
        try:
            agg.export_json(str(out))
            self.assertTrue(out.exists())
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("summary", data)
            self.assertIn("entries", data)
        finally:
            out.unlink(missing_ok=True)

    def test_aggregator_search(self):
        agg = LogAggregator()
        agg.process_file(str(FIXTURES / "json.log"))
        results = agg.search("Database")
        self.assertGreater(len(results), 0)
        self.assertIn("Database", results[0]["message"])

    def test_malformed_fixtures_do_not_crash_aggregator(self):
        agg = LogAggregator()
        for name in ["json-malformed.log", "nginx-malformed.log", "text-malformed.log"]:
            path = FIXTURES / name
            if path.exists():
                agg.process_file(str(path))

        summary = agg.get_summary()
        self.assertIsInstance(summary["total_entries"], int)

    def test_mixed_format_processing(self):
        agg = LogAggregator()
        agg.process_file(str(FIXTURES / "json.log"))
        agg.process_file(str(FIXTURES / "text.log"))
        agg.process_file(str(FIXTURES / "nginx.log"))

        breakdown = agg.get_service_breakdown()
        self.assertIn("payments", breakdown)
        self.assertIn("nginx", breakdown)

    def test_error_timeline(self):
        agg = LogAggregator()
        agg.process_file(str(FIXTURES / "json.log"))
        agg.process_file(str(FIXTURES / "nginx.log"))

        timeline = agg.get_error_timeline()
        self.assertIsInstance(timeline, list)
        for entry in timeline:
            self.assertIn("hour", entry)
            self.assertIn("count", entry)


if __name__ == "__main__":
    unittest.main()
