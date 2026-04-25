from typing import Dict, Union

from pydantic import BaseModel, Field


class InputRequest(BaseModel):
    # Feature-engineered inputs including lag features.
    input_data: Dict[str, Union[float, str]] = Field(default_factory=dict)
