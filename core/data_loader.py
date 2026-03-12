"""Generic data loader with lazy loading, caching, and multiple source support."""

from __future__ import annotations

import csv
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

DataDict = Dict[str, Any]
DataSource = Union[str, Path, dict]


@dataclass
class LoaderConfig:
    """Configuration for data loader behavior."""
    cache_enabled: bool = True
    cache_dir: Path = field(default_factory=lambda: Path.cwd() / ".cache" / "data_loader")
    cache_ttl_seconds: int = 3600
    lazy_loading: bool = True
    chunk_size: int = 1000
    auto_detect_format: bool = True
    default_encoding: str = "utf-8"


@dataclass
class DataEntry:
    """Represents a single data entry with metadata."""
    data: Any
    source: str
    format: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> DataDict:
        return {
            "data": self.data,
            "source": self.source,
            "format": self.format,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class DataSourceHandler(ABC):
    """Abstract base class for data source handlers."""

    @abstractmethod
    def can_handle(self, source: DataSource) -> bool:
        pass

    @abstractmethod
    def load_raw(self, source: DataSource, config: LoaderConfig) -> bytes:
        pass

    @abstractmethod
    def get_source_info(self, source: DataSource) -> Dict[str, Any]:
        pass


class FileHandler(DataSourceHandler):
    """Handler for local file sources."""

    def can_handle(self, source: DataSource) -> bool:
        if isinstance(source, Path):
            return True
        if isinstance(source, str):
            try:
                path = Path(source)
                return not source.startswith(("http://", "https://")) and (path.exists() or path.is_absolute())
            except (ValueError, OSError):
                return False
        return False

    def load_raw(self, source: DataSource, config: LoaderConfig) -> bytes:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")
        return path.read_bytes()

    def get_source_info(self, source: DataSource) -> Dict[str, Any]:
        path = Path(source)
        if path.exists():
            stat = path.stat()
            return {
                "type": "file",
                "path": str(path.absolute()),
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
                "exists": True,
            }
        return {"type": "file", "path": str(path), "exists": False}


class DataFormatter:
    """Handles parsing of different data formats."""

    @staticmethod
    def detect_format(data: bytes, source: str) -> str:
        """Simple format detection by file extension."""
        if isinstance(source, (str, Path)):
            path = Path(source)
            ext = path.suffix.lower()

            format_map = {
                ".json": "json",
                ".csv": "csv",
                ".tsv": "tsv",
                ".txt": "text",
            }
            if ext in format_map:
                return format_map[ext]

        # Try content-based detection for JSON
        try:
            text = data.decode("utf-8").strip()
            if text.startswith(("{", "[")):
                return "json"
        except UnicodeDecodeError:
            pass

        return "text"

    @staticmethod
    def parse(data: bytes, format_type: str, encoding: str = "utf-8") -> Any:
        """Parse data according to the specified format."""
        if format_type == "json":
            return json.loads(data.decode(encoding))
        elif format_type in ("csv", "tsv"):
            delimiter = "	" if format_type == "tsv" else ","
            text = data.decode(encoding)
            reader = csv.DictReader(StringIO(text), delimiter=delimiter)
            return list(reader)
        elif format_type == "text":
            return data.decode(encoding)
        elif format_type == "binary":
            return data
        else:
            raise ValueError(f"Unsupported format: {format_type}")


class DataCache:
    """Manages caching of loaded data."""

    def __init__(self, config: LoaderConfig):
        self.config = config
        self.cache_dir = config.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, DataEntry] = {}

    def _get_cache_key(self, source: str) -> str:
        import hashlib
        return hashlib.md5(source.encode()).hexdigest()

    def get(self, source: str) -> Optional[DataEntry]:
        if not self.config.cache_enabled:
            return None
        
        cache_key = self._get_cache_key(source)
        return self._memory_cache.get(cache_key)

    def put(self, source: str, entry: DataEntry) -> None:
        if not self.config.cache_enabled:
            return
        
        cache_key = self._get_cache_key(source)
        self._memory_cache[cache_key] = entry

    def clear(self) -> None:
        self._memory_cache.clear()


class DataLoader:
    """Main data loader class with support for multiple sources and formats."""

    def __init__(self, config: Optional[LoaderConfig] = None):
        self.config = config or LoaderConfig()
        self.cache = DataCache(self.config)
        self.handlers: List[DataSourceHandler] = [FileHandler()]

    def load(self, source: DataSource, format_type: Optional[str] = None) -> DataEntry:
        source_str = str(source)
        
        # Check cache first
        cached = self.cache.get(source_str)
        if cached:
            return cached

        # Find appropriate handler
        handler = self._find_handler(source)
        if not handler:
            raise ValueError(f"No handler available for data source: {source}")

        # Load raw data
        try:
            raw_data = handler.load_raw(source, self.config)
            source_info = handler.get_source_info(source)
        except Exception as e:
            logger.error(f"Failed to load data from {source}: {e}")
            raise

        # Detect format if not specified
        if format_type is None and self.config.auto_detect_format:
            format_type = DataFormatter.detect_format(raw_data, source_str)
        elif format_type is None:
            format_type = "text"

        # Parse data
        try:
            parsed_data = DataFormatter.parse(raw_data, format_type, self.config.default_encoding)
        except Exception as e:
            logger.error(f"Failed to parse data as {format_type}: {e}")
            raise

        # Create data entry
        import time
        entry = DataEntry(
            data=parsed_data,
            source=source_str,
            format=format_type,
            timestamp=time.time(),
            metadata=source_info,
        )

        # Store in cache
        self.cache.put(source_str, entry)
        return entry

    def load_batch(self, sources: List[DataSource]) -> List[DataEntry]:
        results = []
        for source in sources:
            try:
                entry = self.load(source)
                results.append(entry)
            except Exception as e:
                logger.error(f"Failed to load from {source}: {e}")
        return results

    def get_loader_stats(self) -> Dict[str, Any]:
        return {
            "cache_enabled": self.config.cache_enabled,
            "cache_dir": str(self.cache.cache_dir),
            "memory_cache_size": len(self.cache._memory_cache),
            "handlers_registered": len(self.handlers),
        }

    def _find_handler(self, source: DataSource) -> Optional[DataSourceHandler]:
        for handler in self.handlers:
            if handler.can_handle(source):
                return handler
        return None


# Convenience functions
def load_data(source: DataSource, format_type: Optional[str] = None, **kwargs) -> Any:
    config = LoaderConfig(**kwargs) if kwargs else LoaderConfig()
    loader = DataLoader(config)
    entry = loader.load(source, format_type)
    return entry.data


def load_json(source: DataSource, **kwargs) -> Union[Dict, List]:
    return load_data(source, "json", **kwargs)


def load_csv(source: DataSource, **kwargs) -> List[Dict]:
    return load_data(source, "csv", **kwargs)


def create_default_loader() -> DataLoader:
    return DataLoader()
