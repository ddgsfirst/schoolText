"""
이중 데이터베이스 엔진 및 세션 관리

- ref_engine / get_ref_db(): 레퍼런스 DB (reference)
- client_engine / get_client_db(): 클라이언트 DB (client)

모든 연결에 UTF-8 인코딩을 강제 적용합니다 (SQL_ASCII 서버 대응).
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# ────────────────────────────────────────
# 공통 Base 클래스
# ────────────────────────────────────────
RefBase = declarative_base()
ClientBase = declarative_base()


def _apply_utf8_encoding(engine):
    """SQL_ASCII 서버에서도 한글이 정상 처리되도록 UTF-8 인코딩을 강제 적용합니다."""
    @event.listens_for(engine, "connect")
    def set_client_encoding(dbapi_conn, connection_record):
        dbapi_conn.set_client_encoding("UTF8")


# ────────────────────────────────────────
# 레퍼런스 DB (gongdo_ref)
# ────────────────────────────────────────
ref_engine = create_engine(settings.REF_DATABASE_URL, echo=False)
_apply_utf8_encoding(ref_engine)
RefSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ref_engine)


def get_ref_db():
    """레퍼런스 DB 세션을 제공하는 FastAPI 의존성"""
    db = RefSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ────────────────────────────────────────
# 클라이언트 DB (client)
# ────────────────────────────────────────
client_engine = create_engine(settings.CLIENT_DATABASE_URL, echo=False)
_apply_utf8_encoding(client_engine)
ClientSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=client_engine)


def get_client_db():
    """클라이언트 DB 세션을 제공하는 FastAPI 의존성"""
    db = ClientSessionLocal()
    try:
        yield db
    finally:
        db.close()
