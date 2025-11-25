from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# --- CONFIGURACIÓN CONEXIÓN ---
# Conexión a la base de datos 'pedidos_beta'
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://admin_beta:P3didos_2025!@localhost/pedidos_beta"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- TABLAS ---
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    price = Column(Float)
    estatus = Column(String(50))
    user = Column(Integer)

class Pedido(Base):
    __tablename__ = "pedidos"
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(50))
    estatus = Column(String(50), default="pendiente")
    user = Column(Integer)
    type = Column(String(50))
    comentary = Column(String(255))

    items = relationship("ProductsPedidos", back_populates="pedido")
# En models.py

class InstanceUser(Base):
    __tablename__ = "instance_user"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255)) # Longitud típica para URLs
    iduser = Column(Integer)  # El ID del usuario asociado

    
class ProductsPedidos(Base):
    __tablename__ = "products_pedidos"
    id = Column(Integer, primary_key=True, index=True)
    idProducts = Column(Integer, ForeignKey("products.id"))
    idPedido = Column(Integer, ForeignKey("pedidos.id"))
    
    pedido = relationship("Pedido", back_populates="items")
    product = relationship("Product")

# Dependencia para obtener la DB en cada petición
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
