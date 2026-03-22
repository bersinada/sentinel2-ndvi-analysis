"""
Sentinel-2 scene search (STAC) and band download (S3).

Encapsulates the search-filter-download workflow from notebook 01.
Handles 180-day temporal window limit for CDSE OpenEO/STAC API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import boto3
from pystac_client import Client

from shapely.geometry import shape

if TYPE_CHECKING:
    from core.config import PipelineConfig

logger = logging.getLogger(__name__)

STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac"
S3_ENDPOINT = "https://eodata.dataspace.copernicus.eu"
S3_BUCKET = "eodata"
COLLECTION = "sentinel-2-l2a"
def split_date_range_into_monthly_chunks(
    start_date: datetime, end_date: datetime
) -> list[tuple[datetime, datetime]]:
    """
    Split a date range into monthly chunks for better search results.
    
    Each chunk covers one full calendar month (1st to last day).
    This approach yields better results than larger temporal windows.
    
    Args:
        start_date: Start of date range (YYYY-MM-DD)
        end_date: End of date range (YYYY-MM-DD)
    
    Returns:
        List of (start, end) tuples for each month.
    
    Example:
        2023-01-15 to 2023-03-20 returns:
        [(2023-01-01, 2023-01-31), (2023-02-01, 2023-02-28), (2023-03-01, 2023-03-31)]
    """
    chunks = []
    current = start_date.replace(day=1)  # Start from first day of month
    
    while current <= end_date:
        # Get first day of next month
        if current.month == 12:
            next_month_first = current.replace(year=current.year + 1, month=1, day=1)
        else:
            next_month_first = current.replace(month=current.month + 1, day=1)
        
        # Last day of current month is day before first day of next month
        month_end = next_month_first - timedelta(days=1)
        
        # Cap the end date to user's specified end date
        actual_end = min(month_end, end_date)
        
        chunks.append((current, actual_end))
        
        # Move to first day of next month
        current = next_month_first
    
    return chunks


class SceneDownloader:
    """Search Copernicus STAC catalog and download Sentinel-2 bands via S3."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self._s3 = None

    @property
    def s3(self) -> boto3.client:
        if self._s3 is None:
            self._s3 = boto3.client(
                "s3",
                endpoint_url=S3_ENDPOINT,
                aws_access_key_id=self.config.s3_access_key,
                aws_secret_access_key=self.config.s3_secret_key,
                region_name="default",
            )
        return self._s3

    def test_connection(self) -> bool:
        try:
            self.s3.list_objects_v2(
                Bucket=S3_BUCKET, Prefix="Sentinel-2/", Delimiter="/", MaxKeys=1
            )
            return True
        except Exception as exc:
            logger.error("S3 connection failed: %s", exc)
            return False

    def search_scenes(self) -> list[dict]:
        """
        Search STAC catalog and return filtered scenes.
        Automatically splits date range into 180-day chunks to respect CDSE API limits.
        
        Returns list of dicts with keys: id, datetime, cloud_cover, assets.
        """
        # Parse date range from config
        date_range_str = self.config.search_date_range
        if "/" not in date_range_str:
            raise ValueError(f"Invalid date range format: {date_range_str}. Expected: YYYY-MM-DD/YYYY-MM-DD")
        
        start_str, end_str = date_range_str.split("/")
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
        
        # Split into monthly chunks (better search results)
        chunks = split_date_range_into_monthly_chunks(start_date, end_date)
        logger.info("Split date range into %d monthly chunks", len(chunks))
        
        catalog = Client.open(STAC_URL)
        clean: list[dict] = []
        last_date = None

        for chunk_idx, (chunk_start, chunk_end) in enumerate(chunks, 1):
            logger.info("Processing chunk %d/%d: %s to %s", chunk_idx, len(chunks), 
                       chunk_start.date(), chunk_end.date())
            
            # Create datetime string for this chunk
            datetime_str = f"{chunk_start.isoformat()}/{chunk_end.isoformat()}"
            
            try:
                search = catalog.search(
                    collections=[COLLECTION],
                    intersects=self.config.aoi,
                    datetime=datetime_str,
                    max_items=self.config.max_items,
                )
                
                for item in sorted(search.items(), key=lambda x: x.datetime):
                    # Filter: only keep items fully contained within AOI
                    item_geom = shape(item.geometry)
                    aoi_geom = shape(self.config.aoi)
                    
                    if not aoi_geom.contains(item_geom):
                        continue
                    
                    cloud_cover = item.properties.get("eo:cloud_cover", 100)
                    current_date = item.datetime

                    if cloud_cover >= self.config.cloud_threshold:
                        continue
                    if last_date and (current_date - last_date) < timedelta(
                        days=self.config.min_days_interval
                    ):
                        continue

                    # Avoid duplicates from overlapping chunks
                    if not any(s["id"] == item.id for s in clean):
                        clean.append(
                            {
                                "id": item.id,
                                "datetime": current_date,
                                "cloud_cover": cloud_cover,
                                "assets": {k: v.href for k, v in item.assets.items()},
                            }
                        )
                        last_date = current_date
            except Exception as exc:
                logger.error("Search failed for chunk %d (%s to %s): %s", 
                           chunk_idx, chunk_start.date(), chunk_end.date(), exc)
                raise

        logger.info("Found %d clean scenes across all chunks", len(clean))
        return clean

    def download_scenes(
        self, scenes: list[dict]
    ) -> Generator[dict, None, None]:
        """
        Download target bands for each scene.
        Yields progress dicts: {scene, band, status, path, error?}
        """
        raw_dir = self.config.raw_path

        for scene in scenes:
            scene_date = scene["datetime"].strftime("%Y-%m-%d")
            scene_dir = raw_dir / scene_date
            scene_dir.mkdir(parents=True, exist_ok=True)

            for band_name in self.config.target_bands:
                dest = scene_dir / f"{scene_date}_{band_name}.jp2"
                progress = {"scene": scene_date, "band": band_name}

                if dest.exists():
                    progress.update(status="skipped", path=str(dest))
                    yield progress
                    continue

                href = scene["assets"].get(band_name, "")
                s3_key = href.replace("s3://eodata/", "")

                try:
                    self.s3.download_file(Bucket=S3_BUCKET, Key=s3_key, Filename=str(dest))
                    progress.update(status="ok", path=str(dest))
                except Exception as exc:
                    progress.update(status="error", path=str(dest), error=str(exc))
                    logger.error("Download failed %s/%s: %s", scene_date, band_name, exc)

                yield progress

    def run(self) -> tuple[list[dict], list[dict]]:
        """
        Full search + download pipeline.
        Returns (scenes, download_results).
        """
        scenes = self.search_scenes()
        results = list(self.download_scenes(scenes))
        return scenes, results
