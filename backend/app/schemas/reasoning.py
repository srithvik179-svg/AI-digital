from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime

class ConditionSchema(BaseModel):
    metric: str = Field(..., description="The telemetry metric name (e.g. cpu_usage, cpu_temperature, etc.)")
    operator: str = Field(..., description="Comparison operator (e.g. >, <, >=, <=, ==, !=)")
    value: Union[float, str] = Field(..., description="Threshold value (can be float or string)")

class RuleCreate(BaseModel):
    name: str = Field(..., description="Name of the reasoning rule")
    description: Optional[str] = Field(None, description="Optional explanation of what the rule checks")
    conditions: List[ConditionSchema] = Field(..., description="List of conditions that must be evaluated")
    logical_operator: str = Field("AND", description="Logical combining operator ('AND' or 'OR')")
    conclusion: str = Field(..., description="The conclusion triggered by this rule")
    severity: str = Field("info", description="Severity category ('info', 'warning', 'critical')")
    is_active: bool = Field(True, description="Whether the rule is enabled")

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[ConditionSchema]] = None
    logical_operator: Optional[str] = None
    conclusion: Optional[str] = None
    severity: Optional[str] = None
    is_active: Optional[bool] = None

class RuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    conditions: List[ConditionSchema]
    logical_operator: str
    conclusion: str
    severity: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EvaluationResult(BaseModel):
    rule_id: str
    rule_name: str
    triggered: bool
    explanation: str
    evidence: dict = Field(..., description="Key-value pairs of metrics evaluated and their actual telemetry values")
    severity: str
