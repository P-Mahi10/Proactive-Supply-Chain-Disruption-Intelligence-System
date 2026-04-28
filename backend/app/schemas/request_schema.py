from typing import Dict, Any
from pydantic import BaseModel

class InputRequest(BaseModel):
    """
    Standard request schema for all pipeline endpoints.
    Contains the input features needed for prediction and simulation.
    """
    input_data: Dict[str, Any]
