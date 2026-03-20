let chart;
let catalogOffset = 0;
const FAVORITES_KEY = "pricepulse_favorites";
const IMAGE_FALLBACK = "/static/product-fallback.svg";

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

function formatPrice(v) {
  return new Intl.NumberFormat("ru-RU").format(Math.round(v)) + " ₽";
}

function getFavorites() {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function setFavorites(ids) {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(ids.slice(0, 8)));
}

function toggleFavorite(id) {
  const pid = Number(id);
  const fav = getFavorites();
  const exists = fav.includes(pid);
  const next = exists ? fav.filter((x) => x !== pid) : [...fav, pid];
  setFavorites(next);
  return !exists;
}

function imageTag(src, alt, cls) {
  const safeAlt = String(alt || "").replace(/"/g, "&quot;");
  return `<img class="${cls}" src="${src}" alt="${safeAlt}" loading="lazy" onerror="this.onerror=null;this.src='${IMAGE_FALLBACK}'" />`;
}

function drawStats(data) {
  const container = document.getElementById("stats");
  if (!container) return;
  const cards = [
    { title: "Сегменты", value: data.categories },
    { title: "Товары", value: data.products },
    { title: "Магазины", value: data.stores },
    { title: "Среднее изменение 24ч", value: `${data.avg_change_24h_pct}%` },
  ];
  container.innerHTML = cards.map((c) => `<div class="stat-card"><h3>${c.title}</h3><p>${c.value}</p></div>`).join("");
}

function drawProducts(products, append = false) {
  const grid = document.getElementById("productsGrid");
  if (!grid) return;
  if (!products.length) {
    if (!append) {
      grid.innerHTML = "<p>Товары не найдены.</p>";
    }
    return;
  }
  const html = products.map((p) => {
    const cls = p.change_7d_pct > 0 ? "up" : "down";
    const sign = p.change_7d_pct > 0 ? "+" : "";
    return `
      <article class="product-card">
        ${imageTag(p.image_url, p.name, "product-image")}
        <h4>${p.name}</h4>
        <div class="meta">${p.brand} · ${p.category_name}</div>
        <div class="price-row"><span>Мин. цена</span><strong>${formatPrice(p.min_price)}</strong></div>
        <div class="price-row"><span>Средняя цена</span><strong>${formatPrice(p.avg_price)}</strong></div>
        <div class="price-row"><span>7д</span><span class="delta ${cls}">${sign}${p.change_7d_pct}%</span></div>
        <a href="/product/${p.id}"><button>Открыть товар</button></a>
        <button class="fav-btn ${getFavorites().includes(p.id) ? "is-favorite" : ""}" data-fav-id="${p.id}">
          ${getFavorites().includes(p.id) ? "В избранном" : "В избранное"}
        </button>
      </article>`;
  }).join("");
  if (append) {
    grid.insertAdjacentHTML("beforeend", html);
  } else {
    grid.innerHTML = html;
  }
  bindFavoriteButtons();
}

function drawMovers(blockId, items) {
  const target = document.getElementById(blockId);
  if (!target) return;
  target.innerHTML = `<div class="mini-list">${items.map((item) => `
      <div class="mini-item">
        <a href="/product/${item.id}">${item.name}</a>
        <span class="${item.change_7d_pct > 0 ? "delta up" : "delta down"}">${item.change_7d_pct > 0 ? "+" : ""}${item.change_7d_pct}%</span>
      </div>`).join("")}</div>`;
}

async function fillCategorySelect() {
  const select = document.getElementById("categorySelect");
  if (!select) return;
  const categories = await fetchJSON("/api/categories");
  select.innerHTML = `<option value="">Все сегменты</option>` + categories
    .map((x) => `<option value="${x.slug}">${x.name}</option>`)
    .join("");
}

async function loadCatalogProducts(reset = true) {
  if (reset) catalogOffset = 0;
  const category = document.getElementById("categorySelect")?.value || "";
  const q = document.getElementById("searchInput")?.value.trim() || "";
  const params = new URLSearchParams({ limit: "60", offset: String(catalogOffset) });
  if (category) params.set("category", category);
  if (q) params.set("q", q);
  const products = await fetchJSON(`/api/products?${params.toString()}`);
  drawProducts(products, !reset);
  catalogOffset += products.length;
}

async function drawProductChart(productId) {
  const historyData = await fetchJSON(`/api/products/${productId}/history?days=30`);
  const ctx = document.getElementById("priceChart");
  if (!ctx || !historyData.product) return;
  document.getElementById("productTitle").textContent = `${historyData.product.name}`;
  const productImage = document.getElementById("productImage");
  if (productImage) {
    productImage.src = historyData.product.image_url;
    productImage.alt = historyData.product.name;
    productImage.onerror = () => {
      productImage.onerror = null;
      productImage.src = IMAGE_FALLBACK;
    };
  }
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: historyData.history.map((x) => x.date),
      datasets: [{
        label: "Минимальная цена",
        data: historyData.history.map((x) => x.min_price),
        borderColor: "#6ea8fe",
        backgroundColor: "rgba(110, 168, 254, 0.16)",
        tension: 0.33,
      }],
    },
    options: { responsive: true },
  });
}

async function drawOffers(productId) {
  const offersData = await fetchJSON(`/api/products/${productId}/offers`);
  const target = document.getElementById("offersTable");
  if (!target || !offersData.product) return;
  target.innerHTML = `
    <table class="table">
      <thead>
        <tr><th>Магазин</th><th>Цена</th><th>Ссылка</th><th>Обновлено</th></tr>
      </thead>
      <tbody>
        ${offersData.offers.map((x) => `
          <tr>
            <td>${x.store_name}</td>
            <td>${formatPrice(x.price)}</td>
            <td><a href="${x.url}" target="_blank" rel="noreferrer">Открыть</a></td>
            <td>${new Date(x.captured_at).toLocaleString("ru-RU")}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function bindFavoriteButtons() {
  document.querySelectorAll("[data-fav-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.favId);
      const isNowFavorite = toggleFavorite(id);
      btn.classList.toggle("is-favorite", isNowFavorite);
      btn.textContent = isNowFavorite ? "В избранном" : "В избранное";
    });
  });
}

async function drawSegmentTrends() {
  const target = document.getElementById("segmentTable");
  if (!target) return;
  const data = await fetchJSON("/api/segments/trends");
  target.innerHTML = `
    <table class="table">
      <thead><tr><th>Сегмент</th><th>Товаров</th><th>Средняя цена</th><th>Изм. 7д</th></tr></thead>
      <tbody>
      ${data.map((x) => `<tr>
        <td>${x.category_name}</td>
        <td>${x.products_count}</td>
        <td>${formatPrice(x.avg_price)}</td>
        <td class="${x.avg_change_7d_pct > 0 ? "delta up" : "delta down"}">${x.avg_change_7d_pct > 0 ? "+" : ""}${x.avg_change_7d_pct}%</td>
      </tr>`).join("")}
      </tbody>
    </table>`;
}

async function triggerCollector() {
  const btn = document.getElementById("refreshCollectorBtn");
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = "Обновляю...";
  try {
    await fetchJSON("/api/collector/run", { method: "POST" });
    const overview = await fetchJSON("/api/overview");
    drawStats(overview);
  } finally {
    btn.disabled = false;
    btn.textContent = "Обновить цены";
  }
}

async function drawDealsOfDay() {
  const target = document.getElementById("dealsTable");
  if (!target) return;
  const rows = await fetchJSON("/api/deals/day?limit=30");
  target.innerHTML = `
    <table class="table">
      <thead><tr><th></th><th>Товар</th><th>Сегмент</th><th>Изм. 7д</th><th>Лучшая цена</th><th>Магазин</th><th>Ссылка</th></tr></thead>
      <tbody>
      ${rows.map((x) => `<tr>
        <td>${imageTag(x.image_url, x.name, "thumb")}</td>
        <td><a href="/product/${x.id}">${x.name}</a></td>
        <td>${x.category_name}</td>
        <td class="delta down">${x.change_7d_pct}%</td>
        <td>${x.best_offer_price ? formatPrice(x.best_offer_price) : "-"}</td>
        <td>${x.best_offer_store || "-"}</td>
        <td>${x.best_offer_url ? `<a href="${x.best_offer_url}" target="_blank" rel="noreferrer">Открыть</a>` : "-"}</td>
      </tr>`).join("")}
      </tbody>
    </table>`;
}

async function drawCompare() {
  const target = document.getElementById("compareTable");
  if (!target) return;
  const fav = getFavorites();
  if (!fav.length) {
    target.innerHTML = "<p>Пока нет избранных товаров. Добавь их в каталоге или на странице товара.</p>";
    return;
  }
  const rows = await fetchJSON(`/api/products/bulk?ids=${fav.join(",")}`);
  if (!rows.length) {
    target.innerHTML = "<p>Не удалось загрузить товары для сравнения.</p>";
    return;
  }
  target.innerHTML = `
    <table class="table">
      <thead><tr><th></th><th>Товар</th><th>Сегмент</th><th>Мин. цена</th><th>Средняя</th><th>Изм. 7д</th><th></th></tr></thead>
      <tbody>
      ${rows.map((x) => `<tr>
        <td>${imageTag(x.image_url, x.name, "thumb")}</td>
        <td>${x.name}</td>
        <td>${x.category_name}</td>
        <td>${formatPrice(x.min_price)}</td>
        <td>${formatPrice(x.avg_price)}</td>
        <td class="${x.change_7d_pct > 0 ? "delta up" : "delta down"}">${x.change_7d_pct > 0 ? "+" : ""}${x.change_7d_pct}%</td>
        <td><a href="/product/${x.id}">Открыть</a></td>
      </tr>`).join("")}
      </tbody>
    </table>`;
}

async function init() {
  const page = document.body.dataset.page;
  if (document.getElementById("refreshCollectorBtn")) {
    document.getElementById("refreshCollectorBtn").addEventListener("click", triggerCollector);
  }

  if (page === "home") {
    drawStats(await fetchJSON("/api/overview"));
    const movers = await fetchJSON("/api/movers?limit=8");
    drawMovers("topGrowth", movers.top_growth);
    drawMovers("topDiscounts", movers.top_discounts);
  }

  if (page === "catalog") {
    await fillCategorySelect();
    await loadCatalogProducts(true);
    document.getElementById("loadBtn").addEventListener("click", () => loadCatalogProducts(true));
    document.getElementById("loadMoreBtn").addEventListener("click", () => loadCatalogProducts(false));
  }

  if (page === "product") {
    const productId = document.body.dataset.productId;
    await drawProductChart(productId);
    await drawOffers(productId);
    const favBtn = document.getElementById("favoriteProductBtn");
    if (favBtn) {
      const pid = Number(productId);
      const isFav = getFavorites().includes(pid);
      favBtn.textContent = isFav ? "В избранном" : "В избранное";
      favBtn.classList.toggle("is-favorite", isFav);
      favBtn.addEventListener("click", () => {
        const nowFav = toggleFavorite(pid);
        favBtn.textContent = nowFav ? "В избранном" : "В избранное";
        favBtn.classList.toggle("is-favorite", nowFav);
      });
    }
  }

  if (page === "analytics") {
    await drawSegmentTrends();
  }

  if (page === "deals") {
    await drawDealsOfDay();
  }

  if (page === "compare") {
    await drawCompare();
  }
}

init();
