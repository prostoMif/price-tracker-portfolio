import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import Category, PriceSnapshot, Product, Store


CATEGORY_TITLES = {
    "electronics": "Электроника",
    "home-appliances": "Бытовая техника",
    "sneakers": "Кроссовки",
    "furniture": "Мебель",
    "beauty-and-care": "Красота и уход",
    "gaming": "Гейминг",
    "sports": "Спорт и фитнес",
    "kids": "Детские товары",
}

STORES = ["Ozon", "Wildberries", "Яндекс Маркет", "DNS", "М.Видео"]
STORE_URLS = {
    "Ozon": "https://www.ozon.ru/search/?text=",
    "Wildberries": "https://www.wildberries.ru/catalog/0/search.aspx?search=",
    "Яндекс Маркет": "https://market.yandex.ru/search?text=",
    "DNS": "https://www.dns-shop.ru/search/?q=",
    "М.Видео": "https://www.mvideo.ru/product-list-page?q=",
}

SEGMENT_MODELS = {
    "electronics": {
        "brands": ["Samsung", "Apple", "Xiaomi", "HONOR", "HUAWEI", "ASUS", "Lenovo", "Sony", "Logitech", "Razer"],
        "lines": ["Galaxy", "iPhone", "Redmi", "Magic", "Pura", "ROG", "Legion", "Xperia", "MX", "DeathAdder"],
        "suffixes": ["Ultra", "Pro", "Max", "Plus", "Lite"],
    },
    "home-appliances": {
        "brands": ["Bosch", "LG", "Samsung", "Midea", "Redmond", "Philips", "Dyson", "Tefal", "Beko", "Gorenje"],
        "lines": ["Serie", "Smart", "Power", "Clean", "Inverter", "Cook", "Home", "Jet", "Expert", "Prime"],
        "suffixes": ["X", "S", "Pro", "Plus", "Neo"],
    },
    "sneakers": {
        "brands": ["Nike", "Adidas", "New Balance", "Puma", "ASICS", "Reebok", "Jordan", "Hoka", "On", "Salomon"],
        "lines": ["Air", "Ultraboost", "Runner", "Street", "Cloud", "Zoom", "Court", "Pulse", "Flex", "Motion"],
        "suffixes": ["Pro", "Max", "OG", "Lite", "Prime"],
    },
    "furniture": {
        "brands": ["IKEA", "Hoff", "Askona", "Lazurit", "Shatura", "Dyatkovo", "MOON", "Mr.Doors", "BTS", "Leroy"],
        "lines": ["Malm", "Nova", "Loft", "Sigma", "Smart", "Neo", "Prime", "Comfort", "Modul", "Urban"],
        "suffixes": ["160", "200", "XL", "Plus", "S"],
    },
    "beauty-and-care": {
        "brands": ["Philips", "Braun", "Dyson", "Panasonic", "Oral-B", "Foreo", "Remington", "Babyliss", "Vichy", "Clinique"],
        "lines": ["Care", "Skin", "Series", "One", "Pro", "Hydra", "Smooth", "Luna", "Moisture", "Protect"],
        "suffixes": ["360", "5", "7", "9", "Elite"],
    },
    "gaming": {
        "brands": ["Sony", "Microsoft", "SteelSeries", "HyperX", "Razer", "Logitech", "AOC", "BenQ", "ASUS", "MSI"],
        "lines": ["PlayStation", "Xbox", "Arctis", "Cloud", "BlackWidow", "G Pro", "AGON", "Zowie", "TUF", "MAG"],
        "suffixes": ["Pro", "X", "V2", "Elite", "Max"],
    },
    "sports": {
        "brands": ["Xiaomi", "Garmin", "Polar", "Adidas", "Nike", "Wilson", "HEAD", "Decathlon", "Amazfit", "Puma"],
        "lines": ["Fit", "Run", "Active", "Pulse", "Trainer", "Power", "Move", "Sport", "Zone", "Core"],
        "suffixes": ["Pro", "2", "3", "Plus", "Max"],
    },
    "kids": {
        "brands": ["Happy Baby", "Chicco", "Peg Perego", "Lego", "Hasbro", "Fisher-Price", "Cybex", "Joie", "Bebetto", "Babyton"],
        "lines": ["Kids", "Junior", "Smart", "Play", "Go", "Neo", "Ride", "City", "Mini", "Plus"],
        "suffixes": ["S", "XL", "2", "3", "Pro"],
    },
}


def _slugify_name(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "-")
        .replace(".", "")
        .replace("+", "plus")
        .replace("'", "")
        .replace("/", "-")
    )


def _build_catalog() -> dict[str, list[str]]:
    catalog = {}
    for slug, cfg in SEGMENT_MODELS.items():
        names = []
        for idx in range(50):
            brand = cfg["brands"][idx % len(cfg["brands"])]
            line = cfg["lines"][idx % len(cfg["lines"])]
            suffix = cfg["suffixes"][idx % len(cfg["suffixes"])]
            model_num = 10 + idx
            names.append(f"{brand} {line} {model_num} {suffix}")
        catalog[slug] = names
    return catalog


def seed_if_empty(db: Session) -> None:
    if db.query(Product).count() > 0:
        return

    categories = []
    for slug, title in CATEGORY_TITLES.items():
        category = Category(name=title, slug=slug)
        db.add(category)
        categories.append(category)
    db.commit()

    stores = []
    for store_name in STORES:
        store = Store(name=store_name, slug=store_name.lower().replace(" ", "-"))
        db.add(store)
        stores.append(store)
    db.commit()

    catalog = _build_catalog()
    products = []
    for category in categories:
        for item in catalog[category.slug]:
            product = Product(
                name=item,
                brand=item.split(" ")[0],
                category_id=category.id,
            )
            db.add(product)
            products.append(product)
    db.commit()

    now = datetime.utcnow()
    for product in products:
        base_price = random.randint(2500, 120000)
        for day_back in range(35, -1, -1):
            ts = now - timedelta(days=day_back)
            for store in stores:
                fluctuation = random.uniform(0.88, 1.12)
                store_factor = random.uniform(0.96, 1.04)
                price = round(base_price * fluctuation * store_factor, 2)
                url = f"{STORE_URLS.get(store.name, 'https://example.com/search?q=')}{_slugify_name(product.name)}"
                db.add(
                    PriceSnapshot(
                        product_id=product.id,
                        store_id=store.id,
                        price=price,
                        product_url=url,
                        captured_at=ts,
                    )
                )
    db.commit()


def ensure_readable_product_names(db: Session) -> None:
    catalog = _build_catalog()
    categories = db.query(Category).all()
    for category in categories:
        expected_names = catalog.get(category.slug, [])
        if not expected_names:
            continue

        category_products = (
            db.query(Product)
            .filter(Product.category_id == category.id)
            .order_by(Product.id.asc())
            .all()
        )
        for idx, product in enumerate(category_products):
            target_name = expected_names[idx % len(expected_names)]
            if product.name != target_name:
                product.name = target_name
                product.brand = target_name.split(" ")[0]
    db.commit()


def ensure_catalog_size(db: Session, target_products: int = 400) -> None:
    categories_count = db.query(Category).count()
    products_count = db.query(Product).count()
    if categories_count == len(CATEGORY_TITLES) and products_count >= target_products:
        return

    db.query(PriceSnapshot).delete()
    db.query(Product).delete()
    db.query(Store).delete()
    db.query(Category).delete()
    db.commit()
    seed_if_empty(db)
