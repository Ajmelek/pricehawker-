from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship, synonym
from datetime import datetime
from app.db.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)
    url = Column(String(2000), nullable=True, unique=True)
    image = Column(String(2000), nullable=True)
    target_price = Column(Float, nullable=True)
    currency = Column(String(10), default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)

    # One product has many price records
    price_history = relationship("PriceHistory", back_populates="product")

    product_name = synonym("name")

    @property
    def current_price(self) -> float:
        cached = self.__dict__.get("_current_price")
        if cached is not None:
            return float(cached)
        if not self.price_history:
            return 0.0
        latest = max(self.price_history, key=lambda row: row.scraped_at or datetime.min)
        return float(latest.price or 0.0)

    @current_price.setter
    def current_price(self, value: float) -> None:
        self.__dict__["_current_price"] = float(value or 0.0)

    @property
    def updated_at(self) -> datetime:
        if not self.price_history:
            return self.created_at
        latest = max(self.price_history, key=lambda row: row.scraped_at or datetime.min)
        return latest.scraped_at or self.created_at

    @updated_at.setter
    def updated_at(self, value: datetime) -> None:
        # Backward-compatible no-op: DB schema does not have products.updated_at.
        self.__dict__["_updated_at"] = value


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    recorded_at = synonym("scraped_at")

    # Link back to product
    product = relationship("Product", back_populates="price_history")