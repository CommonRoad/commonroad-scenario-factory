from pydantic import ConfigDict, BaseModel


class TestCase(BaseModel):
    """
    Pydantic model for test cases.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    label: str