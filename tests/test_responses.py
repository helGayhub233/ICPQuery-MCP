from __future__ import annotations

import copy
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from icpquery_mcp.core.client import CaptchaResult, ICPQueryClient, _normalize_response
from icpquery_mcp.core.config import Config
from icpquery_mcp.core.errors import QueryError
from icpquery_mcp.models import ICPQueryResponse
from icpquery_mcp.responses import MAX_OUTPUT_BYTES, render_json, tool_result


def page(*, total=3, count=2, page_number=1, page_size=2, **extra):
    return {"success": True, "code": 200, "params": {
        "list": [{"dataId": str(index), "domain": "example.test"} for index in range(count)],
        "total": total, "pageNum": page_number, "pageSize": page_size, **extra,
    }}


class ResponseTests(unittest.TestCase):
    def test_business_errors_never_claim_completeness_or_request_next_page(self):
        for code in (403, 500, "500"):
            for total in (0, 100):
                with self.subTest(code=code, total=total):
                    body = page(total=total, count=0)
                    body.update(success=False, code=code)
                    result = tool_result(body, query=True)
                    self.assertTrue(result.is_error)
                    payload = result.structured_content
                    self.assertFalse(payload["success"])
                    self.assertEqual(payload["error"]["type"], "provider_error")
                    self.assertEqual(payload["completeness"], "unknown")
                    self.assertEqual(payload["next_action"], "stop")
                    self.assertEqual(payload["returned_count"], 0)
                    if str(code) == "500":
                        self.assertEqual(payload["code"], 122)
                        self.assertEqual(payload["error"]["details"]["provider_code"], 500)

    def test_missing_or_invalid_business_status_is_not_success(self):
        for body in (None, [], {}, {"params": {"list": [], "total": 0}},
                     {"success": True, "code": False}, {"success": True, "code": "not-a-code"}):
            with self.subTest(body=body):
                payload = _normalize_response(body)
                self.assertFalse(payload["success"])
                self.assertEqual(payload["error"]["type"], "invalid_response")
                self.assertEqual(payload["next_action"], "stop")

    def test_contradictory_pagination_keeps_the_positive_more_signal(self):
        body = page(total=100, count=1, page_size=26, hasNext=False)
        result = _normalize_response(body)
        self.assertEqual(result["completeness"], "partial")
        self.assertEqual(result["next_action"], "call_next_page")
        self.assertEqual(result["warnings"][0]["type"], "pagination_conflict")
        self.assertEqual(_normalize_response(result), result)

    def test_actual_returned_count_controls_short_page_continuation(self):
        result = _normalize_response(page(total=20, count=1, page_size=26))
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["next_action"], "call_next_page")

    def test_empty_success_and_known_last_page_are_complete(self):
        for body in (page(total=0, count=0), page(total=3, count=1, page_number=2)):
            with self.subTest(body=body):
                result = _normalize_response(body)
                self.assertEqual(result["completeness"], "complete")
                self.assertEqual(result["next_action"], "stop")

    def test_invalid_or_unknown_pagination_does_not_invent_an_offset(self):
        for metadata in ({}, {"total": False, "pageNum": True, "pageSize": -1}, {"total": 100}):
            with self.subTest(metadata=metadata):
                result = _normalize_response({"success": True, "params": {"list": [{}], **metadata}})
                self.assertEqual(result["completeness"], "unknown")
                self.assertNotIn("page", result)
                self.assertNotIn("page_size", result)

    def test_impossible_total_does_not_claim_a_complete_result(self):
        result = _normalize_response(page(total=0, count=1, hasNext=False))
        self.assertEqual(result["completeness"], "unknown")
        self.assertEqual(result["next_action"], "unknown")

    def test_public_output_keeps_a_bounded_prefix_and_does_not_advance_pages(self):
        body = page(total=26, count=26, page_size=26)
        for record in body["params"]["list"]:
            record["long_field"] = "资料" * 8192
        original = copy.deepcopy(body)
        result = tool_result(body, query=True)
        payload = result.structured_content
        self.assertFalse(result.is_error)
        self.assertLessEqual(len(result.content[0].text.encode("utf-8")), MAX_OUTPUT_BYTES)
        self.assertLessEqual(len(render_json(payload).encode("utf-8")), MAX_OUTPUT_BYTES)
        self.assertGreater(payload["returned_count"], 0)
        self.assertLess(payload["returned_count"], 26)
        self.assertEqual(payload["returned_count"], len(payload["params"]["list"]))
        self.assertEqual(payload["output"]["omitted_records"], 26 - payload["returned_count"])
        self.assertEqual([record["dataId"] for record in payload["params"]["list"]],
                         [str(index) for index in range(payload["returned_count"])])
        self.assertEqual(payload["next_action"], "refine_query")
        self.assertEqual(payload["completeness"], "partial")
        ICPQueryResponse.model_validate(payload)
        self.assertEqual(body, original)

    def test_long_field_clipping_alone_marks_local_partial_output(self):
        body = page(total=1, count=1)
        body["params"]["list"][0]["long_field"] = "x" * 8192
        result = tool_result(body, query=True).structured_content
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["output"]["omitted_records"], 0)
        self.assertEqual(result["next_action"], "refine_query")

    def test_identifiers_are_not_rewritten_to_fit_the_budget(self):
        body = page(total=1, count=1)
        body["params"]["list"][0]["dataId"] = "opaque" * 20000
        result = tool_result(body, query=True).structured_content
        self.assertEqual(result["returned_count"], 0)
        self.assertEqual(result["output"]["omitted_records"], 1)
        self.assertEqual(result["next_action"], "refine_query")

    def test_large_non_record_metadata_returns_a_bounded_error(self):
        body = {"success": True, "params": {str(index): "x" * 1024 for index in range(1000)}}
        result = tool_result(body, query=True)
        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["error"]["type"], "output_too_large")
        self.assertLessEqual(len(result.content[0].text.encode()), MAX_OUTPUT_BYTES)


class DetailFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_bad_details_preserve_the_primary_summary_and_warn(self):
        for detail in (None, [], "unexpected", {"success": False}, {"success": True, "params": []}):
            with self.subTest(detail=detail):
                client = ICPQueryClient(Config())
                primary = page(total=1, count=1)
                captcha = CaptchaResult(puuid="test", token="test", sign="test", headers={})
                with patch.object(client, "_check_img", new=AsyncMock(return_value=captcha)), patch.object(
                    client, "_post_json", new=AsyncMock(side_effect=[primary, detail])
                ):
                    result = await client.query("example.test", "app", include_details=True)
                self.assertTrue(result["success"])
                self.assertEqual(result["params"]["list"][0]["dataId"], "0")
                self.assertEqual(result["warnings"][0]["type"], "detail_enrichment_failed")
                self.assertEqual(result["detail_requests"], 1)

    async def test_transport_and_json_errors_in_optional_details_preserve_summary(self):
        for error in (httpx.ReadTimeout("test"), QueryError("invalid_response", "test")):
            with self.subTest(error=error):
                client = ICPQueryClient(Config())
                primary = page(total=1, count=1)
                captcha = CaptchaResult(puuid="test", token="test", sign="test", headers={})
                with patch.object(client, "_post_json", new=AsyncMock(side_effect=error)):
                    await client._fetch_details(primary, 6, captcha, "", max_detail_enrichment=10)
                self.assertEqual(primary["params"]["list"][0]["dataId"], "0")
                self.assertEqual(primary["warnings"][0]["details"]["failed_requests"], 1)

    async def test_failed_primary_query_never_starts_detail_enrichment(self):
        client = ICPQueryClient(Config())
        body = page(total=1, count=1)
        body["success"] = False
        captcha = CaptchaResult(puuid="test", token="test", sign="test", headers={})
        with patch.object(client, "_check_img", new=AsyncMock(return_value=captcha)), patch.object(
            client, "_post_json", new=AsyncMock(return_value=body)
        ), patch.object(client, "_fetch_details", new=AsyncMock()) as details:
            result = await client.query("example.test", "app", include_details=True)
        details.assert_not_awaited()
        self.assertFalse(result["success"])

    async def test_main_response_json_must_be_an_object(self):
        client = ICPQueryClient(Config())
        for response in (httpx.Response(200, json=[]), httpx.Response(200, json=None), httpx.Response(200, text="invalid JSON")):
            with self.subTest(response=response.content), patch.object(client, "_post", new=AsyncMock(return_value=response)):
                with self.assertRaises(QueryError) as caught:
                    await client._post_json("https://example.test", {}, {}, "")
                self.assertEqual(caught.exception.error_type, "invalid_response")
