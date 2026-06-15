# Douyin Article Scraper

This tool uses Playwright to render a Douyin article page, then exports visible text, image URLs, an HTML snapshot, and optionally downloaded images.

It is intended for content you are allowed to save or analyze. Do not use it to bypass login, access controls, paywalls, privacy settings, or platform rate limits.

## Install

From this directory:

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers venv/bin/python -m playwright install chromium
```

## Run

```bash
venv/bin/python douyin_article_scraper.py "https://www.douyin.com/article/7647067694306479375"
```

The script opens a visible browser by default. If Douyin asks for login, QR scan, or verification, finish it in the browser window, then return to the terminal and press Enter.

Outputs are written under:

```text
outputs/douyin_article/
```

For each article, the script writes:

- `<article_id>.json`: source URL, final URL, title, text, image URLs, downloaded image paths
- `<article_id>.txt`: extracted text only
- `<article_id>.html`: rendered HTML snapshot
- `<article_id>_images/`: downloaded images when accessible

## Useful Options

```bash
# Do not download image binaries, only collect image URLs
venv/bin/python douyin_article_scraper.py URL --no-download

# Run without a visible browser; only works when no manual login/check is needed
venv/bin/python douyin_article_scraper.py URL --headless

# Wait longer before extraction
venv/bin/python douyin_article_scraper.py URL --wait 8
```

## Notes

Douyin pages are often dynamically rendered and may return 404 or empty content to plain HTTP clients. A real browser context is usually required, especially for pages that need cookies, login state, or lazy-loaded images.

The generated article content and downloaded images are not committed here by default. Keep scraped outputs local unless you have the right to redistribute them.
