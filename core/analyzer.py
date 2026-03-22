"""
NDVI statistical analysis and visualization.

Encapsulates the analysis workflow from notebook 02.
"""

from __future__ import annotations

import gc
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask

if TYPE_CHECKING:
    from core.config import PipelineConfig

logger = logging.getLogger(__name__)

MONTH_LABELS = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}
SEASON_COLOR = {
    1: "#74add1", 2: "#74add1", 3: "#a6d96a", 4: "#a6d96a",
    5: "#a6d96a", 6: "#fee08b", 7: "#fee08b", 8: "#fee08b",
    9: "#fdae61", 10: "#fdae61", 11: "#fdae61", 12: "#74add1",
}
SEASONS = {
    "Winter": [12, 1, 2],
    "Spring": [3, 4, 5],
    "Summer": [6, 7, 8],
    "Autumn": [9, 10, 11],
}


def _extract_date(filename: Path) -> tuple[datetime | None, str]:
    date_str = filename.stem.replace("NDVI_", "")
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y_%m_%d"):
        try:
            return datetime.strptime(date_str, fmt), date_str
        except ValueError:
            continue
    return None, date_str


def _classify_ndvi(pixels: np.ndarray) -> tuple[float, float, float, float]:
    n = len(pixels)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0
    return (
        float(np.sum(pixels < 0.1) / n * 100),
        float(np.sum((pixels >= 0.1) & (pixels < 0.3)) / n * 100),
        float(np.sum((pixels >= 0.3) & (pixels < 0.5)) / n * 100),
        float(np.sum(pixels >= 0.5) / n * 100),
    )


class NDVIAnalyzer:
    """Statistical analysis and plot generation for NDVI time series."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.df: pd.DataFrame | None = None
        self.pixel_archive: dict[int, list] = {}
        self._geometries: list | None = None
        self._ndvi_files: list[Path] = []

    def _load_data(self) -> None:
        self._ndvi_files = sorted(self.config.processed_path.glob("NDVI_*.tif"))
        if not self._ndvi_files:
            raise FileNotFoundError(
                f"No NDVI files in {self.config.processed_path}"
            )

        pp = self.config.polygon_path
        if pp and Path(pp).exists():
            gdf = gpd.read_file(pp)
            with rasterio.open(self._ndvi_files[0]) as src:
                if gdf.crs != src.crs:
                    gdf = gdf.to_crs(src.crs)
            self._geometries = gdf.geometry.tolist()

    def compute_statistics(self) -> pd.DataFrame:
        """Compute per-date NDVI statistics. Stores result in self.df."""
        self._load_data()
        nodata = self.config.nodata_value
        records: list[dict] = []
        self.pixel_archive = {}

        for ndvi_path in self._ndvi_files:
            dt, date_str = _extract_date(ndvi_path)

            with rasterio.open(ndvi_path) as src:
                if self._geometries:
                    clipped, _ = mask(src, self._geometries, crop=True, nodata=nodata)
                    band = clipped[0]
                else:
                    band = src.read(1)

            valid = band[(band != nodata) & np.isfinite(band)]
            if len(valid) == 0:
                continue

            bare, sparse, moderate, dense = _classify_ndvi(valid)
            rec = {
                "date": date_str,
                "date_dt": dt,
                "month": dt.month if dt else 0,
                "mean": round(float(np.mean(valid)), 4),
                "median": round(float(np.median(valid)), 4),
                "min": round(float(np.min(valid)), 4),
                "max": round(float(np.max(valid)), 4),
                "std": round(float(np.std(valid)), 4),
                "pixel_count": len(valid),
                "bare_pct": round(bare, 1),
                "sparse_pct": round(sparse, 1),
                "moderate_pct": round(moderate, 1),
                "dense_pct": round(dense, 1),
            }
            records.append(rec)

            month = dt.month if dt else 0
            self.pixel_archive.setdefault(month, [])
            sample = valid if len(valid) <= 50000 else np.random.choice(valid, 50000, replace=False)
            self.pixel_archive[month].extend(sample.tolist())

            del band, valid
            gc.collect()

        self.df = pd.DataFrame(records).sort_values("date_dt").reset_index(drop=True)
        return self.df

    def save_csv(self) -> Path:
        """Export statistics to CSV."""
        if self.df is None or self.df.empty:
            raise RuntimeError("Run compute_statistics() first")

        col_map = {
            "date": "Date", "mean": "NDVI Mean", "median": "NDVI Median",
            "min": "NDVI Min", "max": "NDVI Max", "std": "Std Dev",
            "pixel_count": "Pixel Count", "bare_pct": "Bare/Water (%)",
            "sparse_pct": "Sparse Veg (%)", "moderate_pct": "Moderate Veg (%)",
            "dense_pct": "Dense Veg (%)",
        }
        csv_path = self.config.output_path / self.config.statistics_csv
        self.df[list(col_map.keys())].rename(columns=col_map).to_csv(
            csv_path, index=False, encoding="utf-8-sig"
        )
        return csv_path

    # -- Plot generators (return matplotlib Figure) ----------------------------

    def plot_time_series(self) -> plt.Figure:
        df = self._require_df()
        self._apply_rc()
        idx_max = df["mean"].idxmax()
        idx_min = df["mean"].idxmin()
        t = df["date_dt"]

        fig, ax = plt.subplots(figsize=(15, 6))
        ax.fill_between(t, df["min"], df["max"], alpha=0.10, color="green", label="Min - Max")
        ax.fill_between(
            t, df["mean"] - df["std"], df["mean"] + df["std"],
            alpha=0.25, color="green", label="+/- 1 Std Dev",
        )
        ax.plot(t, df["mean"], "o-", color="darkgreen", lw=2.5, ms=6, label="Mean NDVI", zorder=5)
        ax.plot(t, df["median"], "s--", color="darkorange", lw=1.5, ms=4, label="Median NDVI", alpha=0.7)

        ax.annotate(
            f"Max: {df.loc[idx_max, 'mean']:.3f}\n{df.loc[idx_max, 'date']}",
            xy=(df.loc[idx_max, "date_dt"], df.loc[idx_max, "mean"]),
            xytext=(0, 20), textcoords="offset points", fontsize=9,
            ha="center", color="darkgreen", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="darkgreen"),
        )
        ax.annotate(
            f"Min: {df.loc[idx_min, 'mean']:.3f}\n{df.loc[idx_min, 'date']}",
            xy=(df.loc[idx_min, "date_dt"], df.loc[idx_min, "mean"]),
            xytext=(0, -25), textcoords="offset points", fontsize=9,
            ha="center", color="red", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="red"),
        )

        ax.set_xlabel("Date")
        ax.set_ylabel("NDVI")
        ax.set_title(f"NDVI Time Series - {self.config.project_name}", fontsize=14, fontweight="bold")
        ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
        ax.set_ylim(self.config.ndvi_vmin, 1.0)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.xticks(rotation=45)
        plt.tight_layout()
        return fig

    def plot_class_distribution(self) -> plt.Figure:
        df = self._require_df()
        self._apply_rc()

        fig, ax = plt.subplots(figsize=(15, 6))
        ax.stackplot(
            df["date_dt"],
            df["dense_pct"], df["moderate_pct"], df["sparse_pct"], df["bare_pct"],
            labels=[
                "Dense Vegetation (>= 0.5)",
                "Moderate Vegetation (0.3 - 0.5)",
                "Sparse Vegetation (0.1 - 0.3)",
                "Bare Soil / Water (< 0.1)",
            ],
            colors=["#1a9641", "#a6d96a", "#ffffbf", "#d7191c"],
            alpha=0.85,
        )
        ax.set_xlabel("Date")
        ax.set_ylabel("Area Percentage (%)")
        ax.set_title(
            f"NDVI Class Distribution - {self.config.project_name}",
            fontsize=14, fontweight="bold",
        )
        ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
        ax.set_ylim(0, 100)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.xticks(rotation=45)
        plt.tight_layout()
        return fig

    def plot_monthly_boxplot(self) -> plt.Figure:
        self._require_df()
        self._apply_rc()
        months = sorted(m for m in self.pixel_archive if m > 0)
        if not months:
            raise RuntimeError("No monthly pixel data available")

        box_data = [self.pixel_archive[m] for m in months]
        labels = [MONTH_LABELS[m] for m in months]

        fig, ax = plt.subplots(figsize=(14, 6))
        bp = ax.boxplot(box_data, labels=labels, patch_artist=True, showfliers=False, widths=0.6)
        for patch, month in zip(bp["boxes"], months):
            patch.set_facecolor(SEASON_COLOR[month])
            patch.set_alpha(0.7)
        ax.set_xlabel("Month")
        ax.set_ylabel("NDVI")
        ax.set_title(
            f"Monthly NDVI Distribution - {self.config.project_name}",
            fontsize=14, fontweight="bold",
        )
        ax.set_ylim(self.config.ndvi_vmin, 1.0)
        plt.tight_layout()
        return fig

    def plot_seasonal_maps(self) -> plt.Figure:
        self._require_df()
        self._apply_rc()
        nodata = self.config.nodata_value

        fig, axes = plt.subplots(1, 4, figsize=(22, 6))
        im = None

        for ax, (season, months) in zip(axes, SEASONS.items()):
            f = self._nearest_file(months)
            with rasterio.open(f) as src:
                if self._geometries:
                    clipped, _ = mask(src, self._geometries, crop=True, nodata=nodata)
                    data = clipped[0]
                else:
                    data = src.read(1)

            data = np.where((data == nodata) | ~np.isfinite(data), np.nan, data)
            im = ax.imshow(data, cmap="RdYlGn", vmin=self.config.ndvi_vmin, vmax=self.config.ndvi_vmax)
            _, date_str = _extract_date(f)
            ax.set_title(f"{season}\n{date_str}\nMean: {np.nanmean(data):.3f}", fontsize=11)
            ax.axis("off")
            del data
            gc.collect()

        if im is not None:
            fig.colorbar(im, ax=axes, label="NDVI", shrink=0.75, pad=0.02)
        plt.suptitle(
            f"Seasonal NDVI Comparison - {self.config.project_name}",
            fontsize=14, fontweight="bold", y=1.02,
        )
        plt.tight_layout()
        return fig

    def plot_all_dates_grid(self) -> plt.Figure:
        self._require_df()
        self._apply_rc()
        nodata = self.config.nodata_value
        n = len(self._ndvi_files)
        cols = min(6, n)
        rows = (n + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(3.5 * cols, 3.5 * rows))
        if rows == 1 and cols == 1:
            axes = np.array([[axes]])
        elif rows == 1 or cols == 1:
            axes = axes.reshape((rows, cols))

        for idx, ndvi_path in enumerate(self._ndvi_files):
            with rasterio.open(ndvi_path) as src:
                if self._geometries:
                    clipped, _ = mask(src, self._geometries, crop=True, nodata=nodata)
                    data = clipped[0]
                else:
                    data = src.read(1)

            data = np.where((data == nodata) | ~np.isfinite(data), np.nan, data)
            ax = axes.flat[idx]
            ax.imshow(data, cmap="RdYlGn", vmin=self.config.ndvi_vmin, vmax=self.config.ndvi_vmax)
            _, date_str = _extract_date(ndvi_path)
            ax.set_title(f"{date_str}\n({np.nanmean(data):.3f})", fontsize=8)
            ax.axis("off")
            del data

        for idx in range(n, rows * cols):
            axes.flat[idx].axis("off")

        plt.suptitle(
            f"All NDVI Dates - {self.config.project_name}",
            fontsize=16, fontweight="bold", y=1.01,
        )
        plt.tight_layout()
        return fig

    def save_all_plots(self) -> list[Path]:
        """Generate and save all 5 plots. Returns list of saved file paths."""
        prefix = self.config.plot_prefix
        out = self.config.output_path
        saved: list[Path] = []

        plots = [
            (f"01_{prefix}time_series.png", self.plot_time_series),
            (f"02_{prefix}class_distribution.png", self.plot_class_distribution),
            (f"03_{prefix}monthly_boxplot.png", self.plot_monthly_boxplot),
            (f"04_{prefix}seasonal_maps.png", self.plot_seasonal_maps),
            (f"05_{prefix}all_dates_grid.png", self.plot_all_dates_grid),
        ]

        for name, plot_fn in plots:
            try:
                fig = plot_fn()
                path = out / name
                fig.savefig(path, dpi=300, bbox_inches="tight")
                plt.close(fig)
                saved.append(path)
            except Exception as exc:
                logger.error("Failed to generate %s: %s", name, exc)

        return saved

    def run(self) -> dict:
        """
        Full analysis pipeline.
        Returns dict with df, csv_path, and plot_paths.
        """
        df = self.compute_statistics()
        csv_path = self.save_csv()
        plot_paths = self.save_all_plots()
        return {
            "dataframe": df,
            "csv_path": csv_path,
            "plot_paths": plot_paths,
        }

    # -- Internal helpers ------------------------------------------------------

    def _require_df(self) -> pd.DataFrame:
        if self.df is None or self.df.empty:
            raise RuntimeError("Run compute_statistics() first")
        return self.df

    def _apply_rc(self) -> None:
        plt.rcParams.update({
            "figure.dpi": self.config.figure_dpi,
            "font.size": self.config.font_size,
            "axes.grid": self.config.show_grid,
            "grid.alpha": self.config.grid_alpha,
        })

    def _nearest_file(self, target_months: list[int]) -> Path:
        mid = target_months[len(target_months) // 2]
        return min(
            (f for f in self._ndvi_files if _extract_date(f)[0]),
            key=lambda f: min(
                abs(_extract_date(f)[0].month - mid),  # type: ignore[union-attr]
                12 - abs(_extract_date(f)[0].month - mid),  # type: ignore[union-attr]
            ),
        )
