"""
NDVI computation and VRT generation.

Encapsulates the processing workflow from notebook 01 (cells 4-7).
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import numpy as np
import rasterio
from rasterio.windows import Window

if TYPE_CHECKING:
    from core.config import PipelineConfig

logger = logging.getLogger(__name__)


class NDVIProcessor:
    """Compute NDVI rasters from downloaded Sentinel-2 bands."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def compute_ndvi(
        self, red_path: str | Path, nir_path: str | Path, output_path: str | Path
    ) -> Path:
        """
        Compute NDVI from B04 (Red) and B08 (NIR) using windowed reads.
        Returns the output path.
        """
        red_path = Path(red_path)
        nir_path = Path(nir_path)
        output_path = Path(output_path)
        block = self.config.block_size
        nodata = self.config.nodata_value

        with rasterio.open(red_path) as red_ds, rasterio.open(nir_path) as nir_ds:
            if red_ds.shape != nir_ds.shape:
                raise ValueError(
                    f"Shape mismatch: B04={red_ds.shape}, B08={nir_ds.shape}"
                )

            meta = red_ds.meta.copy()
            meta.update(driver="GTiff", dtype="float32", count=1, compress="lzw", nodata=nodata)

            with rasterio.open(output_path, "w", **meta) as dst:
                for row in range(0, red_ds.height, block):
                    win = Window(0, row, red_ds.width, min(block, red_ds.height - row))
                    red = red_ds.read(1, window=win).astype("float32")
                    nir = nir_ds.read(1, window=win).astype("float32")

                    denom = nir + red
                    ndvi = np.where(denom > 0, (nir - red) / denom, nodata)

                    valid = ndvi != nodata
                    ndvi[valid] = np.clip(ndvi[valid], -1.0, 1.0)

                    dst.write(ndvi.astype("float32"), 1, window=win)
                    del red, nir, denom, ndvi

        gc.collect()
        return output_path

    def process_all(self) -> Generator[dict, None, None]:
        """
        Batch NDVI generation for all downloaded date directories.
        Yields progress dicts: {date, status, path?, size_mb?, error?}
        """
        raw_dir = self.config.raw_path
        processed_dir = self.config.processed_path
        date_dirs = sorted(d for d in raw_dir.iterdir() if d.is_dir())

        for date_dir in date_dirs:
            date_str = date_dir.name
            red_files = list(date_dir.glob("*B04*"))
            nir_files = list(date_dir.glob("*B08*"))

            if not red_files or not nir_files:
                yield {"date": date_str, "status": "skipped", "error": "Missing B04 or B08"}
                continue

            output_path = processed_dir / f"NDVI_{date_str}.tif"
            try:
                self.compute_ndvi(red_files[0], nir_files[0], output_path)
                size_mb = output_path.stat().st_size / (1024 ** 2)
                yield {"date": date_str, "status": "ok", "path": str(output_path), "size_mb": size_mb}
            except Exception as exc:
                yield {"date": date_str, "status": "error", "error": str(exc)}
                logger.error("NDVI compute failed for %s: %s", date_str, exc)

            gc.collect()

    def build_vrt(self) -> Path | None:
        """
        Build a multi-band VRT from all NDVI GeoTIFFs.
        Returns VRT path or None on failure.
        """
        try:
            from osgeo import gdal
        except ImportError:
            logger.warning("GDAL not available — VRT generation skipped")
            return None

        processed = self.config.processed_path
        ndvi_paths = sorted(processed.glob("NDVI_*.tif"))

        if not ndvi_paths:
            logger.warning("No NDVI files found for VRT")
            return None

        dates = [f.stem.replace("NDVI_", "") for f in ndvi_paths]
        vrt_name = f"NDVI_{dates[0]}_to_{dates[-1]}.vrt"
        vrt_path = processed / vrt_name

        vrt = gdal.BuildVRT(str(vrt_path), [str(f) for f in ndvi_paths], separate=True)
        if vrt is None:
            return None

        for i, d in enumerate(dates):
            vrt.GetRasterBand(i + 1).SetDescription(d)

        vrt.FlushCache()
        vrt = None
        return vrt_path

    def get_summary(self) -> dict | None:
        """Return a quick summary of the first NDVI file (CRS, resolution, bounds, stats)."""
        ndvi_files = sorted(self.config.processed_path.glob("NDVI_*.tif"))
        if not ndvi_files:
            return None

        with rasterio.open(ndvi_files[0]) as src:
            data = src.read(1)
            valid = data[data != self.config.nodata_value]
            return {
                "crs": str(src.crs),
                "resolution": src.res,
                "shape": (src.height, src.width),
                "bounds": dict(zip(("left", "bottom", "right", "top"), src.bounds)),
                "file_count": len(ndvi_files),
                "ndvi_min": float(valid.min()) if len(valid) else None,
                "ndvi_max": float(valid.max()) if len(valid) else None,
                "ndvi_mean": float(valid.mean()) if len(valid) else None,
                "dates": [f.stem.replace("NDVI_", "") for f in ndvi_files],
            }

    def run(self) -> list[dict]:
        """Full processing pipeline: compute all NDVI + build VRT."""
        results = list(self.process_all())
        self.build_vrt()
        return results
