from enum import StrEnum


class LifecycleEvent(StrEnum):
    CREATED = "created"
    SUBMITTED_REVIEW = "submitted_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
