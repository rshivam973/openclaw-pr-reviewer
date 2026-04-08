import logging
import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self, pat: str):
        self._http = httpx.AsyncClient(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bearer {pat}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def fetch_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        resp = await self._http.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    async def fetch_compare_diff(self, owner: str, repo: str, base_sha: str, head_sha: str) -> str:
        resp = await self._http.get(
            f"/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    async def fetch_context_md(self, owner: str, repo: str, ref: str) -> str | None:
        try:
            resp = await self._http.get(
                f"/repos/{owner}/{repo}/contents/CONTEXT.md",
                params={"ref": ref},
                headers={"Accept": "application/vnd.github.v3.raw"},
            )
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info("No CONTEXT.md found in %s/%s (ref=%s)", owner, repo, ref)
                return None
            raise

    async def fetch_pr_info(self, owner: str, repo: str, pr_number: int) -> dict:
        resp = await self._http.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        resp.raise_for_status()
        return resp.json()

    async def post_review(self, owner: str, repo: str, pr_number: int, commit_sha: str, body: str, comments: list[dict]) -> None:
        payload = {"commit_id": commit_sha, "body": body, "event": "COMMENT", "comments": comments}
        resp = await self._http.post(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", json=payload)
        resp.raise_for_status()
        logger.info("Posted review on %s/%s#%d", owner, repo, pr_number)

    async def post_comment(self, owner: str, repo: str, pr_number: int, body: str) -> None:
        resp = await self._http.post(f"/repos/{owner}/{repo}/issues/{pr_number}/comments", json={"body": body})
        resp.raise_for_status()

    async def close(self):
        await self._http.aclose()
