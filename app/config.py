"""
공도 서비스 환경 설정

환경변수 또는 .env 파일에서 설정을 로드합니다.
- REF_DATABASE_URL: 레퍼런스 DB (생기부 원문 + testone 평가)
- USER_DATABASE_URL: 사용자 DB (업로드된 생기부 + AI 평가)
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── 데이터베이스 ──
    # 레퍼런스 DB: 사전 등록된 생기부 원문 + 평가 데이터
    REF_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/reference"
    # 클라이언트 DB: 클라이언트가 업로드한 생기부 + AI 생성 평가
    CLIENT_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/client"

    # ── 파일 경로 ──
    # 레퍼런스 데이터 디렉토리 (YAML + PDF 업로드 저장)
    DATA_DIR: str = "./data"

    # 레거시: 기존 testone 디렉토리 (호환성 유지)
    TESTONE_DIR: str = "./testone"
    PDF_DIR: str = "."

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
