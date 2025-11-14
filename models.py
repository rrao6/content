"""Domain models for content info records."""
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ContentInfo:
    """Representation of a row from the content_info table."""

    content_id: Optional[int]
    content_name: Optional[str]
    is_episode: Optional[bool]
    program_name: Optional[str]
    program_id: Optional[int]
    content_type: Optional[str]
    parent_id: Optional[int]
    import_id: Optional[str]
    publisher_id: Optional[str]
    active: Optional[bool]
    policy: Optional[str]
    content_partner_id: Optional[str]
    gracenote_id: Optional[str]
    program_gracenote_id: Optional[str]
    duration: Optional[float]
    cue_points: Optional[str]
    credit_cue_point: Optional[float]
    rating: Optional[str]
    mpaa_rating: Optional[str]
    tvpg_rating: Optional[str]
    poster_img_url: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> "ContentInfo":
        """Build a ContentInfo from the DB-API row object."""
        return cls(
            content_id=getattr(row, "content_id", None),
            content_name=getattr(row, "content_name", None),
            is_episode=getattr(row, "is_episode", None),
            program_name=getattr(row, "program_name", None),
            program_id=getattr(row, "program_id", None),
            content_type=getattr(row, "content_type", None),
            parent_id=getattr(row, "parent_id", None),
            import_id=getattr(row, "import_id", None),
            publisher_id=getattr(row, "publisher_id", None),
            active=getattr(row, "active", None),
            policy=getattr(row, "policy", None),
            content_partner_id=getattr(row, "content_partner_id", None),
            gracenote_id=getattr(row, "gracenote_id", None),
            program_gracenote_id=getattr(row, "program_gracenote_id", None),
            duration=getattr(row, "duration", None),
            cue_points=getattr(row, "cue_points", None),
            credit_cue_point=getattr(row, "credit_cue_point", None),
            rating=getattr(row, "rating", None),
            mpaa_rating=getattr(row, "mpaa_rating", None),
            tvpg_rating=getattr(row, "tvpg_rating", None),
            poster_img_url=getattr(row, "poster_img_url", None),
        )


@dataclass(frozen=True)
class PosterImage:
    """Lightweight representation for poster image extraction."""

    content_id: Optional[int]
    poster_img_url: Optional[str]

    @classmethod
    def from_row(cls, row: Any) -> "PosterImage":
        return cls(
            content_id=getattr(row, "content_id", None),
            poster_img_url=getattr(row, "poster_img_url", None),
        )

