from cerebras.cloud.sdk import Cerebras
import re
from app.core.config import settings
from app.models.product import Product, PriceHistory
from sqlalchemy.orm import Session

client = Cerebras(api_key=settings.cerebras_api_key)

def parse_cerebras_response(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    rec = "BUY NOW" if re.search(r"\bBUY\b", text, re.I) else "WAIT"

    conf_match = re.search(r"CONFIDENCE[:\s]+(\w+)", text, re.I)
    conf_map = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}
    conf_raw = conf_match.group(1).upper() if conf_match else "MEDIUM"
    confidence = conf_map.get(conf_raw, "MEDIUM")

    reason_match = re.search(r"REASON[:\s]+(.+?)(?=PREDICTION:|$)", text, re.I | re.S)
    reason = reason_match.group(1).strip() if reason_match else text

    pred_match = re.search(r"PREDICTION[:\s]+(.+)", text, re.I | re.S)
    prediction = pred_match.group(1).strip() if pred_match else ""

    return {
        "recommendation": rec,
        "confidence": confidence,
        "reason": reason,
        "prediction": prediction,
    }


def analyze_price(db: Session, product_id: int) -> dict:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return {"error": "Product not found"}

    history = db.query(PriceHistory)\
        .filter(PriceHistory.product_id == product_id)\
        .order_by(PriceHistory.recorded_at.asc())\
        .all()

    if not history:
        return {"error": "No price history found"}

    prices = [f"${h.price} on {h.recorded_at.strftime('%Y-%m-%d %H:%M')}" for h in history]
    current_price = history[-1].price
    lowest_price = min(h.price for h in history)
    highest_price = max(h.price for h in history)
    target_price = product.target_price

    prompt = f"""
You are an expert e-commerce pricing analyst AI agent.

Product: {product.product_name}
Current Price: ${current_price}
Lowest Price Ever: ${lowest_price}
Highest Price Ever: ${highest_price}
Target Price Set By User: ${target_price if target_price else 'Not set'}

Price History (oldest to newest):
{chr(10).join(prices)}

Based on this data, provide:
1. A clear BUY or WAIT recommendation
2. A confidence level (High/Medium/Low)
3. A short reason (2-3 sentences)
4. A price prediction for next week

Respond in this exact format:
RECOMMENDATION: [BUY NOW or WAIT]
CONFIDENCE: [High/Medium/Low]
REASON: [your reason here]
PREDICTION: [your price prediction here]
"""

    response = client.chat.completions.create(
        model="llama3.1-8b",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )

    text = response.choices[0].message.content.strip()
    print("Cerebras response:", text)
    return parse_cerebras_response(text)