# main.py
# Punto de entrada principal de la aplicación FastAPI.
# Define todas las rutas HTTP, la lógica de negocio y el manejo de sesiones.
# Arquitectura: request → ruta → consulta DB via SQLAlchemy → respuesta Jinja2

from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
from passlib.context import CryptContext
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import shutil
from typing import Optional
import uuid
import os

# Crea las tablas en la DB si no existen. No migra columnas ya existentes.
# Para agregar columnas nuevas usar ALTER TABLE en pgAdmin.
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# ─── Templates y archivos estáticos ──────────────────────────────────────────
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Filtro personalizado Jinja2: convierte 290000.0 → "290.000" (formato COP)
def format_price(value):
    return "{:,.0f}".format(value).replace(",", ".")

templates.env.filters["price"] = format_price

# Página 404 personalizada con diseño on-brand
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: FastAPIHTTPException):
    return templates.TemplateResponse("404.html", {"request": request, "current_user": None}, status_code=404)

# ─── Utilidades de autenticación ─────────────────────────────────────────────

# Maneja el hashing y verificación de contraseñas con bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Inyección de dependencia: abre sesión DB por request y la cierra al terminar
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Sesiones en memoria: {token_uuid: user_id}
# NOTA: no persistente — se pierde al reiniciar el servidor.
# Para producción considerar JWT o sesiones en DB.
sessions = {}

# Dependencia: lee la cookie session_token y retorna el User activo o None
def get_current_user(session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if session_token and session_token in sessions:
        user_id = sessions[session_token]
        user = db.query(models.User).filter(models.User.id == user_id).first()
        return user
    return None

# Número de productos por página en listados paginados
PAGE_SIZE = 12

# ─── Módulo: Autenticación ───────────────────────────────────────────────────

# Ruta para registrar usuarios
@app.get("/register", response_class=HTMLResponse)
def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(request: Request, 
                  username: str = Form(...),
                  email: str = Form(...), 
                  password: str = Form(...), 
                  whatsapp: str = Form(...),  # Aceptar el campo whatsapp
                  db: Session = Depends(get_db)):
                  
    # Verificar si el usuario o email ya existen
    existing_user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == email)
    ).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "msg": "El usuario o el correo ya existen"})
    
    # Crear nuevo usuario
    hashed_password = pwd_context.hash(password)
    user = models.User(username=username, email=email, hashed_password=hashed_password, whatsapp=whatsapp)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Iniciar sesión automáticamente después del registro
    session_token = str(uuid.uuid4())
    sessions[session_token] = user.id
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token)
    return response

# Ruta para iniciar sesión
@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_user(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Buscar usuario por username
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "msg": "Credenciales incorrectas"})
    
    # Crear sesión
    session_token = str(uuid.uuid4())
    sessions[session_token] = user.id
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token)
    return response

# Ruta para cerrar sesión
@app.get("/logout")
def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token and session_token in sessions:
        del sessions[session_token]
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="session_token")
    return response

# Ruta principal temporal
#@app.get("/", response_class=HTMLResponse)
#def Carga_temporal(request: Request, current_user: models.User = Depends(get_current_user)):
#    return templates.TemplateResponse("base.html", {"request": request, "current_user": current_user})


# ─── Módulo: Productos ───────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def read_products(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    q: str = "",
    page: int = 1
):
    query = db.query(models.Product)
    if q:
        query = query.filter(
            models.Product.name.ilike(f"%{q}%") |
            models.Product.description.ilike(f"%{q}%")
        )

    all_products = query.all()
    products_with_ratings = [(p, len(p.ratings)) for p in all_products]
    products_with_ratings.sort(key=lambda x: x[1], reverse=True)

    total = len(products_with_ratings)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    paginated = products_with_ratings[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "products_with_ratings": paginated,
        "current_user": current_user,
        "q": q,
        "page": page,
        "total_pages": total_pages,
        "total": total
    })


# Ruta para agregar un nuevo producto
@app.get("/add_product", response_class=HTMLResponse)
def add_product_form(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("add_product.html", {
        "request": request, 
        "current_user": current_user
    })

@app.post("/add_product")
async def add_product(request: Request, name: str = Form(...), description: str = Form(...),
                      price: float = Form(...), stock: int = Form(...),
                      link: str = Form(""),
                      image1: UploadFile = File(...),
                      image2: UploadFile = File(None),
                      image3: UploadFile = File(None),
                      db: Session = Depends(get_db),
                      current_user: models.User = Depends(get_current_user)):

    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    image_dir = os.path.join("static", "images")
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    if not image1.filename:
        return templates.TemplateResponse("add_product.html", {
            "request": request, "current_user": current_user,
            "msg": "Debes subir al menos una imagen principal."
        })

    image_filenames = []
    for img in [image1, image2, image3]:
        if img and img.filename:
            filename = f"{uuid.uuid4()}_{img.filename}"
            with open(os.path.join("static", "images", filename), "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)
            image_filenames.append(filename)

    product = models.Product(
        name=name, description=description, price=price, stock=stock,
        image=",".join(image_filenames),
        link=link if link.strip() else None,
        owner_id=current_user.id
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


# Ruta para ver detalles de un producto
@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int, msg: str = "", db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Contar los votos (ratings)
    rating_count = len(product.ratings)
    
    # Verificar si el usuario actual ya ha puntuado este producto
    user_has_rated = False
    if current_user:
        existing_rating = db.query(models.Rating).filter(
            models.Rating.user_id == current_user.id, 
            models.Rating.product_id == product_id
        ).first()
        
        if existing_rating:
            user_has_rated = True
    
    return templates.TemplateResponse("product_detail.html", {
        "request": request,
        "product": product,
        "rating_count": rating_count,
        "user_has_rated": user_has_rated,
        "current_user": current_user,
        "msg": msg
    })


# Ruta para editar un producto
@app.get("/edit_product/{product_id}", response_class=HTMLResponse)
def edit_product_form(request: Request, product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    product = db.query(models.Product).filter(
        models.Product.id == product_id, 
        models.Product.owner_id == current_user.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no tienes permiso para editarlo")
    
    return templates.TemplateResponse("edit_product.html", {
        "request": request, 
        "product": product, 
        "current_user": current_user
    })

@app.post("/edit_product/{product_id}")
async def edit_product(product_id: int, request: Request, name: str = Form(...), description: str = Form(...),
                       price: float = Form(...), stock: int = Form(...),
                       link: str = Form(""),
                       image1: UploadFile = File(None),
                       image2: UploadFile = File(None),
                       image3: UploadFile = File(None),
                       db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_current_user)):

    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.owner_id == current_user.id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no tienes permiso para editarlo")

    product.name = name
    product.description = description
    product.price = price
    product.stock = stock
    product.link = link.strip() if link.strip() else None

    current_images = [i for i in product.image.split(",") if i] if product.image else []
    new_images = []

    for idx, img_upload in enumerate([image1, image2, image3]):
        if img_upload and img_upload.filename:
            if idx < len(current_images):
                old_path = os.path.join("static", "images", current_images[idx])
                if os.path.exists(old_path):
                    os.remove(old_path)
            filename = f"{uuid.uuid4()}_{img_upload.filename}"
            with open(os.path.join("static", "images", filename), "wb") as buffer:
                shutil.copyfileobj(img_upload.file, buffer)
            new_images.append(filename)
        elif idx < len(current_images):
            new_images.append(current_images[idx])

    if new_images:
        product.image = ",".join(new_images)

    db.commit()
    db.refresh(product)

    return RedirectResponse(url=f"/product/{product_id}?msg=saved", status_code=status.HTTP_302_FOUND)


# Ruta para eliminar un producto
@app.post("/delete_product/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    product = db.query(models.Product).filter(
        models.Product.id == product_id, 
        models.Product.owner_id == current_user.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no tienes permiso para eliminarlo")
    
    # Eliminar la imagen asociada
    image_path = os.path.join("static", "images", product.image)
    if os.path.exists(image_path):
        os.remove(image_path)
    
    db.delete(product)
    db.commit()
    
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


# Ruta para ver detalles del usuario (autor)
@app.get("/user/{user_id}", response_class=HTMLResponse)
def user_detail(request: Request, user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    products_with_ratings = sorted(
        [(p, len(p.ratings)) for p in user.products],
        key=lambda x: x[1], reverse=True
    )

    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user": user,
        "current_user": current_user,
        "products_with_ratings": products_with_ratings
    })


# ─── Módulo: Valoraciones ────────────────────────────────────────────────────

# Ruta para puntuar un producto
@app.post("/rate_product/{product_id}")
def rate_product(product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para puntuar un producto")
    
    # Verificar si el producto existe
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar si el usuario ya ha puntuado este producto
    existing_rating = db.query(models.Rating).filter(
        models.Rating.user_id == current_user.id, 
        models.Rating.product_id == product_id
    ).first()
    
    if existing_rating:
        raise HTTPException(status_code=400, detail="Ya has puntuado este producto")
    
    # Crear una nueva puntuación
    rating = models.Rating(user_id=current_user.id, product_id=product_id)
    db.add(rating)
    db.commit()
    db.refresh(rating)
    
    return RedirectResponse(url=f"/product/{product_id}", status_code=status.HTTP_302_FOUND)



# ─── Módulo: Usuarios (CRUD completo) ────────────────────────────────────────

# Ruta para ver mis productos
@app.get("/my_products", response_class=HTMLResponse)
def my_products(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = 1
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    all_products = db.query(models.Product).filter(models.Product.owner_id == current_user.id).all()
    products_with_ratings = [(p, len(p.ratings)) for p in all_products]
    products_with_ratings.sort(key=lambda x: x[1], reverse=True)

    total = len(products_with_ratings)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    paginated = products_with_ratings[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

    return templates.TemplateResponse("my_products.html", {
        "request": request,
        "products_with_ratings": paginated,
        "current_user": current_user,
        "page": page,
        "total_pages": total_pages,
        "total": total
    })


# Ruta para editar perfil
@app.get("/edit_profile", response_class=HTMLResponse)
def edit_profile_form(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("edit_profile.html", {"request": request, "current_user": current_user})

@app.post("/edit_profile")
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


# Ruta para eliminar cuenta
@app.post("/delete_account")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
