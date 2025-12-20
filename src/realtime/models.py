from typing import Optional, Dict, List
from pydantic import BaseModel, Field

class ConversationState(BaseModel):
    """
    Simplified state for the minimal script-based approach.
    We just track the last analysis result.
    """
    script_location: str = "Unknown"
    key_points: List[str] = Field(default_factory=list)
    suggestion: str = ""
    last_updated: float = 0.0
