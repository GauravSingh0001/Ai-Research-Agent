"""
Synthesis Cache Layer
Caches analysis results and synthesis outputs to avoid redundant processing.

Features:
  - Analysis cache: Skip re-analysis of unchanged papers
  - Synthesis cache: Reuse previously generated sections for same papers
  - TTL-based invalidation: Cache expires after 24 hours
  - Hash-based validation: Detect changes in paper data
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

try:
    from src.config import DATA_DIR
except ImportError:
    from config import DATA_DIR


class SynthesisCache:
    """
    Cache for analysis and synthesis results.
    Stores hashes of input data to detect changes.
    """

    def __init__(self, cache_dir: str = None):
        """Initialize cache directory."""
        self.cache_dir = Path(cache_dir) if cache_dir else DATA_DIR / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.analysis_cache_file = self.cache_dir / "analysis_cache.json"
        self.synthesis_cache_file = self.cache_dir / "synthesis_cache.json"
        self.metadata_cache_file = self.cache_dir / "metadata_cache.json"
        
        self._load_caches()

    def _load_caches(self):
        """Load existing caches from disk."""
        self.analysis_cache = self._load_json(self.analysis_cache_file) or {}
        self.synthesis_cache = self._load_json(self.synthesis_cache_file) or {}
        self.metadata_cache = self._load_json(self.metadata_cache_file) or {}

    @staticmethod
    def _load_json(path: Path) -> Optional[Dict]:
        """Load JSON file safely."""
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    @staticmethod
    def _compute_hash(data: Any) -> str:
        """Compute SHA256 hash of data for change detection."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    @staticmethod
    def _is_expired(timestamp_str: str, ttl_hours: int = 24) -> bool:
        """Check if cache entry is expired."""
        try:
            created = datetime.fromisoformat(timestamp_str)
            return datetime.now() - created > timedelta(hours=ttl_hours)
        except Exception:
            return True

    def get_analysis_result(self, papers: List[Dict]) -> Optional[Dict]:
        """
        Get cached analysis result if papers haven't changed.
        
        Returns:
            Cached analysis dict, or None if cache miss/expired
        """
        papers_hash = self._compute_hash(papers)
        cache_key = f"papers_{papers_hash}"
        
        if cache_key in self.analysis_cache:
            entry = self.analysis_cache[cache_key]
            if not self._is_expired(entry.get("created_at", "")):
                return entry.get("result")
        
        return None

    def set_analysis_result(self, papers: List[Dict], result: Dict) -> bool:
        """
        Cache analysis result with papers hash.
        
        Args:
            papers: Original papers list
            result: Analysis results from PaperAnalyzer
        
        Returns:
            True if cached successfully
        """
        try:
            papers_hash = self._compute_hash(papers)
            cache_key = f"papers_{papers_hash}"
            
            self.analysis_cache[cache_key] = {
                "created_at": datetime.now().isoformat(),
                "result": result,
                "papers_hash": papers_hash,
                "num_papers": len(papers),
            }
            
            self._save_cache(self.analysis_cache, self.analysis_cache_file)
            return True
        except Exception:
            return False

    def get_synthesis_result(self, papers: List[Dict], section: str = None) -> Optional[Dict]:
        """
        Get cached synthesis result.
        
        Args:
            papers: List of papers used for synthesis
            section: Optional section name (if caching individual sections)
        
        Returns:
            Cached synthesis dict, or None if cache miss/expired
        """
        papers_hash = self._compute_hash(papers)
        
        if section:
            cache_key = f"section_{papers_hash}_{section}"
        else:
            cache_key = f"synthesis_{papers_hash}"
        
        if cache_key in self.synthesis_cache:
            entry = self.synthesis_cache[cache_key]
            if not self._is_expired(entry.get("created_at", "")):
                return entry.get("result")
        
        return None

    def set_synthesis_result(self, papers: List[Dict], result: Dict, section: str = None) -> bool:
        """
        Cache synthesis result.
        
        Args:
            papers: List of papers
            result: Synthesis output (full document or section)
            section: Optional section name
        
        Returns:
            True if cached successfully
        """
        try:
            papers_hash = self._compute_hash(papers)
            
            if section:
                cache_key = f"section_{papers_hash}_{section}"
            else:
                cache_key = f"synthesis_{papers_hash}"
            
            self.synthesis_cache[cache_key] = {
                "created_at": datetime.now().isoformat(),
                "result": result,
                "papers_hash": papers_hash,
                "num_papers": len(papers),
                "section": section,
            }
            
            self._save_cache(self.synthesis_cache, self.synthesis_cache_file)
            return True
        except Exception:
            return False

    def invalidate_analysis_cache(self):
        """Clear all analysis cache (when papers change)."""
        self.analysis_cache = {}
        self._save_cache(self.analysis_cache, self.analysis_cache_file)

    def invalidate_synthesis_cache(self):
        """Clear all synthesis cache (when synthesis logic changes)."""
        self.synthesis_cache = {}
        self._save_cache(self.synthesis_cache, self.synthesis_cache_file)

    def invalidate_all(self):
        """Clear all caches."""
        self.invalidate_analysis_cache()
        self.invalidate_synthesis_cache()
        self.metadata_cache = {}
        self._save_cache(self.metadata_cache, self.metadata_cache_file)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "analysis_entries": len(self.analysis_cache),
            "synthesis_entries": len(self.synthesis_cache),
            "cache_dir": str(self.cache_dir),
            "total_size_mb": self._get_cache_size() / (1024 * 1024),
        }

    def _get_cache_size(self) -> int:
        """Get total cache directory size in bytes."""
        total = 0
        for file in self.cache_dir.glob("*.json"):
            total += file.stat().st_size
        return total

    @staticmethod
    def _save_cache(cache_dict: Dict, cache_file: Path) -> bool:
        """Save cache dictionary to JSON file."""
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_dict, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


# Convenience functions for single-instance caching
_global_cache: Optional[SynthesisCache] = None


def get_cache() -> SynthesisCache:
    """Get or create global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = SynthesisCache()
    return _global_cache


def clear_cache():
    """Clear global cache instance."""
    global _global_cache
    if _global_cache:
        _global_cache.invalidate_all()
    _global_cache = None
