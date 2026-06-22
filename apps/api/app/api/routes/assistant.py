from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.schemas.assistant import (
    DocumentationAssistantRequest,
    DocumentationAssistantResponse,
    DocumentationAssistantStatusResponse,
)
from app.services.documentation_assistant import (
    DocumentationAssistantNotConfiguredError,
    DocumentationAssistantService,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/docs/status", response_model=DocumentationAssistantStatusResponse)
def get_documentation_assistant_status(current_user: CurrentUser) -> DocumentationAssistantStatusResponse:
    service = DocumentationAssistantService()
    return DocumentationAssistantStatusResponse(
        configured=service.is_configured,
        model=service.settings.xai_model,
        message=service.status_message(),
    )


@router.post("/docs/answer", response_model=DocumentationAssistantResponse)
def ask_documentation_assistant(
    payload: DocumentationAssistantRequest,
    current_user: CurrentUser,
) -> DocumentationAssistantResponse:
    service = DocumentationAssistantService()
    try:
        answer = service.answer(payload.question)
    except DocumentationAssistantNotConfiguredError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI documentation helper could not answer right now. Please try again.",
        ) from error

    return DocumentationAssistantResponse(
        answer=answer,
        configured=service.is_configured,
        model=service.settings.xai_model,
    )
