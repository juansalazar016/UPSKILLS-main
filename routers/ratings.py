from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import models
from dependencies import get_db, get_current_user

router = APIRouter()


@router.post("/rate_product/{product_id}")
def rate_product(
    product_id: int,
    score: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para puntuar un producto")

    if score < 1 or score > 5:
        raise HTTPException(status_code=400, detail="La puntuación debe estar entre 1 y 5")

    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    existing_rating = db.query(models.Rating).filter(
        models.Rating.user_id == current_user.id,
        models.Rating.product_id == product_id
    ).first()
    if existing_rating:
        raise HTTPException(status_code=400, detail="Ya has puntuado este producto")

    db.add(models.Rating(user_id=current_user.id, product_id=product_id, score=score))
    db.commit()

    return RedirectResponse(url=f"/product/{product_id}", status_code=status.HTTP_302_FOUND)
