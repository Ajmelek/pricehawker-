from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.db.database import get_db
from app.agents.pricing_agent import analyze_price
from app.schemas.product import ProductCreate, ProductWithHistory, AiAnalysis
from app.services.price_service import (
    add_product,
    get_all_products,
    get_product_by_id,
    refresh_product_price
)
from typing import List
import httpx


router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/image-proxy")
async def image_proxy(url: str):
    """
    Proxy Amazon product images through the backend so the browser
    never makes a direct request to Amazon CDN (which blocks localhost).
    Usage: /products/image-proxy?url=https://m.media-amazon.com/...
    """
    if not url.startswith("https://m.media-amazon.com"):
        raise HTTPException(status_code=400, detail="Only Amazon media URLs allowed")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.amazon.com/",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.get(url)

        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Image not found")

        content_type = resp.headers.get("content-type", "image/jpeg")

        return Response(
            content=resp.content,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # cache 24h
                "Access-Control-Allow-Origin": "*",
            }
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Image fetch timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ProductWithHistory)
async def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    url = (product.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")
    if len(url) > 2000:
        raise HTTPException(status_code=400, detail="URL is too long.")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        return await add_product(db, url, product.target_price, "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not save product.") from exc


@router.get("/", response_model=List[ProductWithHistory])
def list_products(db: Session = Depends(get_db)):
    return get_all_products(db)


@router.get("/{product_id}", response_model=ProductWithHistory)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/{product_id}/refresh", response_model=ProductWithHistory)
async def refresh_price_route(product_id: int, db: Session = Depends(get_db)):
    return await refresh_product_price(db, product_id)


@router.get("/{product_id}/analyze", response_model=AiAnalysis)
def analyze_product_price(product_id: int, db: Session = Depends(get_db)):
    return analyze_price(db, product_id)