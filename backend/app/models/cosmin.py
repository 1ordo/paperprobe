from sqlalchemy import String, Text, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CosminBox(Base):
    __tablename__ = "cosmin_boxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    box_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prerequisite: Mapped[str | None] = mapped_column(Text, nullable=True)

    sub_boxes = relationship("CosminSubBox", back_populates="box", cascade="all, delete-orphan", order_by="CosminSubBox.sort_order")


class CosminSubBox(Base):
    __tablename__ = "cosmin_sub_boxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    box_id: Mapped[int] = mapped_column(Integer, ForeignKey("cosmin_boxes.id", ondelete="CASCADE"), nullable=False)
    sub_box_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    box = relationship("CosminBox", back_populates="sub_boxes")
    standards = relationship("CosminStandard", back_populates="sub_box", cascade="all, delete-orphan", order_by="CosminStandard.sort_order")

    __table_args__ = (
        {"comment": "Sub-sections within a COSMIN box (e.g. 1a, 1b, 2a-2f, 9a, 9b, 10a-10d)"},
    )


class CosminStandard(Base):
    __tablename__ = "cosmin_standards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_box_id: Mapped[int] = mapped_column(Integer, ForeignKey("cosmin_sub_boxes.id", ondelete="CASCADE"), nullable=False)
    standard_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rating_very_good: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating_adequate: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating_doubtful: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating_inadequate: Mapped[str | None] = mapped_column(Text, nullable=True)
    na_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    has_sub_criteria: Mapped[bool] = mapped_column(Boolean, default=False)
    sub_criteria_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    sub_box = relationship("CosminSubBox", back_populates="standards")
