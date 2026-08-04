"""Keyword-based expense classifier.

Loads keywords from the database and matches vendor text to categories.
Maintains an in-memory cache that can be refreshed when admin modifies keywords.
"""

from typing import Optional

from bot import db


class Classifier:
    """Classifies vendor text into categories using keyword matching."""

    def __init__(self) -> None:
        self._keywords: list[dict] = []
        self.refresh()

    def refresh(self) -> None:
        """Reload keywords from database."""
        self._keywords = db.get_keywords()

    def classify(self, vendor_text: Optional[str]) -> tuple[Optional[int], Optional[str]]:
        """Classify vendor text into a category.

        Returns (category_id, category_name) or (None, None) if no match.
        """
        if not vendor_text:
            return None, None

        text_lower = vendor_text.lower()

        for kw in self._keywords:
            if kw["keyword"].lower() in text_lower:
                category = db.get_category(kw["category_id"])
                if category:
                    return category["id"], category["name"]

        return None, None


# Global classifier instance
_classifier: Optional[Classifier] = None


def get_classifier() -> Classifier:
    """Get or create the global classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = Classifier()
    return _classifier


def refresh_classifier() -> None:
    """Refresh the global classifier's keyword cache."""
    get_classifier().refresh()
