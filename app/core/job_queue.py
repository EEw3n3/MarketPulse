"""Redis-backed job queue for distributed scrape workers.

The server's "Scrape now" admin button enqueues a job via `enqueue()`.
A local worker (running on user's machine with a residential IP that bypasses
Cloudflare) polls via long-poll `dequeue()`, executes the scrape locally, and
POSTs results back to the server through an ingest endpoint.

Keys used in Redis:
  marketpulse:scrape:queue           — list, RPUSH job, BLPOP for dequeue
  marketpulse:scrape:state:{job_id}  — hash, status / domain / created_at
  marketpulse:worker:heartbeat       — string with TTL, set on every poll
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Optional

import redis.asyncio as aioredis
from loguru import logger

from app.core.config import settings


_QUEUE_KEY = "marketpulse:scrape:queue"
_STATE_PREFIX = "marketpulse:scrape:state:"
_HEARTBEAT_KEY = "marketpulse:worker:heartbeat"
_HEARTBEAT_TTL = 60  # seconds — worker must heartbeat at least every minute


class JobQueue:
    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None
        self._lock = asyncio.Lock()

    async def client(self) -> aioredis.Redis:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._client

    async def enqueue(self, domain: str, max_items: Optional[int] = None) -> str:
        """Push a new scrape job. `max_items=None` means worker uses its default
        (9999 = unlimited). Returns the job_id."""
        c = await self.client()
        job_id = uuid.uuid4().hex[:12]
        job_payload = {
            "id": job_id,
            "domain": domain,
            "created_at": time.time(),
            "max_items": max_items,
        }
        await c.rpush(_QUEUE_KEY, json.dumps(job_payload))
        await c.hset(
            _STATE_PREFIX + job_id,
            mapping={
                "domain": domain,
                "status": "queued",
                "created_at": str(time.time()),
                "max_items": str(max_items) if max_items is not None else "",
            },
        )
        await c.expire(_STATE_PREFIX + job_id, 86400)  # state cleared after 24h
        logger.info(f"[QUEUE] Enqueued job {job_id} for {domain} (max_items={max_items or 'unlimited'})")
        return job_id

    async def dequeue(self, timeout_s: int = 25) -> Optional[dict]:
        """Worker side — BLPOP with timeout. Returns the job dict or None."""
        c = await self.client()
        result = await c.blpop(_QUEUE_KEY, timeout=timeout_s)
        if not result:
            return None
        _key, payload = result
        try:
            job = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning(f"[QUEUE] Malformed job payload: {payload!r}")
            return None
        await self.update_status(job["id"], "in_progress")
        return job

    async def update_status(self, job_id: str, status: str, extra: Optional[dict] = None) -> None:
        c = await self.client()
        mapping = {"status": status, "updated_at": str(time.time())}
        if extra:
            for k, v in extra.items():
                mapping[k] = str(v)
        await c.hset(_STATE_PREFIX + job_id, mapping=mapping)

    async def get_state(self, job_id: str) -> Optional[dict]:
        c = await self.client()
        data = await c.hgetall(_STATE_PREFIX + job_id)
        return data or None

    async def heartbeat(self) -> None:
        """Worker pings — server reads `worker_online()` to display badge."""
        c = await self.client()
        await c.set(_HEARTBEAT_KEY, str(time.time()), ex=_HEARTBEAT_TTL)

    async def worker_status(self) -> dict:
        """Returns {online: bool, last_seen_ago: int|None, queue_depth: int}."""
        c = await self.client()
        last_seen_raw = await c.get(_HEARTBEAT_KEY)
        queue_depth = await c.llen(_QUEUE_KEY)
        if last_seen_raw is None:
            return {"online": False, "last_seen_ago_s": None, "queue_depth": queue_depth}
        try:
            last_seen = float(last_seen_raw)
        except ValueError:
            return {"online": False, "last_seen_ago_s": None, "queue_depth": queue_depth}
        ago = int(time.time() - last_seen)
        return {"online": ago < _HEARTBEAT_TTL, "last_seen_ago_s": ago, "queue_depth": queue_depth}


job_queue = JobQueue()
