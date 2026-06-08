from pydantic import BaseModel, Field


class DocumentationAssistantStatusResponse(BaseModel):
    configured: bool
    model: str
    message: str


class DocumentationAssistantRequest(BaseModel):
    question: str = Field(min_length=8, max_length=4000)


class DocumentationAssistantResponse(BaseModel):
    answer: str
    configured: bool
    model: str
