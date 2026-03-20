import asyncio
from html import escape

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db, SessionLocal
from .models import Product
from .seed import CATEGORY_TITLES, ensure_catalog_size, ensure_readable_product_names, seed_if_empty
from .services import (
    get_deals_of_day,
    get_categories,
    get_history,
    get_overview,
    get_product_offers,
    get_products_by_ids,
    get_products,
    get_segment_trends,
    get_stores,
    get_top_movers,
    simulate_collect_cycle,
)

app = FastAPI(title="Price Tracker Portfolio", version="1.0.0")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

collect_task = None


@app.on_event("startup")
async def startup() -> None:
    global collect_task
    Base.metadata.create_all(bind=engine)
    _ensure_optional_columns()
    db = SessionLocal()
    seed_if_empty(db)
    ensure_catalog_size(db, target_products=400)
    ensure_readable_product_names(db)
    db.close()
    collect_task = asyncio.create_task(_collect_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    if collect_task:
        collect_task.cancel()


async def _collect_loop() -> None:
    while True:
        await asyncio.sleep(120)
        db = SessionLocal()
        try:
            simulate_collect_cycle(db)
        finally:
            db.close()


def _ensure_optional_columns() -> None:
    with engine.connect() as conn:
        columns = [row[1] for row in conn.execute(text("PRAGMA table_info(price_snapshots)"))]
        if "product_url" not in columns:
            conn.execute(text("ALTER TABLE price_snapshots ADD COLUMN product_url VARCHAR(500) DEFAULT ''"))
            conn.commit()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "categories": [{"slug": k, "name": v} for k, v in CATEGORY_TITLES.items()]},
    )


@app.get("/catalog", response_class=HTMLResponse)
def catalog_page(request: Request):
    return templates.TemplateResponse("catalog.html", {"request": request})


@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_page(request: Request, product_id: int):
    return templates.TemplateResponse("product.html", {"request": request, "product_id": product_id})


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request):
    return templates.TemplateResponse("analytics.html", {"request": request})


@app.get("/deals", response_class=HTMLResponse)
def deals_page(request: Request):
    return templates.TemplateResponse("deals.html", {"request": request})


@app.get("/compare", response_class=HTMLResponse)
def compare_page(request: Request):
    return templates.TemplateResponse("compare.html", {"request": request})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/overview")
def overview(db: Session = Depends(get_db)):
    return get_overview(db)


@app.get("/api/products")
def products(
    category: str | None = Query(default=None),
    store: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return get_products(db, category_slug=category, store_slug=store, q=q, limit=limit, offset=offset)


@app.get("/api/categories")
def categories(db: Session = Depends(get_db)):
    return get_categories(db)


@app.get("/api/stores")
def stores(db: Session = Depends(get_db)):
    return get_stores(db)


@app.get("/api/products/{product_id}/history")
def product_history(product_id: int, days: int = Query(default=30, ge=7, le=180), db: Session = Depends(get_db)):
    return get_history(db, product_id=product_id, days=days)


@app.get("/api/products/{product_id}/offers")
def product_offers(product_id: int, db: Session = Depends(get_db)):
    return get_product_offers(db, product_id=product_id)


@app.get("/api/products/{product_id}/image")
def product_image(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        svg = """
<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">
  <rect width="640" height="420" fill="#0f1a33"/>
  <text x="50%" y="50%" fill="#dcebff" text-anchor="middle" dominant-baseline="middle" font-size="28" font-family="Inter, Arial">No Image</text>
</svg>
"""
        return Response(content=svg, media_type="image/svg+xml")

    safe_name = escape(product.name)
    safe_brand = escape(product.brand)
    hue = 180 + (product_id * 17) % 140
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="hsl({hue}, 72%, 36%)"/>
      <stop offset="100%" stop-color="#0d1530"/>
    </linearGradient>
  </defs>
  <rect width="640" height="420" fill="url(#bg)"/>
  <circle cx="560" cy="80" r="90" fill="rgba(255,255,255,0.08)"/>
  <circle cx="90" cy="340" r="120" fill="rgba(255,255,255,0.06)"/>
  <text x="40" y="72" fill="#e9f2ff" font-family="Inter, Arial" font-size="26" font-weight="700">{safe_brand}</text>
  <foreignObject x="40" y="98" width="560" height="240">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Inter, Arial; color:#f3f7ff; font-size:34px; font-weight:800; line-height:1.15;">
      {safe_name}
    </div>
  </foreignObject>
  <text x="40" y="390" fill="rgba(230,240,255,0.85)" font-family="Inter, Arial" font-size="16">PricePulse Product Card</text>
</svg>
"""
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/movers")
def movers(limit: int = Query(default=10, ge=3, le=25), db: Session = Depends(get_db)):
    return get_top_movers(db, limit=limit)


@app.get("/api/segments/trends")
def segment_trends(db: Session = Depends(get_db)):
    return get_segment_trends(db)


@app.get("/api/products/bulk")
def products_bulk(ids: str = Query(default=""), db: Session = Depends(get_db)):
    parsed = []
    for token in ids.split(","):
        token = token.strip()
        if token.isdigit():
            parsed.append(int(token))
    return get_products_by_ids(db, parsed[:10])


@app.get("/api/deals/day")
def deals_day(limit: int = Query(default=30, ge=5, le=60), db: Session = Depends(get_db)):
    return get_deals_of_day(db, limit=limit)


@app.post("/api/collector/run")
def run_collector(db: Session = Depends(get_db)):
    return simulate_collect_cycle(db)
