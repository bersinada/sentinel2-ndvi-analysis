"""
Sentinel-2 NDVI Analysis - Core Pipeline Module

Provides automated satellite image download, NDVI computation,
statistical analysis and visualization through a unified API.
"""


def __getattr__(name: str):
    """Lazy imports to avoid hard failures when optional deps are missing."""
    _map = {
        "PipelineConfig": "core.config",
        "SceneDownloader": "core.downloader",
        "NDVIProcessor": "core.processor",
        "NDVIAnalyzer": "core.analyzer",
    }
    if name in _map:
        import importlib

        module = importlib.import_module(_map[name])
        return getattr(module, name)
    raise AttributeError(f"module 'core' has no attribute {name!r}")


__all__ = ["PipelineConfig", "SceneDownloader", "NDVIProcessor", "NDVIAnalyzer"]
