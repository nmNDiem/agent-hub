from datetime import datetime

from pydantic import BaseModel


class UsageSummaryResponse(BaseModel):
    period_started_at: datetime
    period_ends_at: datetime
    timezone: str
    generated_turns: int
    generated_turn_limit: int
    generated_turns_remaining: int
    generation_model_calls: int
    vision_model_calls: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
