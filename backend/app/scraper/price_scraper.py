import re
import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote


def extract_asin(url: str) -> str:
    match = re.search(r"/dp/([A-Z0-9]{10})", url or "", re.I)
    return match.group(1).upper() if match else ""


def normalize_url(url: str) -> str:
    asin = extract_asin(url)
    if asin:
        return f"https://www.amazon.com/dp/{asin}"
    return url


def clean_price(raw) -> float:
    if not raw:
        return 0.0
    text = str(raw).strip()
    digits = re.sub(r"[^\d.]", "", text)
    if not digits:
        return 0.0
    parts = digits.split(".")
    if len(parts) > 2:
        digits = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return round(float(digits), 2)
    except ValueError:
        return 0.0


HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
]


def parse_amazon_page(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    # ── TITLE ──────────────────────────────────────────────────────────
    title = ""
    title_selectors = [
        {"id": "productTitle"},
        {"id": "title"},
        {"class": "product-title-word-break"},
    ]
    for selector in title_selectors:
        tag = soup.find("span", selector) or soup.find("h1", selector)
        if tag:
            title = tag.get_text(strip=True)
            break
    print(f"  [HTML] title: '{title[:80]}'")

    # ── PRICE ───────────────────────────────────────────────────────────
    price = 0.0

    whole_el = soup.find("span", {"class": "a-price-whole"})
    frac_el  = soup.find("span", {"class": "a-price-fraction"})
    if whole_el:
        whole = whole_el.get_text(strip=True).rstrip(".")
        frac  = frac_el.get_text(strip=True) if frac_el else "00"
        price = clean_price(f"{whole}.{frac}")
        print(f"  [HTML] price method 1 (whole+frac): ${price}")

    if price == 0:
        offscreen = soup.find("span", {"class": "a-offscreen"})
        if offscreen:
            price = clean_price(offscreen.get_text(strip=True))
            print(f"  [HTML] price method 2 (offscreen): ${price}")

    if price == 0:
        for pid in ["priceblock_ourprice", "priceblock_dealprice", "priceblock_saleprice"]:
            el = soup.find("span", {"id": pid})
            if el:
                price = clean_price(el.get_text(strip=True))
                print(f"  [HTML] price method 3 ({pid}): ${price}")
                break

    if price == 0:
        for el in soup.find_all("span", {"class": "a-price"}):
            candidate = clean_price(el.get_text(strip=True))
            if candidate > 0:
                price = candidate
                print(f"  [HTML] price method 4 (a-price): ${price}")
                break

    if price == 0:
        matches = re.findall(r"\$\s*(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)", html)
        for m in matches:
            candidate = clean_price(m)
            if candidate > 10:
                price = candidate
                print(f"  [HTML] price method 5 (regex): ${price}")
                break

    # ── IMAGE ───────────────────────────────────────────────────────────
    image_url = ""

    # Method 1: landingImage — primary high-res image
    img_tag = soup.find("img", {"id": "landingImage"})
    if img_tag:
        image_url = (
            img_tag.get("data-old-hires") or
            img_tag.get("data-a-dynamic-image") and "" or  # skip JS blob
            img_tag.get("src") or
            ""
        )
        # data-old-hires gives highest quality, src is fallback
        if not image_url or image_url.startswith("data:"):
            image_url = img_tag.get("src") or ""

    # Method 2: imgBlkFront (books, some electronics)
    if not image_url:
        img_tag = soup.find("img", {"id": "imgBlkFront"})
        if img_tag:
            image_url = img_tag.get("src") or ""

    # Method 3: first image inside #imageBlock container
    if not image_url:
        block = soup.find("div", {"id": "imageBlock"})
        if block:
            img = block.find("img")
            if img:
                image_url = img.get("src") or ""

    # Method 4: og:image meta — always present, very reliable
    if not image_url:
        og = soup.find("meta", {"property": "og:image"})
        if og:
            image_url = og.get("content") or ""

    # Method 5: twitter:image meta
    if not image_url:
        tw = soup.find("meta", {"name": "twitter:image"})
        if tw:
            image_url = tw.get("content") or ""

    # Clean: strip Amazon size suffixes like ._AC_SX679_ to get full res
    if image_url and not image_url.startswith("data:"):
        image_url = re.sub(r"\._[A-Z0-9_,]+_\.", ".", image_url)
    elif image_url.startswith("data:"):
        image_url = ""

    print(f"  [HTML] image: '{image_url[:80]}'")

    return {"title": title, "price": price, "image": image_url}


async def scrape_amazon(url: str) -> dict:
    clean_url = normalize_url(url)
    print(f"[Scraper] Fetching: {clean_url}")

    for attempt, headers in enumerate(HEADERS_LIST):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=20.0,
                headers=headers,
            ) as client:
                response = await client.get(clean_url)

            print(f"[Scraper] Attempt {attempt + 1} → HTTP {response.status_code}")

            if response.status_code == 503:
                print(f"[Scraper] Bot-blocked (503), retrying in {2 ** attempt}s...")
                await asyncio.sleep(2 ** attempt)
                continue

            if response.status_code == 404:
                print("[Scraper] 404 - product not found")
                return {"title": "", "price": 0.0, "image": "", "found": False}

            if response.status_code != 200:
                await asyncio.sleep(1)
                continue

            html = response.text

            if "captcha" in html.lower() or "robot check" in html.lower():
                print(f"[Scraper] CAPTCHA on attempt {attempt + 1}, retrying...")
                await asyncio.sleep(3)
                continue

            result = parse_amazon_page(html)
            if not result["title"] and result["price"] == 0:
                print("[Scraper] Page loaded but nothing extracted, retrying...")
                await asyncio.sleep(1)
                continue

            print(f"[Scraper] SUCCESS → '{result['title'][:60]}' @ ${result['price']}")
            return {
                "title": result["title"],
                "price": result["price"],
                "image": result["image"],
                "found": True,
            }

        except httpx.TimeoutException:
            print(f"[Scraper] Timeout on attempt {attempt + 1}")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[Scraper] Error on attempt {attempt + 1}: {e}")
            await asyncio.sleep(1)

    print("[Scraper] All attempts failed")
    return {"title": "", "price": 0.0, "image": "", "found": False}


async def scrape_price(url: str, product_name: str | None = None) -> dict:
    print(f"\n{'='*50}")
    print(f"[Scraper] URL: {url[:80]}")

    result = await scrape_amazon(url)

    title = result.get("title") or product_name or "Unknown Product"
    price = result.get("price", 0.0)
    image = result.get("image", "")
    found = result.get("found", False)

    if price == 0:
        print(f"[Scraper] WARNING: price is 0 for '{title}'")

    print(f"[Scraper] FINAL → title='{title[:60]}' price=${price} image={'yes' if image else 'none'}")
    print(f"{'='*50}\n")

    return {
        "title": title,
        "price": price,
        "image": image,
        "found": found,
        "url": url,
    }