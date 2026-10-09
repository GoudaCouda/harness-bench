import io
import unittest
from http.client import parse_headers

from src.trace_context import propagate_contexts


POLICY = {
    "vendor_key": "acme",
    "sensitive_baggage_keys": ["user.id"],
    "max_tracestate_entries": 8,
    "max_baggage_entries": 8,
}


class HTTPHeaderIntegrationTests(unittest.TestCase):
    def test_stdlib_parsed_duplicate_header_is_not_silently_collapsed(self):
        raw = (
            b"traceparent: 00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-00\r\n"
            b"baggage: user.id=7,tenant=blue\r\n"
            b"\r\n"
        )
        headers = parse_headers(io.BytesIO(raw))
        request = {
            "request_id": "http-capture",
            "traceparent": headers.get_all("traceparent", []),
            "tracestate": headers.get_all("tracestate", []),
            "baggage": headers.get_all("baggage", []),
            "participate": False,
            "boundary": "external",
            "local_parent_id": "1111111111111111",
            "fallback_trace_id": "22222222222222222222222222222222",
            "vendor_value": "capture",
            "sampled": False,
        }
        decision = propagate_contexts([request], POLICY)["decisions"][0]
        self.assertEqual(decision["disposition"], "forwarded")
        self.assertEqual(decision["baggage"], "tenant=blue")


if __name__ == "__main__":
    unittest.main()
