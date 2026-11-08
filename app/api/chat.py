"""Chat endpoint: the AI assistant (app/services/chat_answer.py).

The server picks the facts from the database with the site's own rules and
the model only words a short answer, which is checked before it is sent.
"""
from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import schemas
from app.api.deps import get_current_user, get_db
from app.core.rate_limit import limit
from app.services import chat_answer

router = APIRouter(prefix="/chat", tags=["chat"])

_FAILED = {
    "ru": "Не получилось ответить. Попробуйте ещё раз через минуту.",
    "lv": "Neizdevās atbildēt. Mēģiniet vēlreiz pēc minūtes.",
    "en": "Sorry, I couldn't process your request. Please try again.",
}


@router.post(
    "",
    response_model=schemas.ChatResponse,
    dependencies=[Depends(limit("chat", 20, 600))],
)
async def chat(
    payload: schemas.ChatRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lang = payload.lang if payload.lang in ("ru", "lv", "en") else "en"
    try:
        a = await chat_answer.answer(
            db,
            message=payload.message,
            history=payload.history[-6:],
            user_id=user.id,
            product_id=payload.product_id,
            ui_lang=lang,
        )
        q = a.query
        logger.info(
            f"[CHAT] user={user.id} intent={q.intent} parsed_by={q.parsed_by} brand={q.brand!r} "
            f"name={q.name!r} conc={q.concentration} ml={q.volume_ml} store={q.store} "
            f"facts={a.facts.kind if a.facts else '-'} how={a.how}"
        )
        return schemas.ChatResponse(reply=a.reply)
    except Exception as e:
        logger.exception(f"[CHAT] Error processing request: {e}")
        return schemas.ChatResponse(reply=_FAILED[chat_answer.detect_lang(payload.message, lang)])
