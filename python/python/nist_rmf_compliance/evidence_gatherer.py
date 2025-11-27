"""Evidence gathering module with screenshot capture capabilities."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from .models import Evidence, EvidenceType

logger = logging.getLogger(__name__)


class EvidenceGatherer:
    """Automated evidence collection using Playwright (Python Puppeteer equivalent).

    Features:
    - Screenshot capture from web applications
    - Configuration file exports
    - Log collection
    - Document gathering
    """

    def __init__(self, output_dir: str = "./evidence"):
        """Initialize evidence gatherer.

        Args:
            output_dir: Directory to store evidence artifacts
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser = None

    async def _init_browser(self):
        """Initialize Playwright browser."""
        try:
            from playwright.async_api import async_playwright
            if not self._playwright:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
            return self._browser
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install")
            raise

    async def capture_screenshot(
        self,
        url: str,
        title: str,
        description: str,
        wait_for_selector: Optional[str] = None,
        full_page: bool = True,
    ) -> Evidence:
        """Capture a screenshot from a web page.

        Args:
            url: URL to capture
            title: Evidence title
            description: Evidence description
            wait_for_selector: Optional CSS selector to wait for before capturing
            full_page: Whether to capture full scrollable page

        Returns:
            Evidence object with screenshot details
        """
        browser = await self._init_browser()
        page = await browser.new_page()

        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until="networkidle")

            if wait_for_selector:
                logger.info(f"Waiting for selector: {wait_for_selector}")
                await page.wait_for_selector(wait_for_selector, timeout=10000)

            # Generate filename
            evidence_id = str(uuid.uuid4())
            filename = f"screenshot_{evidence_id}.png"
            filepath = self.output_dir / filename

            # Capture screenshot
            logger.info(f"Capturing screenshot to {filepath}")
            await page.screenshot(path=str(filepath), full_page=full_page)

            # Create evidence record
            evidence = Evidence(
                evidence_id=evidence_id,
                evidence_type=EvidenceType.SCREENSHOT,
                title=title,
                description=description,
                file_path=str(filepath),
                url=url,
                collected_at=datetime.now(),
                collected_by="evidence_gatherer",
                metadata={
                    "full_page": full_page,
                    "viewport": {
                        "width": page.viewport_size["width"],
                        "height": page.viewport_size["height"],
                    },
                },
            )

            logger.info(f"Screenshot captured: {evidence_id}")
            return evidence

        except Exception as e:
            logger.error(f"Error capturing screenshot from {url}: {e}")
            raise
        finally:
            await page.close()

    async def capture_multiple_screenshots(
        self,
        targets: List[Dict[str, Any]],
    ) -> List[Evidence]:
        """Capture multiple screenshots in batch.

        Args:
            targets: List of dictionaries with 'url', 'title', 'description' keys

        Returns:
            List of Evidence objects
        """
        evidence_list = []
        for target in targets:
            try:
                evidence = await self.capture_screenshot(
                    url=target["url"],
                    title=target["title"],
                    description=target["description"],
                    wait_for_selector=target.get("wait_for_selector"),
                    full_page=target.get("full_page", True),
                )
                evidence_list.append(evidence)
            except Exception as e:
                logger.error(f"Failed to capture {target['url']}: {e}")
                continue

        return evidence_list

    def collect_configuration_file(
        self,
        file_path: str,
        title: str,
        description: str,
    ) -> Evidence:
        """Collect a configuration file as evidence.

        Args:
            file_path: Path to configuration file
            title: Evidence title
            description: Evidence description

        Returns:
            Evidence object
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        evidence_id = str(uuid.uuid4())

        # Copy file to evidence directory
        dest_path = self.output_dir / f"config_{evidence_id}_{path.name}"
        import shutil
        shutil.copy2(file_path, dest_path)

        evidence = Evidence(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.CONFIGURATION,
            title=title,
            description=description,
            file_path=str(dest_path),
            collected_at=datetime.now(),
            collected_by="evidence_gatherer",
            metadata={
                "original_path": file_path,
                "file_size": path.stat().st_size,
            },
        )

        logger.info(f"Configuration file collected: {evidence_id}")
        return evidence

    def collect_log_file(
        self,
        file_path: str,
        title: str,
        description: str,
        lines: Optional[int] = None,
    ) -> Evidence:
        """Collect log file as evidence.

        Args:
            file_path: Path to log file
            title: Evidence title
            description: Evidence description
            lines: Number of recent lines to collect (None for full file)

        Returns:
            Evidence object
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")

        evidence_id = str(uuid.uuid4())
        dest_path = self.output_dir / f"log_{evidence_id}_{path.name}"

        # Read and optionally tail the log
        if lines:
            with open(file_path, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:]

            with open(dest_path, 'w') as f:
                f.writelines(recent_lines)
        else:
            import shutil
            shutil.copy2(file_path, dest_path)

        evidence = Evidence(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.LOG,
            title=title,
            description=description,
            file_path=str(dest_path),
            collected_at=datetime.now(),
            collected_by="evidence_gatherer",
            metadata={
                "original_path": file_path,
                "lines_collected": lines if lines else "all",
            },
        )

        logger.info(f"Log file collected: {evidence_id}")
        return evidence

    async def close(self):
        """Clean up resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._browser or self._playwright:
            asyncio.run(self.close())


# Convenience function for synchronous usage
def capture_screenshot_sync(
    url: str,
    title: str,
    description: str,
    output_dir: str = "./evidence",
    **kwargs,
) -> Evidence:
    """Synchronous wrapper for screenshot capture.

    Args:
        url: URL to capture
        title: Evidence title
        description: Evidence description
        output_dir: Output directory
        **kwargs: Additional arguments passed to capture_screenshot

    Returns:
        Evidence object
    """
    gatherer = EvidenceGatherer(output_dir=output_dir)
    try:
        return asyncio.run(gatherer.capture_screenshot(url, title, description, **kwargs))
    finally:
        asyncio.run(gatherer.close())
