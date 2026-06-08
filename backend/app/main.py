from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine, Base
from app.api.routes import products
import app.models.product

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PriceHawk AI",
    description="AI-powered e-commerce price tracker and optimizer",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)

@app.get("/")
def root():
    return {"message": "PriceHawk AI is running 🦅"}

@app.get("/health")
def health():
    return {"status": "healthy"}