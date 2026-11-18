from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    error: str
    detail: Any = None


COMMON_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorBody, "description": "Некорректный запрос"},
    401: {"model": ErrorBody, "description": "Нет bearer token"},
    403: {"model": ErrorBody, "description": "Доступ запрещен"},
    404: {"model": ErrorBody, "description": "Объект не найден"},
    409: {"model": ErrorBody, "description": "Конфликт состояния"},
    422: {"model": ErrorBody, "description": "Ошибка валидации"},
}
