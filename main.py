from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from database import engine
import models
from dependencies import templates
from routers import auth, products, users, ratings

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates.env.filters["price"] = lambda v: "{:,.0f}".format(v).replace(",", ".")

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: FastAPIHTTPException):
    return templates.TemplateResponse("404.html", {"request": request, "current_user": None}, status_code=404)

@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    return templates.TemplateResponse("500.html", {"request": request, "current_user": None}, status_code=500)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(users.router)
app.include_router(ratings.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
