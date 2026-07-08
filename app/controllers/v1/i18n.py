import json
from pathlib import Path

from fastapi import Request

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.utils import utils

router = new_router()

_I18N_DIR = Path(__file__).resolve().parents[3] / "webui" / "i18n"
_KNOWN_LOCALES = {"de", "en", "es", "id", "pt", "ru", "tr", "vi", "zh"}


@router.get("/i18n/{locale}", response_model=None, summary="Translation strings for a locale")
def get_translations(request: Request, locale: str):
    request_id = base.get_task_id(request)
    if locale not in _KNOWN_LOCALES:
        raise HttpException(
            task_id=request_id,
            status_code=404,
            message=f"{request_id}: unknown locale: {locale}",
        )

    path = _I18N_DIR / f"{locale}.json"
    if not path.is_file():
        raise HttpException(
            task_id=request_id,
            status_code=404,
            message=f"{request_id}: locale file not found: {locale}",
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    return utils.get_response(200, data)
