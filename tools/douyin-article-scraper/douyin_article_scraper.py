#!/usr/bin/env python3
"""
Scrape a Douyin article page after browser rendering.

Usage:
  python3 douyin_article_scraper.py \
    "https://www.douyin.com/article/7647067694306479375"

Install dependency first:
  python3 -m pip install playwright
  python3 -m playwright install chromium
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_URL = "https://www.douyin.com/article/7647067694306479375"
OUTPUT_DIR = Path("outputs") / "douyin_article"


def safe_name(value: str, fallback: str) -> str:
    value = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    value = value.strip("._")
    return value[:120] or fallback


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def pick_extension(url: str, content_type: str | None) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return suffix
    if content_type:
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"
        if "gif" in content_type:
            return ".gif"
    return ".jpg"


def download_image(url: str, target_dir: Path, index: int, referer: str) -> str | None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Referer": referer,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            content_type = response.headers.get("Content-Type")
            data = response.read()
    except (urllib.error.URLError, TimeoutError):
        return None

    extension = pick_extension(url, content_type)
    path = target_dir / f"{index:03d}{extension}"
    path.write_bytes(data)
    return str(path)


def scrape(url: str, headless: bool, wait_seconds: int, no_download: bool) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(".playwright-browsers").resolve()))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeoutError:
            print("页面初次加载超时，继续尝试从当前页面提取。", file=sys.stderr)

        if not headless:
            print()
            print("浏览器已经打开。")
            print("如果页面要求登录、扫码或验证，请先在浏览器里完成。")
            print("完成后回到终端按回车继续抓取。")
            input("> ")

        page.wait_for_timeout(wait_seconds * 1000)

        # Scroll a little to trigger lazy images.
        for _ in range(6):
            page.mouse.wheel(0, 900)
            page.wait_for_timeout(500)
        page.mouse.wheel(0, -5400)
        page.wait_for_timeout(1000)

        html = page.content()
        title = page.title().strip()
        current_url = page.url

        extracted = page.evaluate(
            """
            () => {
              const visibleText = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style && style.visibility !== 'hidden' &&
                  style.display !== 'none' && rect.width > 0 && rect.height > 0;
              };

              const textBlocks = Array.from(document.querySelectorAll('article, main, [class*="article"], [class*="content"], [class*="detail"], p, h1, h2, h3, div, span'))
                .filter(visibleText)
                .map(el => (el.innerText || el.textContent || '').trim())
                .filter(text => text.length > 0);

              const images = Array.from(document.images)
                .map(img => img.currentSrc || img.src || img.getAttribute('data-src') || '')
                .filter(src => /^https?:\\/\\//.test(src));

              return { textBlocks, images };
            }
            """
        )

        text_blocks = unique(extracted.get("textBlocks", []))
        images = unique(extracted.get("images", []))

        article_id = safe_name(urlparse(current_url).path.rsplit("/", 1)[-1], "douyin_article")
        json_path = OUTPUT_DIR / f"{article_id}.json"
        text_path = OUTPUT_DIR / f"{article_id}.txt"
        html_path = OUTPUT_DIR / f"{article_id}.html"
        images_dir = OUTPUT_DIR / f"{article_id}_images"

        html_path.write_text(html, encoding="utf-8")
        text_path.write_text("\n\n".join(text_blocks), encoding="utf-8")

        downloaded: list[str] = []
        if images and not no_download:
            images_dir.mkdir(parents=True, exist_ok=True)
            for index, image_url in enumerate(images, start=1):
                local_path = download_image(image_url, images_dir, index, current_url)
                if local_path:
                    downloaded.append(local_path)

        payload = {
            "source_url": url,
            "final_url": current_url,
            "title": title,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "text": "\n\n".join(text_blocks),
            "image_urls": images,
            "downloaded_images": downloaded,
            "html_snapshot": str(html_path),
            "text_file": str(text_path),
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        browser.close()

    print(f"标题: {title or '(未识别)'}")
    print(f"文本块: {len(text_blocks)}")
    print(f"图片链接: {len(images)}")
    print(f"已下载图片: {len(downloaded)}")
    print(f"JSON: {json_path}")
    print(f"TXT: {text_path}")
    print(f"HTML: {html_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape a rendered Douyin article page.")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser.")
    parser.add_argument("--wait", type=int, default=3, help="Seconds to wait before extraction.")
    parser.add_argument("--no-download", action="store_true", help="Do not download images.")
    args = parser.parse_args()

    return scrape(args.url, args.headless, args.wait, args.no_download)


if __name__ == "__main__":
    raise SystemExit(main())
