from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
import uuid
import os
import shutil
import models
from dependencies import templates, get_db, get_current_user, build_ratings_list, paginate

router = APIRouter()

ALLOWED_IMAGE_SIGNATURES = [
    b'\xff\xd8\xff',  # JPEG
    b'\x89PNG',       # PNG
    b'GIF8',          # GIF
    b'RIFF',          # WebP
    b'BM',            # BMP
]

async def is_valid_image(file: UploadFile) -> bool:
    header = await file.read(12)
    await file.seek(0)
    return any(header.startswith(sig) for sig in ALLOWED_IMAGE_SIGNATURES)


@router.get("/", response_class=HTMLResponse)
def read_products(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    q: str = "",
    page: int = 1
):
    query = db.query(models.Product).options(joinedload(models.Product.ratings))
    if q:
        query = query.filter(
            models.Product.name.ilike(f"%{q}%") |
            models.Product.description.ilike(f"%{q}%")
        )

    rated = build_ratings_list(query.all())
    paged = paginate(rated, page)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "products_with_ratings": paged["items"],
        "current_user": current_user,
        "q": q,
        "page": paged["page"],
        "total_pages": paged["total_pages"],
        "total": paged["total"],
    })


@router.get("/add_product", response_class=HTMLResponse)
def add_product_form(request: Request, current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("add_product.html", {"request": request, "current_user": current_user})


@router.post("/add_product")
async def add_product(
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    stock: int = Form(...),
    link: str = Form(""),
    image1: UploadFile = File(...),
    image2: UploadFile = File(None),
    image3: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
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

    for img in [image1, image2, image3]:
        if img and img.filename and not await is_valid_image(img):
            return templates.TemplateResponse("add_product.html", {
                "request": request, "current_user": current_user,
                "msg": f"El archivo '{img.filename}' no es una imagen válida."
            })

    image_filenames = []
    for img in [image1, image2, image3]:
        if img and img.filename:
            ext = os.path.splitext(img.filename)[1].lower() or ".jpg"
            filename = f"{uuid.uuid4()}{ext}"
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


@router.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(
    request: Request,
    product_id: int,
    msg: str = "",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    rating_count = len(product.ratings)
    avg_rating = round(sum(r.score for r in product.ratings) / rating_count, 1) if rating_count > 0 else 0

    user_has_rated = False
    user_rating_score = None
    if current_user:
        existing_rating = db.query(models.Rating).filter(
            models.Rating.user_id == current_user.id,
            models.Rating.product_id == product_id
        ).first()
        if existing_rating:
            user_has_rated = True
            user_rating_score = existing_rating.score

    return templates.TemplateResponse("product_detail.html", {
        "request": request,
        "product": product,
        "rating_count": rating_count,
        "avg_rating": avg_rating,
        "user_has_rated": user_has_rated,
        "user_rating_score": user_rating_score,
        "current_user": current_user,
        "msg": msg
    })


@router.get("/edit_product/{product_id}", response_class=HTMLResponse)
def edit_product_form(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.owner_id == current_user.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no tienes permiso para editarlo")

    return templates.TemplateResponse("edit_product.html", {
        "request": request, "product": product, "current_user": current_user
    })


@router.post("/edit_product/{product_id}")
async def edit_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    stock: int = Form(...),
    link: str = Form(""),
    image1: UploadFile = File(None),
    image2: UploadFile = File(None),
    image3: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
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

    for img in [image1, image2, image3]:
        if img and img.filename and not await is_valid_image(img):
            return templates.TemplateResponse("edit_product.html", {
                "request": request, "current_user": current_user, "product": product,
                "msg": f"El archivo '{img.filename}' no es una imagen válida."
            })

    current_images = [i.strip() for i in product.image.split(",") if i.strip()] if product.image else []
    new_images = []

    for idx, img_upload in enumerate([image1, image2, image3]):
        if img_upload and img_upload.filename:
            if idx < len(current_images):
                old_path = os.path.join("static", "images", current_images[idx])
                if os.path.exists(old_path):
                    os.remove(old_path)
            ext = os.path.splitext(img_upload.filename)[1].lower() or ".jpg"
            filename = f"{uuid.uuid4()}{ext}"
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


@router.post("/delete_product/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.owner_id == current_user.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no tienes permiso para eliminarlo")

    for img_name in [i for i in product.image.split(",") if i]:
        img_path = os.path.join("static", "images", img_name)
        if os.path.exists(img_path):
            os.remove(img_path)

    db.delete(product)
    db.commit()

    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
