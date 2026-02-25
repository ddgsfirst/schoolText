"""
공도 FastAPI 서버 진입점

생기부 평가 데이터 API 서버입니다.
레퍼런스 DB(gongdo_ref)와 사용자 DB(gongdo)를 이중으로 관리합니다.

실행 방법:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API 문서:
    http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import ref_engine, user_engine, RefBase, UserBase
from app.models import reference, client  # 테이블 생성을 위해 모델 임포트 필요
from app.routers import reference as ref_router, client as client_router

# ── 테이블 자동 생성 ──
# 서버 시작 시 각 DB에 테이블이 없으면 자동으로 생성합니다.
RefBase.metadata.create_all(bind=ref_engine)    # gongdo_ref 테이블 생성
UserBase.metadata.create_all(bind=user_engine)  # gongdo 테이블 생성

# ── FastAPI 앱 초기화 ──
app = FastAPI(
    title="등대 텍스트 처리 API",
    description="""
## 등대 텍스트 처리 API

### 레퍼런스 (`/api/ref/`)
- 사전 등록된 생기부 원문 + 평가 데이터 관리
- 레퍼런스 DB(**reference**)에 저장

### 클라이언트 (`/api/client/`)
- 클라이언트가 업로드한 생기부 PDF 관리
- AI 평가 결과를 클라이언트 DB(**client**)에 저장
    """,
    version="2.0.0",
)

# ── CORS 설정 ──
# 공동 작업 시 프론트엔드 도메인을 allow_origins에 추가하세요.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── data 디렉토리 자동 생성 ──
from pathlib import Path
from app.config import settings
_data_dir = Path(settings.DATA_DIR)
(_data_dir / "yaml").mkdir(parents=True, exist_ok=True)
(_data_dir / "pdf").mkdir(parents=True, exist_ok=True)

# ── 라우터 등록 ──
app.include_router(ref_router.router)
app.include_router(client_router.router)


@app.get("/", tags=["상태 확인"])
def root():
    """서버 기본 정보를 반환합니다."""
    return {
        "service": "공도 생기부 평가 API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "레퍼런스": "/api/ref",
            "사용자": "/api/user",
        }
    }


@app.get("/health", tags=["상태 확인"])
def health():
    """서버 헬스체크 엔드포인트입니다."""
    return {"status": "ok"}


# ── 디버그 엔드포인트 (개발용) ──
from fastapi import UploadFile, File
import tempfile, os

@app.post("/debug/raw-text", tags=["디버그"])
async def debug_raw_text(file: UploadFile = File(...)):
    """PDF에서 pdfplumber가 추출하는 원본 텍스트를 페이지별로 반환합니다."""
    try:
        import pdfplumber
    except ImportError:
        return {"error": "pdfplumber 미설치"}

    suffix = os.path.splitext(file.filename or "upload.pdf")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        pages_out = []
        with pdfplumber.open(tmp_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                tables_out = []
                for ti, table in enumerate(tables):
                    rows_out = []
                    for ri, row in enumerate(table or []):
                        cells = [str(c or "") for c in row]
                        rows_out.append({"row": ri, "cells": cells, "cell_lengths": [len(c) for c in cells]})
                    tables_out.append({"table_index": ti, "rows": rows_out})
                pages_out.append({"page": i + 1, "text": text, "tables": tables_out})
        return {"pages": pages_out}
    finally:
        os.unlink(tmp_path)
