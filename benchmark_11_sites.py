import sys
import asyncio
from rankintel.crawler.deep_crawler import AsyncDeepCrawler
from rankintel.models.schema import CrawlConfig
import time

SITES = [
    "https://alephindia.in/",
    "https://www.tcreng.com/",
    "https://www.zaubacorp.com/",
    "https://www.yadavmeasurements.com/",
    "https://www.uniquemeasurement.com/",
    "https://qualityinternational.org/",
    "https://www.ascgroup.in/",
    "https://www.standphillindia.in/",
    "https://umspcs.in/",
    "https://sqccertification.com/",
    "https://sunrisetesting.vercel.app/"
]

def format_row(site, res, error=""):
    if error:
        return f"| {site} | - | - | - | - | - | - | - | {error} | ERROR |"
    
    discovered = res.pages_discovered
    crawled = res.pages_crawled
    sitemap = res.sitemap_only_urls
    rendered = res.rendered_only_urls
    blocked = res.pages_blocked
    errors = res.pages_failed
    unfetched = res.pages_queued
    
    coverage = f"Found {crawled} HTML, {sitemap} sitemap-only"
    status = res.completeness_status
    
    return f"| {site} | {discovered} | {crawled} | {sitemap} | {rendered} | {blocked} | {errors} | {unfetched} | {coverage} | {status} |"

async def crawl_site(site: str) -> str:
    config = CrawlConfig(
        max_pages=50,
        max_depth=3,
        concurrency=3,
        crawl_delay=0.2,
        timeout_sec=15.0,
        enable_sitemap_analysis=True,
        enable_browser_rendering=True
    )
    crawler = AsyncDeepCrawler(config=config)
    try:
        res = await crawler.crawl(site)
        return format_row(site, res)
    except Exception as e:
        return format_row(site, None, str(e))

async def main():
    print("| Site | Discovered | Crawled | Sitemap | Rendered-only | Blocked | Errors | Unfetched | Recall/coverage evidence | Status |", flush=True)
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|---|", flush=True)
    
    tasks = [asyncio.create_task(crawl_site(site)) for site in SITES]
    
    for completed in asyncio.as_completed(tasks):
        row = await completed
        print(row, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
