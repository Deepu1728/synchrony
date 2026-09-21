from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccountId = Annotated[str, Field(pattern=r"^[CM][0-9]{1,12}$")]
Money = Annotated[float, Field(ge=0, le=1e11, allow_inf_nan=False)]


class TransactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=1, le=100_000)
    type: Literal["TRANSFER", "CASH_OUT"]
    amount: Money
    name_orig: AccountId
    oldbalance_org: Money
    newbalance_orig: Money
    name_dest: AccountId
    oldbalance_dest: Money
    newbalance_dest: Money
    true_label: bool | None = None

    @model_validator(mode="after")
    def parties_differ(self):
        if self.name_orig == self.name_dest:
            raise ValueError("name_orig and name_dest must differ")
        return self


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    role: str


class ReasonOut(BaseModel):
    feature: str
    label: str
    value: float
    shap: float
    direction: str
    text: str


class RuleFlagOut(BaseModel):
    code: str
    message: str
    weight: float


class ScoreOut(BaseModel):
    transaction_id: int
    decision: Literal["approve", "review", "block"]
    combined_score: float
    xgb_proba: float
    anomaly_percentile: float
    similarity_score: float
    fraud_neighbours: int
    rule_score: float
    rules: list[RuleFlagOut]
    alert_id: int | None
    explanation: str | None
    reasons: list[ReasonOut]
    latency_ms: float


class TransactionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step: int
    type: str
    amount: float
    name_orig: str
    name_dest: str
    oldbalance_org: float
    newbalance_orig: float
    oldbalance_dest: float
    newbalance_dest: float
    true_label: bool | None
    created_at: datetime


class ScoreBreakdown(BaseModel):
    model: float
    similarity: float
    anomaly: float
    rules: float
    combined: float


class Thresholds(BaseModel):
    review: float
    block: float


class FeedbackInfo(BaseModel):
    verdict: str
    username: str
    note: str | None
    created_at: datetime


class AlertOut(BaseModel):
    id: int
    decision: str
    score: float
    status: str
    reasons: list[ReasonOut]
    rules: list[RuleFlagOut]
    explanation_text: str | None
    explanation_source: str
    created_at: datetime
    transaction: TransactionSummary
    scores: ScoreBreakdown
    thresholds: Thresholds
    feedback: FeedbackInfo | None = None


class AlertList(BaseModel):
    total: int
    items: list[AlertOut]


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: int = Field(ge=1)
    verdict: Literal["fraud", "legit"]
    note: str | None = Field(default=None, max_length=500)


class FeedbackOut(BaseModel):
    id: int
    alert_id: int
    verdict: str
    alert_status: str
    case_added: bool


class ReportFraudIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class ReportFraudOut(BaseModel):
    transaction_id: int
    case_id: int
    case_added: bool


class PreviewOut(BaseModel):
    decision: Literal["approve", "review", "block"]
    combined_score: float
    xgb_proba: float
    similarity_score: float
    rules: list[RuleFlagOut]


class FeedRow(BaseModel):
    id: int
    created_at: datetime
    step: int
    type: str
    amount: float
    name_orig: str
    name_dest: str
    decision: Literal["approve", "review", "block"]
    score: float
    alert_id: int | None
    alert_status: str | None
    true_label: bool | None


class FeedOut(BaseModel):
    items: list[FeedRow]
    last_id: int | None


class SimilarCase(BaseModel):
    id: int
    label: str
    source: str
    distance: float
    type: str | None
    amount: float | None
    hour: int | None
    note: str | None
    alert_id: int | None


class SimilarSummary(BaseModel):
    fraud: int
    legit: int
    learned_fraud: int
    learned_legit: int


class SimilarOut(BaseModel):
    alert_id: int
    k: int
    cases: list[SimilarCase]
    summary: SimilarSummary


class DecisionCounts(BaseModel):
    total: int
    approve: int
    review: int
    block: int


class GroundTruthMetrics(BaseModel):
    labelled: int
    fraud_total: int
    fraud_flagged: int
    fraud_blocked: int
    genuine_total: int
    genuine_flagged: int
    genuine_blocked: int
    catch_rate: float | None
    block_catch_rate: float | None
    false_positive_rate: float | None
    false_block_rate: float | None
    precision_flagged: float | None
    precision_block: float | None
    stream_fraud_share: float | None


class AlertStats(BaseModel):
    open: int
    confirmed_fraud: int
    false_positive: int
    reviewed: int
    analyst_precision: float | None


class LearnedCases(BaseModel):
    fraud: int
    legit: int


class MetricsOut(BaseModel):
    window_minutes: int | None
    decisions: DecisionCounts
    ground_truth: GroundTruthMetrics
    alerts: AlertStats
    learned_cases: LearnedCases
    note: str