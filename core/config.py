"""
Configuration management for the NDVI analysis pipeline.

Builds a validated config dict from user inputs (UI or YAML),
creates required directories, and loads S3 credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


@dataclass
class PipelineConfig:
    """Immutable pipeline configuration built from user inputs."""

    # Study area (GeoJSON geometry dict)
    aoi: dict
    project_name: str = "NDVI Analysis"
    search_date_range: str = "2023-01-01/2023-12-31"

    # Sentinel-2 search
    target_bands: list[str] = field(default_factory=lambda: ["B04_10m", "B08_10m"])
    cloud_threshold: float = 10.0
    min_days_interval: int = 14
    max_items: int = 100

    # Processing
    block_size: int = 512
    nodata_value: float = -9999.0

    # Directories
    raw_dir: str = "./data/raw"
    processed_dir: str = "./data/processed"
    output_dir: str = "./data/output"
    polygon_path: str | None = None

    # Visualization
    figure_dpi: int = 150
    font_size: int = 11
    ndvi_vmin: float = -0.1
    ndvi_vmax: float = 0.8
    show_grid: bool = True
    grid_alpha: float = 0.3
    statistics_csv: str = "ndvi_statistics.csv"
    plot_prefix: str = "ndvi_"

    # S3 credentials (loaded from env or passed directly)
    s3_access_key: str = ""
    s3_secret_key: str = ""

    def __post_init__(self) -> None:
        self._resolve_dirs()
        self._load_credentials()

    def _resolve_dirs(self) -> None:
        for attr in ("raw_dir", "processed_dir", "output_dir"):
            p = Path(getattr(self, attr))
            p.mkdir(parents=True, exist_ok=True)

    def _load_credentials(self) -> None:
        if not self.s3_access_key or not self.s3_secret_key:
            load_dotenv()
            self.s3_access_key = self.s3_access_key or os.getenv("S3_ACCESS_KEY", "")
            self.s3_secret_key = self.s3_secret_key or os.getenv("S3_SECRET_KEY", "")

    @property
    def raw_path(self) -> Path:
        return Path(self.raw_dir)

    @property
    def processed_path(self) -> Path:
        return Path(self.processed_dir)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    def to_dict(self) -> dict[str, Any]:
        """Export as plain dict (compatible with existing config.yaml structure)."""
        return {
            "aoi": self.aoi,
            "project_name": self.project_name,
            "search_date_range": self.search_date_range,
            "target_bands": self.target_bands,
            "cloud_threshold": self.cloud_threshold,
            "min_days_interval": self.min_days_interval,
            "max_items": self.max_items,
            "block_size": self.block_size,
            "nodata_value": self.nodata_value,
            "raw_dir": self.raw_dir,
            "processed_dir": self.processed_dir,
            "output_dir": self.output_dir,
            "polygon_path": self.polygon_path,
            "figure_dpi": self.figure_dpi,
            "font_size": self.font_size,
            "ndvi_vmin": self.ndvi_vmin,
            "ndvi_vmax": self.ndvi_vmax,
            "show_grid": self.show_grid,
            "grid_alpha": self.grid_alpha,
            "statistics_csv": self.statistics_csv,
            "plot_prefix": self.plot_prefix,
        }

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PipelineConfig":
        """Create config from an existing YAML file."""
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
