import asyncio
import json
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.registry import register_domain
from app.core.database import async_session

class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    async def _run_hardcore_scan(self):
        """
        Executes the hardcore monitor logic.
        Since we are in a headless/background mode, we don't use the Rich UI.
        """
        logger.info("🕰️ [SCHEDULER] Starting scheduled Hardcore Market Monitor...")
        
        try:
            with open("configs/categories.json", "r", encoding="utf-8") as f:
                cats = json.load(f)
                targets = cats.get("mens_perfume", {}).get("targets", [])
        except Exception as e:
            logger.error(f"❌ [SCHEDULER] Config error: {e}")
            return

        if not targets:
            logger.error("❌ [SCHEDULER] No targets found in config!")
            return

        # Import locally to avoid circular imports if any
        from app.main import process_target_worker
        from urllib.parse import urlparse
        
        tasks = []
        for t in targets:
            site_name = t.get("site", urlparse(t["url"]).netloc)
            register_domain(t["url"])
            target_payload = {
                "url": t["url"],
                "search_term": "ScheduledMonitor", 
                "category": t.get("category", "Men's Perfume"),
                "site_name": site_name
            }
            # process_target_worker signature: target, intent, group_id, enable_price_filter
            tasks.append(asyncio.create_task(process_target_worker(target_payload, None, None, True)))
        
        if tasks:
            await asyncio.gather(*tasks)
            
        logger.info("✅ [SCHEDULER] Scheduled scan completed successfully.")

    def start(self, interval_hours: int = 24):
        """
        Starts the scheduler.
        """
        if self.is_running:
            logger.warning("Scheduler is already running.")
            return
            
        # Add the main scanning job
        self.scheduler.add_job(
            self._run_hardcore_scan,
            trigger=IntervalTrigger(hours=interval_hours),
            id="hardcore_scan_job",
            name="Daily Hardcore Market Scan",
            replace_existing=True,
            next_run_time=datetime.now() # Run immediately on startup
        )
        
        self.scheduler.start()
        self.is_running = True
        logger.info(f"📅 [SCHEDULER] Started. Jobs will run every {interval_hours} hours.")

    def stop(self):
        if self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("🛑 [SCHEDULER] Stopped.")

scheduler_service = SchedulerService()
