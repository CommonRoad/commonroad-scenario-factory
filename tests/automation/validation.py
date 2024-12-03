import pydantic


class TestCase(pydantic.BaseModel):
    """
    Base class for all Test Case Models.
    """

    label: str

    class Config:
        arbitrary_types_allowed = True
