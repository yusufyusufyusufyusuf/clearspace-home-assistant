"""Async client for the ClearSpace public API."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientResponseError, ClientSession


class ClearSpaceAuthError(Exception):
    """Raised when a ClearSpace API token is invalid."""


class ClearSpaceApiError(Exception):
    """Raised when ClearSpace cannot complete a request."""


class ClearSpaceApi:
    """Small async ClearSpace API client."""

    def __init__(self, session: ClientSession, base_url: str, token: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers,
                timeout=20,
                **kwargs,
            ) as response:
                if response.status == 401:
                    raise ClearSpaceAuthError("Invalid or revoked API token")
                if response.status >= 400:
                    detail = await response.json(content_type=None)
                    raise ClearSpaceApiError(detail.get("error", f"HTTP {response.status}"))
                if response.status == 204:
                    return None
                return await response.json(content_type=None)
        except ClearSpaceAuthError:
            raise
        except (ClientResponseError, TimeoutError, OSError) as error:
            raise ClearSpaceApiError(str(error)) from error

    async def tasks(self) -> list[dict[str, Any]]:
        return (await self.request("GET", "/v1/tasks"))["tasks"]

    async def spaces(self) -> list[dict[str, Any]]:
        return (await self.request("GET", "/v1/spaces"))["spaces"]

    async def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        return (await self.request("POST", "/v1/tasks", json=data))["task"]

    async def update_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return (await self.request("PATCH", f"/v1/tasks/{task_id}", json=data))["task"]

    async def delete_task(self, task_id: str) -> None:
        await self.request("DELETE", f"/v1/tasks/{task_id}")

