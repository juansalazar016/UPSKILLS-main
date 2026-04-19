# models.py
# Define las tablas de la base de datos como clases Python (ORM SQLAlchemy).
# Tres modelos: User, Product, Rating.
# Las relaciones usan cascade="all, delete-orphan" para que al eliminar
# un usuario se borren en cadena sus productos y todas las valoraciones.

from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


# ─── Tabla: users ────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String, unique=True, index=True, nullable=False)
    email           = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)  # bcrypt via passlib
    whatsapp        = Column(String, nullable=True)

    # cascade: eliminar usuario → elimina sus productos y sus valoraciones dadas
    products = relationship("Product", back_populates="owner", cascade="all, delete-orphan")
    ratings  = relationship("Rating",  back_populates="user",  cascade="all, delete-orphan")


# ─── Tabla: products ─────────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    price       = Column(Float, nullable=False)
    stock       = Column(Integer, nullable=False)
    # Puede contener 1 a 3 nombres de archivo separados por coma
    # Ejemplo: "uuid1_img.jpg,uuid2_img.jpg,uuid3_img.jpg"
    image       = Column(String, nullable=False)
    # Enlace externo opcional (tienda, red social, etc.)
    # Columna agregada con: ALTER TABLE products ADD COLUMN link VARCHAR;
    link        = Column(String, nullable=True)
    owner_id    = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner   = relationship("User",   back_populates="products")
    # cascade: eliminar producto → elimina sus valoraciones
    ratings = relationship("Rating", back_populates="product", cascade="all, delete-orphan")


# ─── Tabla: ratings ──────────────────────────────────────────────────────────
class Rating(Base):
    __tablename__ = "ratings"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"),    nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    user    = relationship("User",    back_populates="ratings")
    product = relationship("Product", back_populates="ratings")

    # Garantiza que un usuario no pueda valorar el mismo producto dos veces
    __table_args__ = (UniqueConstraint('user_id', 'product_id', name='_user_product_uc'),)
