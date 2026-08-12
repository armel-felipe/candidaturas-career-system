from __future__ import annotations

from .fit_map import FitMapDraftSchema, FitMapFinalSchema
from .notion import NotionApplicationRecordSchema, NotionApplicationsCacheSchema
from .review import CvReviewReportSchema

__all__ = [
    "CvReviewReportSchema",
    "FitMapDraftSchema",
    "FitMapFinalSchema",
    "NotionApplicationRecordSchema",
    "NotionApplicationsCacheSchema",
]

