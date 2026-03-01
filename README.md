# Sentinel-2 NDVI Analysis Automation

Automated NDVI (Normalized Difference Vegetation Index) analysis pipeline using Sentinel-2 satellite imagery from Copernicus Data Space.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Sentinel-2](https://img.shields.io/badge/Satellite-Sentinel--2-orange.svg)

## Features

- **Automated Data Download**: Search and download Sentinel-2 L2A imagery from Copernicus Data Space via S3
- **Cloud Filtering**: Automatically filter scenes based on cloud cover percentage and minimum date interval
- **NDVI Computation**: Calculate NDVI from Red (B04) and NIR (B08) bands using memory-efficient windowed reads
- **Automatic VRT Build**: Stack all NDVI rasters into a single multi-band VRT for QGIS time series visualization
- **Time Series Analysis**: Statistics and visualizations across all acquired dates
- **Multiple Outputs**:
  - NDVI GeoTIFF rasters per date
  - Multi-band VRT file for QGIS time series visualization
  - Optional RGB composite GeoTIFFs (3 NDVI dates mapped to R/G/B)
  - CSV statistics with vegetation class percentages
  - Time series, seasonal, monthly, and grid plots
- **Configurable**: All parameters controlled via a single `config.yaml` file

## Project Structure

```
sentinel2-ndvi-analysis/
├── config.yaml                    # Your project configuration (create from example)
├── config.example.yaml            # Configuration template
├── .env                           # S3 credentials (never commit this)
├── .env.example                   # Credentials template
├── 01_download_and_compute.ipynb  # Step 1: Download, compute NDVI, build VRT
├── 02_analysis_and_visualization.ipynb # Step 2: Analysis and visualization
├── build_vrt.py                   # VRT builder (auto-called by notebook, also standalone)
├── requirements.txt               # Python dependencies
├── LICENSE
└── data/
    ├── study_area.geojson        # Your study polygon (optional, place here)
    ├── raw/                      # Downloaded Sentinel-2 bands (auto-created)
    ├── processed/                # NDVI GeoTIFFs + VRT (auto-created)
    └── output/                   # Plots and CSV reports (auto-created)
```

## How It Works

```
config.yaml + .env
       │
       ▼
01_download_and_compute.ipynb
  ├── Search & filter Sentinel-2 scenes (STAC catalog)
  ├── Download B04 (Red) + B08 (NIR) bands via S3
  ├── Compute NDVI GeoTIFF for each date
  ├── Build multi-band VRT  ──▶  build_vrt.py
  └── (Optional) Create RGB composite .tif files
       │
       ▼
02_analysis_and_visualization.ipynb
  ├── Load NDVI files, clip to study polygon
  ├── Compute statistics per date
  ├── Export CSV report
  └── Generate 5 plots
```

## Quick Start

### 1. Prerequisites

- Python 3.9 or higher
- GDAL installed (required for `build_vrt.py`)
  - Recommended: `conda install -c conda-forge gdal`
  - Or see the [GDAL installation guide](https://gdal.org/download.html)
- Free Copernicus Data Space account: https://dataspace.copernicus.eu/

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/sentinel2-ndvi-analysis.git
cd sentinel2-ndvi-analysis
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / Mac
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** If GDAL fails to install via pip, use conda: `conda install -c conda-forge gdal`

### 5. Configure Your Project

1. **Copy the configuration file:**
   ```bash
   cp config.example.yaml config.yaml
   ```

2. **Edit `config.yaml`** with your study area and preferences:
   - `aoi` — your study area polygon coordinates (use [geojson.io](https://geojson.io) to draw)
   - `search_date_range` — e.g. `"2023-01-01/2023-12-31"`
   - `project_name` — shown in plot titles
   - `cloud_threshold` — maximum cloud cover % to accept
   - Directory paths under `raw_dir`, `processed_dir`, `output_dir`
   - `polygon_path` — path to a GeoJSON/Shapefile to clip statistics (optional)

3. **Set up S3 credentials:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your Copernicus S3 credentials:
   ```
   S3_ACCESS_KEY=your_access_key
   S3_SECRET_KEY=your_secret_key
   ```
   To get credentials: Log in to [Copernicus Data Space](https://dataspace.copernicus.eu/) → User Settings → S3 Access → Generate credentials.

### 6. Define Your Study Area

You can define your AOI in `config.yaml` using GeoJSON coordinates:

```yaml
aoi:
  type: "Polygon"
  coordinates:
    - - [longitude1, latitude1]
      - [longitude2, latitude2]
      - [longitude3, latitude3]
      - [longitude4, latitude4]
      - [longitude1, latitude1]  # Close the polygon
```

**Tip:** Use [geojson.io](https://geojson.io) to draw your polygon and paste the coordinates here.

Optionally, place a GeoJSON or Shapefile at the path defined by `polygon_path` in `config.yaml` to clip the statistical analysis to a specific sub-area.

### 7. Run the Pipeline

**Step 1 — Download data, compute NDVI, and build VRT:**

Open `01_download_and_compute.ipynb` in Jupyter and run all cells in order.

| Cell | What it does |
|------|-------------|
| 1 | Load libraries and configuration |
| 2 | Search and filter Sentinel-2 scenes via STAC |
| 3 | Test S3 connection |
| 4 | Download B04 + B08 bands |
| 5 | Define NDVI computation function |
| 6 | Batch compute NDVI GeoTIFFs |
| 7 | **Build multi-band VRT automatically** |
| 8 | *(Optional)* Create RGB composite .tif files — skip if not needed |
| 9 | Print data summary |

**Step 2 — Analyze and visualize:**

Open `02_analysis_and_visualization.ipynb` in Jupyter and run all cells.

**Step 3 — Rebuild VRT only (if needed):**

If you add new NDVI files or want to regenerate the VRT without re-running the full notebook:
```bash
python build_vrt.py
```

## Outputs

### NDVI GeoTIFFs
One `NDVI_YYYY-MM-DD.tif` file per scene in `data/processed/`. Float32, LZW-compressed, nodata = -9999.

### Multi-band VRT
`NDVI_<start>_to_<end>.vrt` in `data/processed/`. Each band corresponds to one date. Open in QGIS → Layer Properties → Symbology → Multiband Color to assign any three dates to R/G/B for change visualization. No additional disk space used.

### RGB Composite GeoTIFFs *(optional)*
`RGB_NDVI_NN_<start>_to_<end>.tif` in `data/processed/`. Three consecutive NDVI dates mapped to R/G/B channels into a single physical file. Useful for printing or sharing. Files can be several hundred MB each depending on area size. Run Cell 8 in `01_download_and_compute.ipynb` to generate these.

### CSV Statistics
`ndvi_statistics.csv` in `data/output/`. Per-date mean, median, min, max, std, pixel count, and vegetation class percentages (dense / moderate / sparse / bare).

### Plots

| File | Description |
|------|-------------|
| `01_ndvi_time_series.png` | Mean NDVI over time with std band and min/max range |
| `02_ndvi_class_distribution.png` | Stacked vegetation class percentages over time |
| `03_ndvi_monthly_boxplot.png` | Monthly NDVI distribution with seasonal colors |
| `04_ndvi_seasonal_maps.png` | One representative NDVI map per season |
| `05_ndvi_all_dates_grid.png` | Grid of all acquired NDVI dates |

## Configuration Reference

| Parameter | Description | Default |
|-----------|-------------|---------|
| `project_name` | Label shown in plot titles | `"My Study Area"` |
| `search_date_range` | Date range for scene search | `"2023-01-01/2023-12-31"` |
| `cloud_threshold` | Max accepted cloud cover (%) | `10.0` |
| `min_days_interval` | Min days between selected scenes | `14` |
| `max_items` | Max scenes to retrieve from STAC | `100` |
| `block_size` | Windowed read block size (pixels) | `512` |
| `nodata_value` | NoData fill value in output rasters | `-9999.0` |
| `polygon_path` | Clip polygon path for statistics (optional) | `null` |
| `figure_dpi` | Plot resolution | `150` |
| `ndvi_vmin` / `ndvi_vmax` | NDVI color scale range | `-0.1` / `0.8` |
| `statistics_csv` | Output CSV filename | `"ndvi_statistics.csv"` |

See `config.example.yaml` for the full list with comments.

## Getting Copernicus S3 Credentials

1. Register at [Copernicus Data Space](https://dataspace.copernicus.eu/)
2. Log in and go to **User Settings**
3. Navigate to **S3 Access** section
4. Click **Generate S3 Credentials**
5. Copy the Access Key and Secret Key to your `.env` file

## Dependencies

| Package | Purpose |
|---------|---------|
| `rasterio` | Raster I/O and polygon masking |
| `geopandas` | Vector data handling (polygon clipping) |
| `numpy` | Array operations |
| `pandas` | Statistics tables |
| `matplotlib` | Plotting |
| `boto3` | S3 download from Copernicus |
| `pystac-client` | STAC catalog scene search |
| `python-dotenv` | Load `.env` credentials |
| `pyyaml` | Parse `config.yaml` |
| `gdal` | Build multi-band VRT file |

## Contributing

Contributions are welcome. Please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Copernicus Data Space](https://dataspace.copernicus.eu/) for free Sentinel-2 data access
- [European Space Agency (ESA)](https://www.esa.int/) for the Sentinel-2 mission
