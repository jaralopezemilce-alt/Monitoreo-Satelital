// Visor del monitor de deforestación. Habla con la API del mismo servidor (FastAPI).
// Sin CDN ni teselas online: el fondo es la imagen Sentinel-2 que sirve la API.

const API = "";               // mismo origen: http://127.0.0.1:8000
const SPLIT_NAMES = { train: "entrenamiento", val: "validación", test: "prueba" };
const ZONE_NAMES = { A_boqueron: "A · Boquerón", B_alto_paraguay: "B · Alto Paraguay" };

const $ = (id) => document.getElementById(id);
const map = L.map("map", { zoomControl: true, attributionControl: true, minZoom: 10 });
map.attributionControl.setPrefix("Leaflet");
map.attributionControl.addAttribution("Sentinel-2 (ESA Copernicus) · MapBiomas Chaco");

const state = { zones: [], zone: null, role: "historical_2022_0", maxArea: 4 };
const layers = {
  background: null,
  outline: L.layerGroup().addTo(map),
  splits: L.layerGroup().addTo(map),
  result: L.layerGroup().addTo(map),
  rect: null,
};
let splitFeatures = [];

// ---------- utilidades ----------

function showError(msg) {
  $("error").textContent = msg;
  $("error").hidden = !msg;
}

async function getJSON(url, options) {
  const r = await fetch(API + url, options);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ? String(body.detail) : `Error ${r.status} en ${url}`);
  return body;
}

// Área aproximada (km²) de un rectángulo lon/lat: suficiente para avisar antes de pedir.
function areaKm2(bounds) {
  const s = bounds.getSouth(), n = bounds.getNorth();
  const latMid = ((s + n) / 2) * Math.PI / 180;
  const dx = (bounds.getEast() - bounds.getWest()) * 111.32 * Math.cos(latMid);
  const dy = (n - s) * 110.57;
  return Math.abs(dx * dy);
}

const fmt = (v, d = 1) => Number(v).toLocaleString("es-PY", { minimumFractionDigits: d, maximumFractionDigits: d });

// ---------- zonas y fondo ----------

async function loadZones() {
  try {
    state.zones = await getJSON("/zones");
  } catch (e) {
    $("zone-dates").textContent = "";
    showError(`No se pudo leer la API: ${e.message}`);
    return;
  }
  const sel = $("zone");
  sel.innerHTML = state.zones.map((z) => `<option value="${z.id}">${ZONE_NAMES[z.id] || z.id}</option>`).join("");
  sel.addEventListener("change", () => selectZone(sel.value));
  if (state.zones.length) selectZone(state.zones[0].id);
}

async function selectZone(id) {
  state.zone = state.zones.find((z) => z.id === id);
  state.maxArea = state.zone.max_area_km2 ?? 4;
  $("max-area").textContent = fmt(state.maxArea, 0);
  const f = state.zone.fechas;
  $("zone-dates").textContent =
    `Antes: ${f.historical_2022_0.slice(0, 10)} · Después: ${f.historical_2023_1.slice(0, 10)} · ${state.zone.crs}`;
  clearResult();
  layers.outline.clearLayers();
  const outline = L.polygon(state.zone.outline.map(([x, y]) => [y, x]),
    { color: "#ffffff", weight: 2, fill: false, interactive: false });
  layers.outline.addLayer(outline);
  map.fitBounds(outline.getBounds(), { padding: [20, 20] });
  await Promise.all([loadBackground(), loadSplits()]);
}

async function loadBackground() {
  const z = state.zone;
  try {
    const r = await fetch(`${API}/zones/${z.id}/rgb/${state.role}.png`);
    if (!r.ok) throw new Error(`Error ${r.status}`);
    const [w, s, e, n] = r.headers.get("X-Bounds").split(",").map(Number);
    const url = URL.createObjectURL(await r.blob());
    if (layers.background) map.removeLayer(layers.background);
    layers.background = L.imageOverlay(url, [[s, w], [n, e]], { interactive: false }).addTo(map);
    layers.background.bringToBack();
  } catch (e) {
    showError(`No se pudo cargar la imagen de fondo: ${e.message}`);
  }
}

async function loadSplits() {
  layers.splits.clearLayers();
  splitFeatures = [];
  try {
    const fc = await getJSON(`/zones/${state.zone.id}/splits`);
    splitFeatures = fc.features;
    L.geoJSON(fc, {
      interactive: false,
      style: (f) => f.properties.split === "test"
        ? { color: "#e0a106", weight: 2.5, dashArray: "6 4", fill: false }
        : { color: "#ffffff", weight: 0.8, opacity: 0.6, fill: false },
    }).addTo(layers.splits);
    toggleSplits();
  } catch (e) {
    console.warn("Sin bloques del dataset:", e.message);
  }
}

function toggleSplits() {
  if ($("show-splits").checked) map.addLayer(layers.splits);
  else map.removeLayer(layers.splits);
}

// ¿En qué bloques del dataset cae el rectángulo? Para avisar si el modelo ya vio esa área.
function splitsFor(bounds) {
  const hit = new Set();
  for (const f of splitFeatures) {
    const ring = f.geometry.coordinates[0];
    const b = L.latLngBounds(ring.map(([x, y]) => [y, x]));
    if (b.intersects(bounds)) hit.add(f.properties.split);
  }
  if (!hit.size) return "fuera de los bloques";
  return [...hit].map((s) => SPLIT_NAMES[s] || s).join(" + ");
}

// ---------- dibujo del rectángulo ----------

let drawing = false, start = null;
const tip = L.tooltip({ permanent: true, direction: "top", className: "area-tip", offset: [0, -6] });

function setDrawing(on) {
  drawing = on;
  $("draw").classList.toggle("drawing", on);
  $("draw").textContent = on ? "Arrastrá sobre el mapa… (Esc cancela)" : "Dibujar área a analizar";
  map.getContainer().classList.toggle("map-drawing", on);
  if (on) map.dragging.disable(); else map.dragging.enable();
}

$("draw").addEventListener("click", () => setDrawing(!drawing));
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && drawing) { setDrawing(false); start = null; } });

map.on("mousedown", (e) => {
  if (!drawing) return;
  start = e.latlng;
  if (layers.rect) map.removeLayer(layers.rect);
  layers.rect = L.rectangle([start, start], { color: "#ffffff", weight: 2, fillOpacity: 0.05, interactive: false }).addTo(map);
});

map.on("mousemove", (e) => {
  if (!drawing || !start) return;
  const b = L.latLngBounds(start, e.latlng);
  layers.rect.setBounds(b);
  const a = areaKm2(b);
  tip.setLatLng(b.getNorthWest().equals(b.getNorthEast()) ? e.latlng : L.latLng(b.getNorth(), b.getCenter().lng))
    .setContent(`${fmt(a, 2)} km²`);
  if (!map.hasLayer(tip)) tip.addTo(map);
  tip.getElement()?.classList.toggle("too-big", a > state.maxArea);
});

map.on("mouseup", async (e) => {
  if (!drawing || !start) return;
  const b = L.latLngBounds(start, e.latlng);
  start = null;
  setDrawing(false);
  map.removeLayer(tip);
  const a = areaKm2(b);
  if (a < 0.01) { map.removeLayer(layers.rect); return; }
  if (a > state.maxArea) {
    layers.rect.setStyle({ color: "#d7301f", dashArray: "4 4" });
    showError(`El área dibujada mide ${fmt(a, 2)} km² y el máximo es ${fmt(state.maxArea, 0)} km². Dibujá un rectángulo más chico o acercá el mapa.`);
    return;
  }
  await analyze(b);
});

// ---------- análisis ----------

function clearResult() {
  layers.result.clearLayers();
  if (layers.rect) { map.removeLayer(layers.rect); layers.rect = null; }
  $("result").hidden = true;
  showError("");
}

async function analyze(bounds) {
  showError("");
  layers.result.clearLayers();
  const bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()];
  const btn = $("draw");
  btn.disabled = true;
  btn.textContent = "Analizando con la U-Net…";
  try {
    const r = await getJSON("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ zone: state.zone.id, bbox, pair: "historical" }),
    });
    L.geoJSON(r.no_observable_geojson, {
      interactive: false, style: { color: "#8a8a8a", weight: 0, fillColor: "#8a8a8a", fillOpacity: 0.7 },
    }).addTo(layers.result);
    L.geoJSON(r.loss_geojson, {
      style: { color: "#d7301f", weight: 1, fillColor: "#d7301f", fillOpacity: 0.55 },
      onEachFeature: (f, l) => l.bindTooltip(`${fmt(f.properties.ha, 2)} ha`),
    }).addTo(layers.result);
    layers.rect.setStyle({ color: "#ffffff", dashArray: null, fillOpacity: 0 });

    $("r-loss").textContent = fmt(r.loss_ha, 1);
    $("r-mb").textContent = r.mapbiomas ? `${fmt(r.mapbiomas.loss_ha, 1)} ha` : "sin etiquetas";
    $("r-agree").textContent = r.mapbiomas?.acuerdo_pct != null ? `${fmt(r.mapbiomas.acuerdo_pct, 1)} %` : "–";
    $("r-area").textContent = `${fmt(r.area_km2, 2)} km²`;
    $("r-valid").textContent = `${fmt(r.valid_pct, 1)} %`;
    $("r-split").textContent = splitsFor(bounds);
    $("r-time").textContent = `${fmt(r.inference_seconds, 2)} s`;
    $("result").hidden = false;
  } catch (e) {
    if (layers.rect) layers.rect.setStyle({ color: "#d7301f", dashArray: "4 4" });
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Dibujar área a analizar";
  }
}

// ---------- controles ----------

document.querySelectorAll(".segmented button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".segmented button").forEach((x) => x.classList.toggle("active", x === b));
  state.role = b.dataset.role;
  loadBackground();
}));
$("show-splits").addEventListener("change", toggleSplits);

loadZones();
