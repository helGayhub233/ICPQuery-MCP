from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from icpquery_mcp.core.captcha import match_slider_offset
from icpquery_mcp.core.config import Config
from icpquery_mcp.core.errors import QueryError
from icpquery_mcp.responses import normalize_response as _normalize_response

AUTH_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/auth"
GET_CHECK_IMAGE_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/image/getCheckImagePoint"
CHECK_IMAGE_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/image/checkImage"
QUERY_BY_CONDITION_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/icpAbbreviateInfo/queryByCondition"
BLACK_QUERY_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/blackListDomain/queryByCondition"
BLACK_APP_MINI_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/blackListDomain/queryByCondition_appAndMini"
DETAIL_BY_APP_MINI_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/icpAbbreviateInfo/queryDetailByAppAndMiniId"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32"
)

SERVICE_TYPES = {"web": 1, "app": 6, "mapp": 7, "kapp": 8}
BLACKLIST_TYPES = {"bweb": 1, "bapp": 6, "bmapp": 7, "bkapp": 8}

# 滑块识别偶发受背景同色区域影响，上游会拒绝错误偏移；上游每轮返回的图片是随机的，
# 因此一次有界自动重试即可显著降低调用方感知到的失败率。
_CAPTCHA_ATTEMPTS = 2


@dataclass
class CaptchaResult:
    puuid: str
    token: str
    sign: str
    headers: dict[str, str]


class ICPQueryClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._token = ""  # nosec B105
        self._token_expire = 0.0
        self._token_lock = asyncio.Lock()

    async def query(self, name: str, query_type: str = "web", page: int = 1, page_size: int = 26, proxy: str = "", *, include_details: bool = True, max_detail_enrichment: int = 10) -> dict[str, Any]:
        service_type = SERVICE_TYPES.get(query_type)
        if service_type is None:
            raise ValueError(f"unsupported type: {query_type}")
        data = await self._get_beian(name, service_type, page, min(max(page_size, 1), 26), proxy, include_details=include_details, max_detail_enrichment=max_detail_enrichment)
        return _normalize_response(data)

    async def blacklist(self, name: str, query_type: str = "bweb", proxy: str = "") -> dict[str, Any]:
        service_type = BLACKLIST_TYPES.get(query_type)
        if service_type is None:
            raise ValueError(f"unsupported type: {query_type}")
        data = await self._get_black_beian(name, service_type, proxy)
        return _normalize_response(data)

    async def _get_beian(self, name: str, service_type: int, page: int, page_size: int, proxy: str, *, include_details: bool, max_detail_enrichment: int) -> dict[str, Any]:
        resolved_proxy = self._resolve_proxy(proxy)
        captcha = await self._check_img(resolved_proxy)
        body = {
            "pageNum": page,
            "pageSize": page_size,
            "unitName": name,
            "serviceType": service_type,
        }
        headers = self._auth_headers(captcha, body)
        result = await self._post_json(QUERY_BY_CONDITION_URL, body, headers, resolved_proxy)
        if result.get("success") is True and service_type != SERVICE_TYPES["web"] and include_details:
            await self._fetch_details(result, service_type, captcha, resolved_proxy, max_detail_enrichment=max_detail_enrichment)
        else:
            result.setdefault("detail_requests", 0)
            result.setdefault("details_truncated", False)
        return result

    async def _get_black_beian(self, name: str, service_type: int, proxy: str) -> dict[str, Any]:
        resolved_proxy = self._resolve_proxy(proxy)
        if service_type == SERVICE_TYPES["web"]:
            body: dict[str, Any] = {"domainName": name}
            target_url = BLACK_QUERY_URL
        else:
            body = {"serviceName": name, "serviceType": service_type}
            target_url = BLACK_APP_MINI_URL
        captcha = await self._check_img(resolved_proxy)
        headers = self._auth_headers(captcha, body)
        return await self._post_json(target_url, body, headers, resolved_proxy)

    async def _fetch_details(self, result: dict[str, Any], service_type: int, captcha: CaptchaResult, proxy: str, *, max_detail_enrichment: int) -> None:
        params = result.get("params")
        if not isinstance(params, dict):
            result.setdefault("detail_requests", 0)
            result.setdefault("details_truncated", False)
            return
        items = params.get("list")
        if not isinstance(items, list) or not items:
            result.setdefault("detail_requests", 0)
            result.setdefault("details_truncated", False)
            return

        original_items = list(items)
        requestable_indices = [
            index
            for index, item in enumerate(original_items)
            if isinstance(item, dict) and item.get("dataId")
        ]
        selected_indices = requestable_indices[: max(0, max_detail_enrichment)]
        if not selected_indices:
            result["detail_requests"] = 0
            result["details_truncated"] = bool(requestable_indices)
            return
        sem = asyncio.Semaphore(1)

        async def fetch_one(index: int) -> tuple[int, Any, bool]:
            item = original_items[index]
            if not isinstance(item, dict) or not item.get("dataId"):
                return index, item, False
            async with sem:
                body = {"dataId": item["dataId"], "serviceType": service_type}
                try:
                    headers = self._auth_headers(captcha, body)
                    detail = await self._post_json(DETAIL_BY_APP_MINI_URL, body, headers, proxy)
                    if isinstance(detail, dict) and detail.get("success") is True and isinstance(detail.get("params"), dict):
                        return index, detail["params"], True
                # Optional enrichment must preserve the primary summary after
                # transport, decoding, or provider-shape failures.
                except Exception:  # noqa: BLE001
                    return index, item, False
                return index, item, False

        enriched = await asyncio.gather(*(fetch_one(index) for index in selected_indices))
        enriched_by_index = {index: item for index, item, _ in enriched}
        params["list"] = [
            enriched_by_index.get(index, item)
            for index, item in enumerate(original_items)
        ]
        result["detail_requests"] = len(selected_indices)
        result["details_truncated"] = len(selected_indices) < len(requestable_indices)
        failures = sum(not succeeded for _, _, succeeded in enriched)
        if failures:
            result.setdefault("warnings", []).append({
                "type": "detail_enrichment_failed",
                "message": "Some detail requests failed; their original summary records were retained.",
                "details": {"failed_requests": failures},
            })

    async def _check_img(self, proxy: str) -> CaptchaResult:
        last_error: QueryError | None = None
        for _attempt in range(_CAPTCHA_ATTEMPTS):
            try:
                return await self._solve_captcha(proxy)
            except QueryError as exc:
                last_error = exc
        raise last_error if last_error is not None else QueryError("captcha_error", "验证码识别失败，请稍后顺序重试。")

    async def _solve_captcha(self, proxy: str) -> CaptchaResult:
        token, headers = await self._get_token(proxy)
        client_uid = "point-" + str(uuid.uuid4())
        body = {"clientUid": client_uid}
        headers["token"] = token
        headers["Content-Type"] = "application/json"
        img_result = await self._post_json(GET_CHECK_IMAGE_URL, body, headers, proxy)
        params = img_result.get("params")
        if not isinstance(params, dict):
            raise QueryError("invalid_response", "验证码响应缺少 params，请检查上游状态后再重试。")  # noqa: TRY004
        puuid = str(params.get("uuid") or "")
        big_image = str(params.get("bigImage") or "")
        small_image = str(params.get("smallImage") or "")
        if not puuid or not big_image or not small_image:
            raise QueryError("invalid_response", "验证码响应缺少 uuid/bigImage/smallImage，请检查上游状态后再重试。")

        matched, offset_x = match_slider_offset(small_image, big_image)
        if not matched:
            raise QueryError("captcha_error", "滑块匹配失败，请稍后顺序重试。")

        check_body = {"key": puuid, "value": str(offset_x)}
        check_result = await self._post_json(CHECK_IMAGE_URL, check_body, headers, proxy)
        if check_result.get("success") is not True:
            raise QueryError("captcha_error", "验证码识别失败，请检查代理及上游状态后顺序重试。")
        sign = check_result.get("params")
        if not isinstance(sign, str) or not sign:
            raise QueryError("invalid_response", "验证结果缺少 sign，请检查上游状态后再重试。")
        return CaptchaResult(puuid=puuid, token=token, sign=sign, headers=dict(headers))

    async def _get_token(self, proxy: str) -> tuple[str, dict[str, str]]:
        headers = _base_headers()
        headers["Cookie"] = f"__jsluid_s={_random_hex(32)}"

        async with self._token_lock:
            now_ms = time.time() * 1000
            if self._token and self._token_expire > now_ms:
                return self._token, headers

            ts = int(now_ms)
            auth_key = hashlib.md5(
                f"testtest{ts}".encode(),
                usedforsecurity=False,
            ).hexdigest()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            response = await self._post(AUTH_URL, f"authKey={auth_key}&timeStamp={ts}".encode(), headers, proxy)
            try:
                result = response.json()
            except ValueError as error:
                raise QueryError("invalid_response", "MIIT returned invalid token JSON. Check provider status before retrying.") from error
            if not isinstance(result, dict):
                raise QueryError("invalid_response", "MIIT returned a non-object token response. Check provider status before retrying.")
            params = result.get("params")
            if not isinstance(params, dict):
                raise QueryError("invalid_response", "MIIT returned an invalid token response. Check provider status before retrying.")  # noqa: TRY004
            token = str(params.get("bussiness") or "")
            try:
                expire = int(params.get("expire") or 0)
            except (TypeError, ValueError) as error:
                raise QueryError("invalid_response", "MIIT returned an invalid token expiry. Check provider status before retrying.") from error
            if not token or expire <= 0:
                raise QueryError("invalid_response", "MIIT token response is missing bussiness/expire. Check provider status before retrying.")
            self._token = token
            self._token_expire = now_ms + expire
            return token, headers

    async def _post_json(self, url: str, body: dict[str, Any], headers: dict[str, str], proxy: str) -> dict[str, Any]:
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        response = await self._post(url, raw, headers, proxy)
        data = response.content
        if b"\xe5\xbd\x93\xe5\x89\x8d\xe8\xae\xbf\xe9\x97\xae\xe7\x96\x91\xe4\xbc\xbc\xe9\xbb\x91\xe5\xae\xa2\xe6\x94\xbb\xe5\x87\xbb" in data:
            raise QueryError("provider_blocked", "当前访问已被创宇盾拦截，请检查代理并降低请求频率。")
        try:
            result = response.json()
        except ValueError as error:
            raise QueryError("invalid_response", "MIIT returned invalid JSON. Check provider status before retrying.") from error
        if not isinstance(result, dict):
            raise QueryError("invalid_response", "MIIT returned a non-object response. Check provider status before retrying.")
        return result

    async def _post(self, url: str, body: bytes, headers: dict[str, str], proxy: str) -> httpx.Response:
        request_headers = dict(headers)
        request_headers["Content-Length"] = str(len(body))
        async with httpx.AsyncClient(
            timeout=self.config.timeout,
            proxy=proxy or None,
            headers=None,
        ) as client:
            response = await client.post(url, content=body, headers=request_headers)
            response.raise_for_status()
            return response

    def _auth_headers(self, captcha: CaptchaResult, body: dict[str, Any]) -> dict[str, str]:
        headers = dict(captcha.headers)
        headers["uuid"] = captcha.puuid
        headers["token"] = captcha.token
        headers["sign"] = captcha.sign
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))
        return headers

    def _resolve_proxy(self, proxy: str) -> str:
        return proxy or self.config.proxy.tunnel


def _base_headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Origin": "https://beian.miit.gov.cn",
        "Referer": "https://beian.miit.gov.cn/",
        "Accept": "application/json, text/plain, */*",
    }


def _random_hex(length: int) -> str:
    return secrets.token_hex(length)
