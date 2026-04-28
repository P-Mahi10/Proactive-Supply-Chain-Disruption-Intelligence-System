from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field

class InputRequest(BaseModel):
    """
    Standard request schema for all pipeline endpoints.
    Contains the input features needed for prediction and simulation.
    """
    input_data: Dict[str, Any]


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    message: Dict[str, Any]
