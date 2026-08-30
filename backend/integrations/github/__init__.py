"""
GitHub integration module.
Handles GitHub API interactions and data normalization.
"""

from .client import GitHubClient
from .normalizer import GitHubNormalizer

__all__ = ["GitHubClient", "GitHubNormalizer"]
