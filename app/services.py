import random
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Category, PriceSnapshot, Product, Store


def _product_image_url(product_id: int, product_name: str) -> str:
    _ = product_name
    return f"/api/products/{product_id}/image"


def _latest_per_product_subquery(db: Session):
    return (
        db.query(
            PriceSnapshot.product_id,
            func.max(PriceSnapshot.captured_at).label("latest_ts"),
        )
        .group_by(PriceSnapshot.product_id)
        .subquery()
    )


def get_overview(db: Session) -> dict:
    categories_count = db.query(Category).count()
    products_count = db.query(Product).count()
    stores_count = db.query(Store).count()

    global_latest_ts = db.query(func.max(PriceSnapshot.captured_at)).scalar()
    day_ago = (global_latest_ts or datetime.utcnow()) - timedelta(days=1)

    latest_per_product = _latest_per_product_subquery(db)
    latest_prices = (
        db.query(PriceSnapshot.product_id, func.min(PriceSnapshot.price).label("latest_price"))
        .join(
            latest_per_product,
            (latest_per_product.c.product_id == PriceSnapshot.product_id)
            & (latest_per_product.c.latest_ts == PriceSnapshot.captured_at),
        )
        .group_by(PriceSnapshot.product_id)
        .subquery()
    )
    previous_prices = (
        db.query(PriceSnapshot.product_id, func.min(PriceSnapshot.price).label("prev_price"))
        .filter(PriceSnapshot.captured_at >= day_ago, PriceSnapshot.captured_at < global_latest_ts)
        .group_by(PriceSnapshot.product_id)
        .subquery()
    )
    avg_change = (
        db.query(func.avg((latest_prices.c.latest_price - previous_prices.c.prev_price) / previous_prices.c.prev_price * 100))
        .join(previous_prices, previous_prices.c.product_id == latest_prices.c.product_id)
        .scalar()
    )

    return {
        "categories": categories_count,
        "products": products_count,
        "stores": stores_count,
        "avg_change_24h_pct": round(avg_change or 0.0, 2),
        "latest_snapshot_at": global_latest_ts.isoformat() if global_latest_ts else None,
    }


def get_products(
    db: Session,
    category_slug: str | None = None,
    store_slug: str | None = None,
    q: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> list[dict]:
    global_latest_ts = db.query(func.max(PriceSnapshot.captured_at)).scalar()
    week_ago = (global_latest_ts or datetime.utcnow()) - timedelta(days=7)

    latest_per_product = _latest_per_product_subquery(db)

    query = (
        db.query(
            Product.id,
            Product.name,
            Product.brand,
            Category.name.label("category_name"),
            Category.slug.label("category_slug"),
            func.min(PriceSnapshot.price).label("min_price"),
            func.avg(PriceSnapshot.price).label("avg_price"),
        )
        .join(Category, Category.id == Product.category_id)
        .join(PriceSnapshot, PriceSnapshot.product_id == Product.id)
        .join(
            latest_per_product,
            (latest_per_product.c.product_id == PriceSnapshot.product_id)
            & (latest_per_product.c.latest_ts == PriceSnapshot.captured_at),
        )
        .group_by(Product.id, Category.name, Category.slug)
    )

    if category_slug:
        query = query.filter(Category.slug == category_slug)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))

    rows = query.offset(offset).limit(limit).all()

    result = []
    for row in rows:
        prev = (
            db.query(func.min(PriceSnapshot.price))
            .join(Store, Store.id == PriceSnapshot.store_id)
            .filter(
                PriceSnapshot.product_id == row.id,
                PriceSnapshot.captured_at >= week_ago,
                PriceSnapshot.captured_at < global_latest_ts,
                Store.slug == store_slug if store_slug else True,
            )
            .scalar()
        )
        pct = 0.0
        if prev and prev > 0:
            pct = round((row.min_price - prev) / prev * 100, 2)

        result.append(
            {
                "id": row.id,
                "name": row.name,
                "brand": row.brand,
                "image_url": _product_image_url(row.id, row.name),
                "category_name": row.category_name,
                "category_slug": row.category_slug,
                "min_price": round(row.min_price, 2),
                "avg_price": round(row.avg_price, 2),
                "change_7d_pct": pct,
            }
        )
    return result


def get_history(db: Session, product_id: int, days: int = 30) -> dict:
    from_dt = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            func.date(PriceSnapshot.captured_at).label("day"),
            func.min(PriceSnapshot.price).label("min_price"),
            func.avg(PriceSnapshot.price).label("avg_price"),
        )
        .filter(PriceSnapshot.product_id == product_id, PriceSnapshot.captured_at >= from_dt)
        .group_by(func.date(PriceSnapshot.captured_at))
        .order_by(func.date(PriceSnapshot.captured_at))
        .all()
    )
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return {"product": None, "history": []}

    history = [
        {"date": str(item.day), "min_price": round(item.min_price, 2), "avg_price": round(item.avg_price, 2)}
        for item in rows
    ]
    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "image_url": _product_image_url(product.id, product.name),
        },
        "history": history,
    }


def get_product_offers(db: Session, product_id: int) -> dict:
    latest_ts = (
        db.query(func.max(PriceSnapshot.captured_at))
        .filter(PriceSnapshot.product_id == product_id)
        .scalar()
    )
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or not latest_ts:
        return {"product": None, "offers": []}

    rows = (
        db.query(Store.name, Store.slug, PriceSnapshot.price, PriceSnapshot.product_url, PriceSnapshot.captured_at)
        .join(Store, Store.id == PriceSnapshot.store_id)
        .filter(PriceSnapshot.product_id == product_id, PriceSnapshot.captured_at == latest_ts)
        .order_by(PriceSnapshot.price.asc())
        .all()
    )
    offers = [
        {
            "store_name": row.name,
            "store_slug": row.slug,
            "price": round(row.price, 2),
            "url": row.product_url or "",
            "captured_at": row.captured_at.isoformat(),
        }
        for row in rows
    ]
    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "image_url": _product_image_url(product.id, product.name),
        },
        "offers": offers,
    }


def get_categories(db: Session) -> list[dict]:
    rows = db.query(Category).order_by(Category.name.asc()).all()
    return [{"id": row.id, "name": row.name, "slug": row.slug} for row in rows]


def get_stores(db: Session) -> list[dict]:
    rows = db.query(Store).order_by(Store.name.asc()).all()
    return [{"id": row.id, "name": row.name, "slug": row.slug} for row in rows]


def get_top_movers(db: Session, limit: int = 10) -> dict:
    products = get_products(db, limit=400)
    up = sorted(products, key=lambda x: x["change_7d_pct"], reverse=True)[:limit]
    down = sorted(products, key=lambda x: x["change_7d_pct"])[:limit]
    return {"top_growth": up, "top_discounts": down}


def get_segment_trends(db: Session) -> list[dict]:
    latest = get_products(db, limit=500)
    by_segment = {}
    for row in latest:
        slug = row["category_slug"]
        if slug not in by_segment:
            by_segment[slug] = {"category_name": row["category_name"], "sum_price": 0.0, "sum_change": 0.0, "count": 0}
        by_segment[slug]["sum_price"] += row["avg_price"]
        by_segment[slug]["sum_change"] += row["change_7d_pct"]
        by_segment[slug]["count"] += 1

    result = []
    for slug, data in by_segment.items():
        count = max(data["count"], 1)
        result.append(
            {
                "category_slug": slug,
                "category_name": data["category_name"],
                "avg_price": round(data["sum_price"] / count, 2),
                "avg_change_7d_pct": round(data["sum_change"] / count, 2),
                "products_count": data["count"],
            }
        )
    return sorted(result, key=lambda x: x["category_name"])


def get_products_by_ids(db: Session, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    all_rows = get_products(db, limit=500, offset=0)
    selected = [row for row in all_rows if row["id"] in ids]
    order_map = {pid: idx for idx, pid in enumerate(ids)}
    return sorted(selected, key=lambda x: order_map.get(x["id"], 10**9))


def get_deals_of_day(db: Session, limit: int = 30) -> list[dict]:
    rows = get_products(db, limit=500, offset=0)
    discounts = sorted(rows, key=lambda x: x["change_7d_pct"])[:limit]
    enriched = []
    for item in discounts:
        offers = get_product_offers(db, item["id"]).get("offers", [])
        best_offer = offers[0] if offers else None
        enriched.append(
            {
                **item,
                "best_offer_store": best_offer["store_name"] if best_offer else None,
                "best_offer_price": best_offer["price"] if best_offer else None,
                "best_offer_url": best_offer["url"] if best_offer else "",
            }
        )
    return enriched


def simulate_collect_cycle(db: Session) -> dict:
    latest_per_product = (
        db.query(
            PriceSnapshot.product_id,
            func.max(PriceSnapshot.captured_at).label("latest_ts"),
        )
        .group_by(PriceSnapshot.product_id)
        .subquery()
    )
    latest_rows = (
        db.query(PriceSnapshot.product_id, func.min(PriceSnapshot.price).label("base_price"))
        .join(
            latest_per_product,
            (latest_per_product.c.product_id == PriceSnapshot.product_id)
            & (latest_per_product.c.latest_ts == PriceSnapshot.captured_at),
        )
        .group_by(PriceSnapshot.product_id)
        .all()
    )
    base_map = {row.product_id: row.base_price for row in latest_rows}
    latest_urls_rows = (
        db.query(PriceSnapshot.product_id, PriceSnapshot.store_id, PriceSnapshot.product_url)
        .join(
            latest_per_product,
            (latest_per_product.c.product_id == PriceSnapshot.product_id)
            & (latest_per_product.c.latest_ts == PriceSnapshot.captured_at),
        )
        .all()
    )
    url_map = {(row.product_id, row.store_id): row.product_url for row in latest_urls_rows}

    products = db.query(Product).all()
    stores = db.query(Store).all()

    if not base_map:
        return {"updated": 0}

    cycle_ts = datetime.utcnow()
    updated = 0
    for product in products:
        base = base_map.get(product.id)
        if not base:
            continue
        for store in stores:
            drift = random.uniform(0.97, 1.03)
            noise = random.uniform(0.98, 1.02)
            new_price = round(base * drift * noise, 2)
            db.add(
                PriceSnapshot(
                    product_id=product.id,
                    store_id=store.id,
                    price=new_price,
                    product_url=url_map.get((product.id, store.id), ""),
                    captured_at=cycle_ts,
                )
            )
            updated += 1
    db.commit()
    return {"updated": updated}
