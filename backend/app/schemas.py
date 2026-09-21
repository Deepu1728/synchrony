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
    true_label: bool | None


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