"""Artifact storage system for reducing context usage in proposals.

Large data objects (like merge proposals with extensive properties) can be stored
as artifacts and referenced by ID, reducing the size of proposals sent to the client.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ArtifactStore:
    """In-memory artifact storage with automatic expiration."""

    def __init__(self, ttl_minutes: int = 60):
        """Initialize artifact store.

        Args:
            ttl_minutes: Time-to-live for artifacts in minutes
        """
        self._store: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)

    def store(self, data: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store data and return an artifact ID.

        Args:
            data: Data to store
            metadata: Optional metadata about the artifact

        Returns:
            Artifact ID
        """
        artifact_id = str(uuid.uuid4())
        self._store[artifact_id] = {
            "data": data,
            "metadata": metadata or {},
            "created_at": datetime.now(),
            "accessed_at": datetime.now(),
            "access_count": 0,
        }
        logger.debug(f"Stored artifact {artifact_id}")
        return artifact_id

    def retrieve(self, artifact_id: str) -> Optional[Any]:
        """Retrieve data by artifact ID.

        Args:
            artifact_id: ID of artifact to retrieve

        Returns:
            Stored data or None if not found/expired
        """
        # Clean up expired artifacts
        self._cleanup_expired()

        if artifact_id not in self._store:
            logger.warning(f"Artifact {artifact_id} not found")
            return None

        artifact = self._store[artifact_id]

        # Update access info
        artifact["accessed_at"] = datetime.now()
        artifact["access_count"] += 1

        return artifact["data"]

    def delete(self, artifact_id: str) -> bool:
        """Delete an artifact.

        Args:
            artifact_id: ID of artifact to delete

        Returns:
            True if deleted, False if not found
        """
        if artifact_id in self._store:
            del self._store[artifact_id]
            logger.debug(f"Deleted artifact {artifact_id}")
            return True
        return False

    def get_metadata(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata about an artifact without retrieving the data.

        Args:
            artifact_id: ID of artifact

        Returns:
            Metadata dict or None if not found
        """
        if artifact_id not in self._store:
            return None

        artifact = self._store[artifact_id]
        return {
            "metadata": artifact["metadata"],
            "created_at": artifact["created_at"].isoformat(),
            "accessed_at": artifact["accessed_at"].isoformat(),
            "access_count": artifact["access_count"],
        }

    def _cleanup_expired(self) -> None:
        """Remove expired artifacts."""
        now = datetime.now()
        expired = [
            aid
            for aid, artifact in self._store.items()
            if (now - artifact["created_at"]) > self.ttl
        ]

        for aid in expired:
            del self._store[aid]
            logger.debug(f"Removed expired artifact {aid}")

    def clear(self) -> None:
        """Clear all artifacts."""
        count = len(self._store)
        self._store.clear()
        logger.info(f"Cleared {count} artifacts")

    def stats(self) -> Dict[str, Any]:
        """Get statistics about the artifact store.

        Returns:
            Stats dictionary
        """
        self._cleanup_expired()
        return {
            "total_artifacts": len(self._store),
            "total_access_count": sum(a["access_count"] for a in self._store.values()),
            "average_access_count": (
                sum(a["access_count"] for a in self._store.values()) / len(self._store)
                if self._store
                else 0
            ),
        }


# Global artifact store instance
_global_store: Optional[ArtifactStore] = None


def get_artifact_store(ttl_minutes: int = 60) -> ArtifactStore:
    """Get the global artifact store instance.

    Args:
        ttl_minutes: Time-to-live for artifacts (only used on first call)

    Returns:
        ArtifactStore instance
    """
    global _global_store
    if _global_store is None:
        _global_store = ArtifactStore(ttl_minutes=ttl_minutes)
    return _global_store


def should_use_artifact(data: Dict[str, Any], threshold_kb: int = 5) -> bool:
    """Determine if data should be stored as artifact based on size.

    Args:
        data: Data to check
        threshold_kb: Size threshold in kilobytes

    Returns:
        True if data should be stored as artifact
    """
    import json

    try:
        size_bytes = len(json.dumps(data).encode("utf-8"))
        size_kb = size_bytes / 1024
        return size_kb > threshold_kb
    except Exception:
        return False


def create_merge_artifact(
    primary_props: Dict[str, Any],
    secondary_props: Dict[str, Any],
    merged_props: Dict[str, Any],
    threshold_kb: int = 5,
) -> Optional[str]:
    """Create artifact for merge node data if size exceeds threshold.

    Args:
        primary_props: Primary node properties
        secondary_props: Secondary node properties
        merged_props: Merged properties
        threshold_kb: Size threshold in KB

    Returns:
        Artifact ID if created, None otherwise
    """
    full_data = {
        "primary_properties": primary_props,
        "secondary_properties": secondary_props,
        "merged_properties": merged_props,
    }

    if should_use_artifact(full_data, threshold_kb):
        store = get_artifact_store()
        artifact_id = store.store(
            full_data,
            metadata={
                "type": "merge_node",
                "primary_props_count": len(primary_props),
                "secondary_props_count": len(secondary_props),
                "merged_props_count": len(merged_props),
            },
        )
        logger.info(
            f"Created merge artifact {artifact_id} "
            f"({len(primary_props)} + {len(secondary_props)} → {len(merged_props)} properties)"
        )
        return artifact_id

    return None
