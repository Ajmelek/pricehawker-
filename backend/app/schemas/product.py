from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class PriceHistorySchema(BaseModel):
    id: int
    price: float
    scraped_at: datetime
    recorded_at: Optional[datetime] = None  # backward compat alias

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    url: str
    product_name: Optional[str] = ""
    target_price: Optional[float] = None


class ProductWithHistory(BaseModel):
    id: int
    product_name: str
    url: Optional[str] = None
    image: Optional[str] = None          # ← THIS WAS MISSING
    current_price: float = 0.0
    target_price: Optional[float] = None
    currency: Optional[str] = "USD"
    created_at: datetime
    updated_at: datetime
    price_history: List[PriceHistorySchema] = []

    class Config:
        from_attributes = True


class AiAnalysis(BaseModel):
    recommendation: str
    confidence: str
    reason: str
    prediction: str