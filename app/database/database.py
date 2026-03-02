# app/database/database.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, Text
from sqlalchemy.orm import declarative_base, sessionmaker
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
    if not password:
        return ""
    return cipher_suite.encrypt(password.encode('utf-8')).decode('utf-8')

def decrypt_password(encrypted_password: str) -> str:
    if not encrypted_password:
        return ""
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
    sucursal_default = Column(String(100), nullable=True)

class FacturaGuardada(Base):
    """
    Guarda el estado de la factura parseada y su progreso de emisión.
    """
    __tablename__ = 'facturas_guardadas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    archivo_origen = Column(String(255))
    hoja_origen = Column(String(100), nullable=True)

    # Datos del cliente/receptor
    rfc_cliente = Column(String(13))
    proveedor = Column(String(100))

    # Datos de la factura
    metodo_pago = Column(String(5))
    forma_pago = Column(String(50))
    uso_cfdi = Column(String(5))
    es_usd = Column(Boolean, default=False)
    tipo_cambio = Column(String(20), nullable=True)

    total = Column(Float, nullable=True)
    notas_extra = Column(Text, nullable=True)

    # === NUEVAS COLUMNAS PARA EL BOT ===
    es_automatica = Column(Boolean, default=False)
    conceptos_json = Column(Text, nullable=False) # Guardaremos la lista de conceptos en JSON

    # === CONTROL DE EMISIÓN ===
    estado = Column(String(20), default="Pendiente")
    folio_fiscal = Column(String(100), nullable=True)  # UUID asignado por el SAT
    mensaje_error = Column(Text, nullable=True)

# ==========================================
# CONEXIÓN (SQLITE LOCAL)
# ==========================================
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "facturacion_local.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
