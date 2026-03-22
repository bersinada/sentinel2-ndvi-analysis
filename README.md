# Sentinel-2 NDVI Analysis

> Fully automated vegetation analysis: download satellite imagery → compute NDVI → generate statistics & plots in **10 minutes** (vs 2 hours manual).

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)

## ⚡ Quick Start

### 1️⃣ Setup (5 min)

```bash
# Clone & install
git clone https://github.com/bersinada/sentinel2-ndvi-analysis.git
cd sentinel2-ndvi-analysis
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
cp .env.example .env
# Edit config.yaml (AOI, dates) and .env (S3 credentials)
```

### 2️⃣ Run (Pick One)

**Option A — Web UI (easiest):**
```bash
streamlit run app.py
# Click buttons in browser: Search → Download → Analyze
```

**Option B — Python:**
```python
from core.config import PipelineConfig
from core.downloader import SceneDownloader
from core.processor import NDVIProcessor
from core.analyzer import NDVIAnalyzer

cfg = PipelineConfig.from_yaml("config.yaml")
downloader = SceneDownloader(cfg)
scenes = downloader.search_scenes()
# ... download, process, analyze
```

**Option C — Notebooks (traditional):**
```
Run 01_download_and_compute.ipynb → 02_analysis_and_visualization.ipynb
```

### 3️⃣ Get Results

✅ **`data/processed/NDVI_*.tif`** — NDVI rasters (one per date)  
✅ **`data/processed/NDVI_*.vrt`** — Multi-band VRT (open in QGIS)  
✅ **`data/output/ndvi_statistics.csv`** — Statistics table  
✅ **`data/output/01-05_*.png`** — 5 plots (time series, seasonal, etc.)

---

## 📋 What It Does

1. **Search** — Queries Copernicus STAC for Sentinel-2 L2A scenes (with cloud filtering)
2. **Download** — Streams Red (B04) + NIR (B08) bands from S3
3. **Compute** — Calculates NDVI = (NIR - Red) / (NIR + Red)
4. **Analyze** — Statistics per date, vegetation classification, seasonal trends
5. **Visualize** — Time series plots, seasonal maps, monthly distributions

---

## 🔧 Configuration

Edit `config.yaml`:

```yaml
aoi:
  type: "Polygon"
  coordinates:
    - [[lon1, lat1], [lon2, lat2], [lon3, lat3], [lon1, lat1]]
    # Tip: Draw on geojson.io, copy coordinates

search_date_range: "2024-01-01/2024-12-31"
cloud_threshold: 10.0          # Max cloud cover %
min_days_interval: 14          # Min days between scenes
polygon_path: null             # Optional: clip polygon (GeoJSON/Shapefile)
```

Edit `.env`:

```
S3_ACCESS_KEY=your_key
S3_SECRET_KEY=your_secret
```

**Get S3 credentials:** [Copernicus DataSpace](https://dataspace.copernicus.eu/) → User Settings → S3 Access → Generate

---

## 📂 Outputs

```
data/
├── raw/          NDVI_YYYY-MM-DD_B04.jp2, B08.jp2 (auto-created)
├── processed/    NDVI_*.tif, *.vrt (QGIS ready)
└── output/       ndvi_statistics.csv + 5 plots
```

**Files:**
- `NDVI_*.tif` — Individual NDVI rasters (float32, LZW-compressed)
- `NDVI_*.vrt` — Multi-band stack (open in QGIS, no disk overhead)
- `ndvi_statistics.csv` — Per-date stats (mean, median, std, vegetation classes)
- `01_ndvi_time_series.png` — Time series with confidence bands
- `02_ndvi_class_distribution.png` — Vegetation coverage over time
- `03_ndvi_monthly_boxplot.png` — Monthly distributions
- `04_ndvi_seasonal_maps.png` — Seasonal comparison maps
- `05_ndvi_all_dates_grid.png` — Grid of all dates

---

## 🛠️ For Developers

**Project structure:**
```
core/
  ├── config.py       — Configuration management
  ├── downloader.py   — STAC search + S3 download (monthly chunking)
  ├── processor.py    — NDVI computation + VRT build
  └── analyzer.py     — Statistics + visualization
app.py               — Streamlit web UI
01_download_and_compute.ipynb  — Traditional notebook (Step 1)
02_analysis_and_visualization.ipynb — Traditional notebook (Step 2)
```

**Key features:**
- ✅ Monthly temporal chunking (overcomes 180-day API limit)
- ✅ AOI geometry containment filtering (only tiles fully within AOI)
- ✅ Memory-efficient windowed NDVI computation
- ✅ Auto VRT generation (QGIS time-series ready)
- ✅ 5 publication-ready plots

---

## ⚠️ Requirements

- Python 3.9+
- GDAL: `conda install -c conda-forge gdal` (or `pip install gdal`)
- Free [Copernicus DataSpace](https://dataspace.copernicus.eu/) account

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

**Data:** Sentinel-2 L2A via [Copernicus Data Space](https://dataspace.copernicus.eu/) (ESA)
