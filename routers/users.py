from fastapi import APIRouter, Depends, Request, Form, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import models
from dependencies import templates, pwd_context, sessions, get_db, get_current_user, build_ratings_list, paginate

router = APIRouter()


@router.get("/user/{user_id}", response_class=HTMLResponse)
def user_detail(
    request: Request,
    user_id: int,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    user = db.query(models.User).options(joinedload(models.User.products).joinedload(models.Product.ratings)).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    rated = build_ratings_list(user.products)
    paged = paginate(rated, page)

    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user": user,
        "current_user": current_user,
        "products_with_ratings": paged["items"],
        "page": paged["page"],
        "total_pages": paged["total_pages"],
        "total": paged["total"],
    })


@router.get("/my_products", response_class=HTMLResponse)
def my_products(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = 1
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    rated = build_ratings_list(db.query(models.Product).options(joinedload(models.Product.ratings)).filter(models.Product.owner_id == current_user.id).all())
    paged = paginate(rated, page)

    return templates.TemplateResponse("my_products.html", {
        "request": request,
        "products_with_ratings": paged["items"],
        "current_user": current_user,
        "page": paged["page"],
        "total_pages": paged["total_pages"],
        "total": paged["total"],
    })


@router.get("/edit_profile", response_class=HTMLResponse)
def edit_profile_form(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("edit_profile.html", {"request": request, "current_user": current_user})


@router.post("/edit_profile")
def edit_profile(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    whatsapp: str = Form(...),
    current_password: str = Form(...),
    new_password: str = Form(""),
    confirm_new_password: str = Form(""),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if not pwd_context.verify(current_password, current_user.hashed_password):
        return templates.TemplateResponse("edit_profile.html", {
            "request": request, "current_user": current_user,
            "msg": "Contraseña actual incorrecta.", "msg_type": "error"
        })

    existing = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == email),
        models.User.id != current_user.id
    ).first()
    if existing:
        return templates.TemplateResponse("edit_profile.html", {
            "request": request, "current_user": current_user,
            "msg": "El usuario o correo ya está en uso.", "msg_type": "error"
        })

    if new_password:
        if new_password != confirm_new_password:
            return templates.TemplateResponse("edit_profile.html", {
                "request": request, "current_user": current_user,
                "msg": "Las contraseñas nuevas no coinciden.", "msg_type": "error"
            })
        current_user.hashed_password = pwd_context.hash(new_password)

    current_user.username = username
    current_user.email = email
    current_user.whatsapp = whatsapp
    db.commit()
    db.refresh(current_user)

    return templates.TemplateResponse("edit_profile.html", {
        "request": request, "current_user": current_user,
        "msg": "Perfil actualizado correctamente.", "msg_type": "success"
    })


@router.post("/delete_account")
def delete_account(
    request: Request,
    password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    session_token: Optional[str] = Cookie(None)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if not pwd_context.verify(password, current_user.hashed_password):
        return templates.TemplateResponse("edit_profile.html", {
            "request": request, "current_user": current_user,
            "msg": "Contraseña incorrecta. No se eliminó la cuenta.", "msg_type": "error"
        })

    if session_token and session_token in sessions:
        del sessions[session_token]

    db.delete(current_user)
    db.commit()

    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_token")
    return response
