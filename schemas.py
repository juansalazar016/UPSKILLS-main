# schemas.py

# Importamos Pydantic para crear esquemas de validación de datos
from pydantic import BaseModel

# Esquemas Pydantic para validar los datos al crear o editar usuarios y productos.

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    whatsapp: str

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    stock: int

class ProductEdit(BaseModel):
    name: str
    description: str
    price: float
    stock: int