from fastapi import Cookie, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal
from passlib.context import CryptContext
from typing import Optional
import models

templates   = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
sessions    = {}
PAGE_SIZE   = 12


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    if session_token and session_token in sessions:
        user_id = sessions[session_token]
        return db.query(models.User).filter(models.User.id == user_id).first()
    return None


def build_ratings_list(products: list) -> list:
    """Devuelve lista de (product, rating_count, avg_rating) ordenada por rating."""
    result = [
        (p, len(p.ratings), round(sum(r.score for r in p.ratings) / len(p.ratings), 1) if p.ratings else 0)
        for p in products
    ]
    result.sort(key=lambda x: (x[2], x[1]), reverse=True)
    return result


def paginate(items: list, page: int) -> dict:
    """Pagina una lista y devuelve los datos necesarios para el template."""
    total = len(items)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    return {
        "items": items[(page - 1) * PAGE_SIZE: page * PAGE_SIZE],
        "page": page,
        "total_pages": total_pages,
        "total": total,
    }
