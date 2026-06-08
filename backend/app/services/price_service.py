from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import HTTPException
from app.models.product import Product, PriceHistory
from app.scraper.price_scraper import scrape_price


async def add_product(db: Session, url: str, target_price: float = None, product_name: str = ""):
    normalized_url = (url or "").strip()
    if not normalized_url:
        raise ValueError("URL is required.")
    if len(normalized_url) > 2000:
        raise ValueError("URL is too long. Please paste a valid product URL.")
    if not (normalized_url.startswith("http://") or normalized_url.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")

    existing = db.query(Product).filter(Product.url == normalized_url).first()
    if existing:
        return existing

    scraped       = await scrape_price(normalized_url, product_name or "")
    current_price = float(scraped.get("price", 0.0) or 0.0)
    resolved_name = (scraped.get("title") or product_name or normalized_url).strip()
    image_url     = scraped.get("image") or None

    product = Product(
        name=resolved_name,
        url=normalized_url,
        image=image_url,
        target_price=target_price,
        currency="USD",
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    price_record = PriceHistory(
        product_id=product.id,
        price=current_price,
        scraped_at=datetime.utcnow()
    )
    db.add(price_record)
    db.commit()
    db.refresh(product)

    return product


def get_all_products(db: Session):
    return db.query(Product).all()


def get_product_by_id(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()


async def refresh_product_price(db: Session, product_id: int):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    scraped   = await scrape_price(product.url or "", "")
    new_price = float(scraped.get("price", 0.0) or 0.0)
    new_name  = (scraped.get("title") or product.name or "").strip()
    new_image = scraped.get("image") or product.image  # keep old if new scrape missed it

    product.current_price = new_price
    product.name          = new_name
    product.image         = new_image
    product.updated_at    = datetime.utcnow()

    history_entry = PriceHistory(
        product_id=product_id,
        price=new_price,
        scraped_at=datetime.utcnow(),
    )
    db.add(history_entry)
    db.commit()
    db.refresh(product)

    return product