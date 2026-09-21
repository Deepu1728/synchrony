from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, Float,
                        ForeignKey, Index, Integer, String, Text, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.scoring.embedding import DIM


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role in ('admin','analyst')", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="analyst")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type in ('TRANSFER','CASH_OUT')", name="ck_txn_type"),
        CheckConstraint("decision in ('approve','review','block')", name="ck_txn_decision"),
        Index("ix_txn_dest_step", "name_dest", "step"),
        Index("ix_txn_orig_step", "name_orig", "step"),
        Index("ix_txn_pair", "name_orig", "name_dest"),
        Index("ix_txn_step", "step"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    step: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[float] = mapped_column(Float)
    name_orig: Mapped[str] = mapped_column(String(32))
    oldbalance_org: Mapped[float] = mapped_column(Float)
    newbalance_orig: Mapped[float] = mapped_column(Float)
    name_dest: Mapped[str] = mapped_column(String(32))
    oldbalance_dest: Mapped[float] = mapped_column(Float)
    newbalance_dest: Mapped[float] = mapped_column(Float)

    features: Mapped[dict] = mapped_column(JSONB)
    rule_flags: Mapped[list] = mapped_column(JSONB, default=list)
    rule_score: Mapped[float] = mapped_column(Float, default=0.0)
    xgb_proba: Mapped[float] = mapped_column(Float)
    anomaly_percentile: Mapped[float] = mapped_column(Float)
    similarity_score: Mapped[float] = mapped_column(Float)
    combined_score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(8))
    true_label: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alert: Mapped["Alert | None"] = relationship(back_populates="transaction")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("status in ('open','confirmed_fraud','false_positive')", name="ck_alert_status"),
        CheckConstraint("explanation_source in ('llm','shap_fallback')", name="ck_alert_source"),
        Index("ix_alerts_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), unique=True)
    score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(20), default="open")
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    explanation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_source: Mapped[str] = mapped_column(String(16), default="shap_fallback")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transaction: Mapped[Transaction] = relationship(back_populates="alert")
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="alert")


class FraudCase(Base):
    __tablename__ = "fraud_cases"
    __table_args__ = (
        CheckConstraint("label in ('fraud','legit')", name="ck_case_label"),
        Index(
            "ix_fraud_cases_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_l2_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(DIM))
    label: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(32))
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("verdict in ('fraud','legit')", name="ck_feedback_verdict"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    verdict: Mapped[str] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alert: Mapped[Alert] = relationship(back_populates="feedback")