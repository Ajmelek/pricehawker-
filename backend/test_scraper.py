import sys
sys.path.insert(0, '.')

from app.scraper.price_scraper import scrape_price

# Test with a real product URL
url = "https://www.ebay.com/itm/404668560156"
result = scrape_price(url)
print("=== SCRAPER RESULT ===")
print(f"Name: {result['name']}")
print(f"Price: {result['price']}")
print(f"Image: {result['image']}")
print(f"URL: {result['url']}")