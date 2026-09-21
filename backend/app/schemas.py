from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccountId = Annotated[str, Field(pattern=r"^[CM][0-9]{6,12}$")]
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