# database.py
# Configura la conexión con PostgreSQL usando SQLAlchemy.
# Migrado desde SQLite durante sesión con Claude (Abril 2026).
# Se usa client_encoding=utf8 para evitar UnicodeDecodeError en Windows
# cuando PostgreSQL responde con mensajes en español (encoding Latin-1).

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL de conexión a PostgreSQL
DATABASE_URL = "postgresql://postgres:Superduper69@localhost:5432/UpSkillss_db?client_encoding=utf8"

# Motor de base de datos — punto de entrada de SQLAlchemy hacia la DB
engine = create_engine(DATABASE_URL)

# Fábrica de sesiones — cada request obtiene su propia sesión vía get_db()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base de la que heredan todos los modelos ORM
Base = declarative_base()
