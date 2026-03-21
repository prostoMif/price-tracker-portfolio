# PricePulse - мониторинг цен для портфолио

Веб-приложение для мониторинга и аналитики цен по ~400 товарам из 8 сегментов:
- Электроника
- Бытовая техника
- Кроссовки
- Мебель
- Красота и уход
- Гейминг
- Спорт и фитнес
- Детские товары

## Что умеет
- Каталог товаров с фильтрацией по сегментам и поиском
- Многостраничный фронтенд: Главная, Каталог, Товар, Аналитика
- Текущая минимальная и средняя цена
- Изменение цены за 7 дней
- График динамики цены по выбранному товару
- Таблица офферов по магазинам с ценой и ссылкой на товар
- Имитация цикла сбора цен из магазинов через API (`POST /api/collector/run`)
- Фоновый цикл обновления данных каждые 120 секунд

## Технологии
- FastAPI
- SQLAlchemy
- SQLite
- Jinja2 + Chart.js

## Запуск локально
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Открыть: `http://127.0.0.1:8000`

## API
- `GET /api/health`
- `GET /api/overview`
- `GET /api/products?category=&q=&limit=&offset=`
- `GET /api/products/{id}/history?days=30`
- `GET /api/products/{id}/offers`
- `GET /api/categories`
- `GET /api/stores`
- `GET /api/movers`
- `GET /api/segments/trends`
- `POST /api/collector/run`

## Идея для реального парсера
В текущем MVP данные обновляются симуляцией. Для production версии достаточно заменить `simulate_collect_cycle()` на набор адаптеров парсеров (Ozon/WB/Я.Маркет и т.д.) с унифицированным интерфейсом.

## Публикация без своего хостинга (Render)
1. Создай репозиторий на GitHub и загрузи туда проект.
2. На [Render](https://render.com) нажми **New +** -> **Blueprint**.
3. Выбери свой GitHub-репозиторий: Render увидит `render.yaml` и создаст сервис автоматически.
4. После деплоя получишь публичный URL вида `https://pricepulse-portfolio.onrender.com`.
5. Этот URL добавляй в портфолио на биржах.

## Railway (Railpack / mise)
Версия Python зафиксирована на **3.12.8** (файлы `.python-version` и `mise.toml`), чтобы избежать ошибки установки **Python 3.13** на билдере (`missing a lib directory`).

**Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (см. также `Procfile`).
