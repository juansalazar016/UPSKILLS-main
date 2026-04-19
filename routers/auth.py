from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import uuid
import models
from dependencies import templates, pwd_context, sessions, get_db

router = APIRouter()


@router.get("/register", response_class=HTMLResponse)
def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    whatsapp: str = Form(""),
    db: Session = Depends(get_db)
):
    if len(password) < 6:
        return templates.TemplateResponse("register.html", {
            "request": request, "msg": "La contraseña debe tener al menos 6 caracteres"
        })

    existing = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == email)
    ).first()
    if existing:
        return templates.TemplateResponse("register.html", {
            "request": request, "msg": "El usuario o el correo ya existen"
        })

    user = models.User(
        username=username, email=email,
        hashed_password=pwd_context.hash(password),
        whatsapp=whatsapp
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session_token = str(uuid.uuid4())
    sessions[session_token] = user.id
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token)
    return response


@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request, "msg": "Credenciales incorrectas"
        })

    session_token = str(uuid.uuid4())
    sessions[session_token] = user.id
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token)
    return response


@router.get("/logout")
def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token and session_token in sessions:
        del sessions[session_token]
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_token")
    return response
