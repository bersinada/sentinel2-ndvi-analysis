"""
Sentinel-2 NDVI Analysis — Web Interface

Launch:  streamlit run app.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from core.config import PipelineConfig
from core.downloader import SceneDownloader
from core.processor import NDVIProcessor
from core.analyzer import NDVIAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Sentinel-2 NDVI Analysis",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1a5632 0%, #2e7d32 50%, #43a047 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #666;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    .step-badge {
        background: #e8f5e9;
        border-left: 4px solid #2e7d32;
        padding: 0.5rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ───────────────────────────────────────────────────────────────────

st.markdown('<p class="main-header">Sentinel-2 NDVI Analysis</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Uydu görüntüsü indirme, NDVI hesaplama ve analiz otomasyonu</p>',
    unsafe_allow_html=True,
)

# ── Sidebar — Parameters ────────────────────────────────────────────────────

with st.sidebar:
    st.header("Proje Ayarları")

    project_name = st.text_input("Proje Adı", value="My Study Area")

    st.subheader("Çalışma Alanı (AOI)")
    st.caption("GeoJSON Polygon koordinatları (WGS84). [geojson.io](https://geojson.io) ile çizebilirsiniz.")

    aoi_method = st.radio("AOI Giriş Yöntemi", ["Koordinat Gir", "GeoJSON Yapıştır"], horizontal=True)

    if aoi_method == "Koordinat Gir":
        col1, col2 = st.columns(2)
        with col1:
            lon_min = st.number_input("Min Boylam", value=38.60, format="%.4f", step=0.01)
            lat_min = st.number_input("Min Enlem", value=37.36, format="%.4f", step=0.01)
        with col2:
            lon_max = st.number_input("Max Boylam", value=38.66, format="%.4f", step=0.01)
            lat_max = st.number_input("Max Enlem", value=37.41, format="%.4f", step=0.01)

        aoi = {
            "type": "Polygon",
            "coordinates": [[
                [lon_min, lat_min],
                [lon_max, lat_min],
                [lon_max, lat_max],
                [lon_min, lat_max],
                [lon_min, lat_min],
            ]],
        }
    else:
        geojson_text = st.text_area(
            "GeoJSON",
            height=200,
            placeholder='{"type": "Polygon", "coordinates": [[[38.60, 37.36], ...]]}',
        )
        aoi = None
        if geojson_text.strip():
            try:
                parsed = json.loads(geojson_text)
                if parsed.get("type") == "FeatureCollection":
                    aoi = parsed["features"][0]["geometry"]
                elif parsed.get("type") == "Feature":
                    aoi = parsed["geometry"]
                else:
                    aoi = parsed
            except (json.JSONDecodeError, KeyError, IndexError):
                st.error("Geçersiz GeoJSON formatı")

    st.divider()
    st.subheader("Tarih Aralığı")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        from datetime import date

        start_date = st.date_input("Başlangıç", value=date(2023, 1, 1))
    with col_d2:
        end_date = st.date_input("Bitiş", value=date(2023, 12, 31))
    date_range = f"{start_date.isoformat()}/{end_date.isoformat()}"

    st.divider()
    st.subheader("Sentinel-2 Parametreleri")
    cloud_threshold = st.slider("Maks. Bulut Oranı (%)", 0, 100, 10)
    min_days = st.slider("Sahneler Arası Min. Gün", 1, 60, 14)
    max_items = st.number_input("Maks. Sahne Sayısı", 10, 500, 100, step=10)

    st.divider()
    st.subheader("S3 Kimlik Bilgileri")
    st.caption("Copernicus Data Space S3 erişim bilgileri")
    s3_access = st.text_input("S3 Access Key", type="password")
    s3_secret = st.text_input("S3 Secret Key", type="password")
    st.caption("Boş bırakırsanız .env dosyasından okunur.")

    st.divider()
    with st.expander("Gelişmiş Ayarlar"):
        block_size = st.select_slider("Block Size (px)", [128, 256, 512, 1024, 2048], value=512)
        ndvi_vmin = st.number_input("NDVI Min (renk skalası)", value=-0.1, step=0.05)
        ndvi_vmax = st.number_input("NDVI Max (renk skalası)", value=0.8, step=0.05)
        figure_dpi = st.select_slider("Grafik DPI", [72, 100, 150, 200, 300], value=150)

# ── Build config ─────────────────────────────────────────────────────────────


def _build_config() -> PipelineConfig | None:
    if aoi is None:
        st.error("Lütfen geçerli bir AOI (çalışma alanı) girin.")
        return None
    return PipelineConfig(
        aoi=aoi,
        project_name=project_name,
        search_date_range=date_range,
        cloud_threshold=cloud_threshold,
        min_days_interval=min_days,
        max_items=max_items,
        block_size=block_size,
        nodata_value=-9999.0,
        s3_access_key=s3_access,
        s3_secret_key=s3_secret,
        ndvi_vmin=ndvi_vmin,
        ndvi_vmax=ndvi_vmax,
        figure_dpi=figure_dpi,
    )


# ── Main Content — Tabs ─────────────────────────────────────────────────────

tab_run, tab_results, tab_help = st.tabs(["Pipeline Çalıştır", "Sonuçlar", "Yardım"])

# ── TAB 1: Pipeline Execution ────────────────────────────────────────────────

with tab_run:
    st.markdown(
        '<div class="step-badge"><strong>Adım 1 → 2 → 3:</strong> '
        "Sahne Arama → İndirme & NDVI Hesaplama → Analiz & Görselleştirme</div>",
        unsafe_allow_html=True,
    )

    col_run1, col_run2, col_run3 = st.columns(3)

    # ── Step 1: Search ───────────────────────────────────────────────────────

    with col_run1:
        st.markdown("### 1. Sahne Arama")
        if st.button("Sahneleri Ara", use_container_width=True, type="primary"):
            cfg = _build_config()
            if cfg:
                with st.spinner("STAC kataloğu sorgulanıyor..."):
                    try:
                        dl = SceneDownloader(cfg)
                        scenes = dl.search_scenes()
                        st.session_state["scenes"] = scenes
                        st.session_state["config"] = cfg
                        st.success(f"{len(scenes)} sahne bulundu")
                    except Exception as exc:
                        st.error(f"Arama hatası: {exc}")

        if "scenes" in st.session_state and st.session_state["scenes"]:
            scenes = st.session_state["scenes"]
            st.dataframe(
                [
                    {
                        "Tarih": s["datetime"].strftime("%Y-%m-%d"),
                        "Bulut %": f"{s['cloud_cover']:.1f}",
                        "Sahne ID": s["id"][:40],
                    }
                    for s in scenes
                ],
                use_container_width=True,
                hide_index=True,
            )

    # ── Step 2: Download & Compute ───────────────────────────────────────────

    with col_run2:
        st.markdown("### 2. İndir & NDVI Hesapla")

        scenes_ready = "scenes" in st.session_state and st.session_state["scenes"]
        if st.button(
            "İndir & Hesapla",
            use_container_width=True,
            type="primary",
            disabled=not scenes_ready,
        ):
            cfg = st.session_state.get("config")
            scenes = st.session_state["scenes"]

            progress_bar = st.progress(0, text="Başlatılıyor...")
            status_area = st.empty()
            total_bands = len(scenes) * len(cfg.target_bands)

            dl = SceneDownloader(cfg)
            with st.spinner("S3 bağlantısı test ediliyor..."):
                if not dl.test_connection():
                    st.error("S3 bağlantısı başarısız. Kimlik bilgilerini kontrol edin.")
                    st.stop()

            # Download
            download_results = []
            for i, prog in enumerate(dl.download_scenes(scenes)):
                download_results.append(prog)
                pct = (i + 1) / total_bands
                label = f"İndiriliyor: {prog['scene']} / {prog['band']} ({prog['status']})"
                progress_bar.progress(pct, text=label)

            ok_count = sum(1 for r in download_results if r["status"] == "ok")
            skip_count = sum(1 for r in download_results if r["status"] == "skipped")
            err_count = sum(1 for r in download_results if r["status"] == "error")
            status_area.info(f"İndirme tamamlandı — Yeni: {ok_count} | Mevcut: {skip_count} | Hata: {err_count}")

            # NDVI Compute
            proc = NDVIProcessor(cfg)
            ndvi_results = []
            progress_bar2 = st.progress(0, text="NDVI hesaplanıyor...")
            date_dirs = sorted(d for d in cfg.raw_path.iterdir() if d.is_dir())
            total_dates = len(date_dirs) or 1

            for i, res in enumerate(proc.process_all()):
                ndvi_results.append(res)
                pct = (i + 1) / total_dates
                progress_bar2.progress(pct, text=f"NDVI: {res['date']} ({res['status']})")

            proc.build_vrt()
            st.session_state["ndvi_done"] = True
            st.success(f"NDVI hesaplama tamamlandı — {sum(1 for r in ndvi_results if r['status'] == 'ok')} dosya üretildi")

    # ── Step 3: Analysis & Visualization ─────────────────────────────────────

    with col_run3:
        st.markdown("### 3. Analiz & Görselleştirme")

        ndvi_done = st.session_state.get("ndvi_done", False)
        if st.button(
            "Analiz Et",
            use_container_width=True,
            type="primary",
            disabled=not ndvi_done,
        ):
            cfg = st.session_state["config"]
            with st.spinner("İstatistikler hesaplanıyor..."):
                analyzer = NDVIAnalyzer(cfg)
                result = analyzer.run()
                st.session_state["analysis"] = result
                st.session_state["analyzer"] = analyzer
                st.success(
                    f"Tamamlandı — {len(result['dataframe'])} tarih, "
                    f"{len(result['plot_paths'])} grafik üretildi"
                )

    # ── Run All ──────────────────────────────────────────────────────────────

    st.divider()
    if st.button("Tüm Pipeline'ı Çalıştır (Tek Tık)", use_container_width=True, type="secondary"):
        cfg = _build_config()
        if cfg:
            overall = st.progress(0, text="Pipeline başlatılıyor...")
            log_area = st.empty()

            # Step 1
            overall.progress(0.05, text="Adım 1/3 — Sahneler aranıyor...")
            try:
                dl = SceneDownloader(cfg)
                scenes = dl.search_scenes()
                st.session_state["scenes"] = scenes
                st.session_state["config"] = cfg
                log_area.info(f"Adım 1 tamamlandı: {len(scenes)} sahne bulundu")
            except Exception as exc:
                st.error(f"Sahne arama hatası: {exc}")
                st.stop()

            if not scenes:
                st.warning("Kriterlere uygun sahne bulunamadı. Parametreleri değiştirin.")
                st.stop()

            # Step 2
            overall.progress(0.15, text="Adım 2/3 — İndirme & NDVI...")
            if not dl.test_connection():
                st.error("S3 bağlantısı başarısız.")
                st.stop()

            total_bands = len(scenes) * len(cfg.target_bands)
            dl_bar = st.progress(0, text="İndiriliyor...")
            for i, prog in enumerate(dl.download_scenes(scenes)):
                dl_bar.progress((i + 1) / total_bands, text=f"{prog['scene']} / {prog['band']}")

            proc = NDVIProcessor(cfg)
            date_dirs = sorted(d for d in cfg.raw_path.iterdir() if d.is_dir())
            total_dates = len(date_dirs) or 1
            ndvi_bar = st.progress(0, text="NDVI hesaplanıyor...")
            ndvi_ok = 0
            for i, res in enumerate(proc.process_all()):
                ndvi_bar.progress((i + 1) / total_dates, text=f"NDVI: {res['date']}")
                if res["status"] == "ok":
                    ndvi_ok += 1
            proc.build_vrt()
            st.session_state["ndvi_done"] = True
            log_area.info(f"Adım 2 tamamlandı: {ndvi_ok} NDVI dosyası üretildi")

            # Step 3
            overall.progress(0.70, text="Adım 3/3 — Analiz & Görselleştirme...")
            analyzer = NDVIAnalyzer(cfg)
            result = analyzer.run()
            st.session_state["analysis"] = result
            st.session_state["analyzer"] = analyzer

            overall.progress(1.0, text="Pipeline tamamlandı!")
            st.balloons()
            st.success(
                f"Tüm pipeline başarıyla tamamlandı! "
                f"{len(scenes)} sahne → {ndvi_ok} NDVI → "
                f"{len(result['plot_paths'])} grafik"
            )

# ── TAB 2: Results ───────────────────────────────────────────────────────────

with tab_results:
    analysis = st.session_state.get("analysis")

    if analysis is None:
        st.info("Henüz bir analiz çalıştırılmadı. 'Pipeline Çalıştır' sekmesinden başlayın.")
    else:
        df = analysis["dataframe"]

        # Metrics row
        st.markdown("### Özet İstatistikler")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Tarih Sayısı", len(df))
        m2.metric("Ort. NDVI", f"{df['mean'].mean():.3f}")
        m3.metric("Maks. NDVI", f"{df['mean'].max():.3f}")
        m4.metric("Min. NDVI", f"{df['mean'].min():.3f}")
        m5.metric("Ort. Piksel", f"{df['pixel_count'].mean():,.0f}")

        st.divider()

        # Data table
        st.markdown("### İstatistik Tablosu")
        display_cols = ["date", "mean", "median", "min", "max", "std", "pixel_count",
                        "bare_pct", "sparse_pct", "moderate_pct", "dense_pct"]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        csv_path = analysis["csv_path"]
        if csv_path and Path(csv_path).exists():
            with open(csv_path, "rb") as f:
                st.download_button("CSV İndir", f.read(), file_name=Path(csv_path).name, mime="text/csv")

        st.divider()

        # Plots
        st.markdown("### Grafikler")
        analyzer_obj = st.session_state.get("analyzer")
        if analyzer_obj:
            plot_names = [
                ("Zaman Serisi", analyzer_obj.plot_time_series),
                ("Sınıf Dağılımı", analyzer_obj.plot_class_distribution),
                ("Aylık Boxplot", analyzer_obj.plot_monthly_boxplot),
                ("Mevsimsel Haritalar", analyzer_obj.plot_seasonal_maps),
                ("Tüm Tarihler Grid", analyzer_obj.plot_all_dates_grid),
            ]
            for name, plot_fn in plot_names:
                with st.expander(name, expanded=(name == "Zaman Serisi")):
                    try:
                        fig = plot_fn()
                        st.pyplot(fig)
                        import matplotlib.pyplot as plt
                        plt.close(fig)
                    except Exception as exc:
                        st.error(f"{name} grafiği oluşturulamadı: {exc}")

# ── TAB 3: Help ──────────────────────────────────────────────────────────────

with tab_help:
    st.markdown("""
### Nasıl Kullanılır?

1. **Sol panelden** proje parametrelerini girin:
   - Çalışma alanı (bbox koordinatları veya GeoJSON)
   - Tarih aralığı
   - Bulut eşiği ve sahne filtreleri
   - S3 kimlik bilgileri

2. **"Pipeline Çalıştır"** sekmesinden:
   - Adım adım çalıştırabilir veya **"Tüm Pipeline'ı Çalıştır"** ile tek tıkla hepsini yapabilirsiniz

3. **"Sonuçlar"** sekmesinden:
   - İstatistikleri ve grafikleri görüntüleyin
   - CSV indirebilirsiniz

---

### S3 Kimlik Bilgileri

1. [dataspace.copernicus.eu](https://dataspace.copernicus.eu/) adresinde hesap oluşturun
2. **User Settings → S3 Access → Generate Credentials**
3. Access Key ve Secret Key'i sol panele girin veya `.env` dosyasına yazın

---

### Veri Kaynağı

- **Copernicus Data Space** (ESA) üzerinden Sentinel-2 L2A verileri
- STAC kataloğu ile sahne arama
- S3 üzerinden bant indirme (B04 - Red, B08 - NIR)

---

### Çıktılar

| Dosya | Açıklama |
|-------|----------|
| `NDVI_YYYY-MM-DD.tif` | Tarih bazlı NDVI GeoTIFF |
| `NDVI_*.vrt` | Çok bantlı VRT (QGIS için) |
| `ndvi_statistics.csv` | İstatistik tablosu |
| `01-05_*.png` | Zaman serisi, sınıf dağılımı, boxplot, mevsimsel haritalar, grid |
""")

    st.info(
        "Bu proje şu an NDVI analizi için yapılandırılmıştır. "
        "İleride EVI, SAVI, NDWI gibi diğer indeksler de eklenecektir."
    )
