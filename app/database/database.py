# app/database/database.py
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from cryptography.fernet import Fernet

# ==========================================
# CONFIGURACIÓN DE SEGURIDAD (ENCRIPTACIÓN)
# ==========================================
KEY_FILE = ".db_key.key"


def load_or_create_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)
    else:
        with open(KEY_FILE, "rb") as key_file:
            key = key_file.read()
    return key


cipher_suite = Fernet(load_or_create_key())


def encrypt_password(password: str) -> str:
    if not password: return ""
    return cipher_suite.encrypt(password.encode('utf-8')).decode('utf-8')


def decrypt_password(encrypted_password: str) -> str:
    if not encrypted_password: return ""
    try:
        return cipher_suite.decrypt(encrypted_password.encode('utf-8')).decode('utf-8')
    except Exception:
        return ""


# ==========================================
# MODELOS DE BASE DE DATOS
# ==========================================
Base = declarative_base()


class ProveedorCredencial(Base):
    __tablename__ = 'proveedor_credenciales'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_proveedor = Column(String(100), unique=True, nullable=False)
    usuario = Column(String(150), nullable=False)
    password_encriptado = Column(String(255), nullable=False)

    # Relación con sucursales
    sucursales = relationship("Sucursal", back_populates="proveedor", cascade="all, delete-orphan")


class Sucursal(Base):
    __tablename__ = "sucursales"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)

    # Ancla al proveedor
    proveedor_id = Column(Integer, ForeignKey("proveedor_credenciales.id"), nullable=False)
    proveedor = relationship("ProveedorCredencial", back_populates="sucursales")


class FacturaGuardada(Base):
    __tablename__ = 'facturas_guardadas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_registro = Column(DateTime, default=datetime.now)
    archivo_origen = Column(String(255))
    hoja_origen = Column(String(100), nullable=True)
    rfc_cliente = Column(String(13))
    proveedor = Column(String(100))
    metodo_pago = Column(String(5))
    forma_pago = Column(String(50))
    uso_cfdi = Column(String(5))
    es_usd = Column(Boolean, default=False)
    tipo_cambio = Column(String(20), nullable=True)
    sucursal = Column(String(100), nullable=True)
    emitir_y_enviar = Column(Boolean, default=False)
    total = Column(Float, nullable=True)
    notas_extra = Column(Text, nullable=True)
    conceptos_json = Column(Text, nullable=False)
    estado = Column(String(50), default="Pendiente")
    folio_fiscal = Column(String(100), nullable=True)
    mensaje_error = Column(Text, nullable=True)

# --- NUEVA TABLA PARA EL PARSER Y MOTOR INTERCOMPAÑÍAS ---
class CatalogoProveedor(Base):
    __tablename__ = 'catalogo_proveedores'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), unique=True, nullable=False)
    rfc = Column(String(13), nullable=True)
    alias = Column(Text, nullable=True) # Aquí guardamos: "MARTO, GRUPOMARTINEZDELATORRE"


# ==========================================
# CONEXIÓN (SQLITE LOCAL)
# ==========================================
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "facturacion_local.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_catalogo_proveedores():

    pass

def obtener_proveedores_alias():
    db = SessionLocal()
    try:
        filas = db.query(CatalogoProveedor.nombre, CatalogoProveedor.alias).all()
        return [(f.nombre, f.alias) for f in filas]
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    seed_catalogo_proveedores()

Base.metadata.create_all(bind=engine)
