@echo off
REM Double-click this file to start the MarketPulse scrape worker.
REM The worker connects to the production server, waits for jobs
REM (queued via Admin → Scraping → "Scrape now"), runs the actual
REM scraping locally using your residential IP, then pushes results
REM back to the server.
REM
REM Leave this window open while you want scraping to be possible.
REM Press Ctrl+C to stop the worker.

cd /d "%~dp0\.."
echo Starting MarketPulse scrape worker...
echo Server: %SERVER_URL%
echo.
echo --- Worker output below ---
echo.
docker compose exec app python scripts/scrape_worker.py
echo.
echo Worker stopped. Press any key to close this window.
pause >nul
