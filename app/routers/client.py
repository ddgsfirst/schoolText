"""
클라이언트 API 라우터

클라이언트가 자신의 생기부 PDF를 업로드하고 AI 평가 결과를 조회하는 엔드포인트입니다.

엔드포인트:
    POST /api/client/upload         - 생기부 PDF 업로드 (원문 저장, AI 평가는 추후)
    GET  /api/client/students       - 클라이언트 학생 목록
    GET  /api/client/students/{id}  - 클라이언트 학생 상세
    DELETE /api/client/students/{id} - 삭제
"""
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from app.database import get_user_db
from app.models.client import UserStudent
from app.schemas.client import UserStudentOut, UserStudentDetail, UploadResult
from app.services.client_service import 클라이언트_생기부_저장

router = APIRouter(prefix="/api/client", tags=["클라이언트"])


@router.post("/upload", response_model=UploadResult, summary="생기부 PDF 업로드")
def upload_pdf(
    file: UploadFile = File(..., description="생기부 PDF 파일 (.pdf)"),
    db: Session = Depends(get_user_db),
):
    """
    클라이언트의 생기부 PDF를 업로드하고 원문을 추출합니다.

    - 창체/세특/행특 원문을 파싱하여 DB에 저장
    - AI 평가는 추후 별도 API로 생성
    - 텍스트 기반 PDF만 지원 (이미지 기반 불가)
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    # 임시 파일에 저장 후 파싱
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        student = 클라이언트_생기부_저장(db, tmp_path, file.filename)
        return UploadResult(
            filename=file.filename,
            student_name=student.name,
            student_id=student.id,
            success=True,
            message=f"생기부 업로드 완료 (ID: {student.id}). AI 평가 대기 중입니다.",
        )
    except ValueError as e:
        # 이미지 기반 PDF 등 파싱 불가
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"저장 오류: {str(e)}")
    finally:
        tmp_path.unlink(missing_ok=True)  # 임시 파일 삭제


@router.get("/students", response_model=list[UserStudentOut], summary="클라이언트 학생 목록 조회")
def list_students(db: Session = Depends(get_user_db)):
    """업로드된 전체 학생 목록을 반환합니다."""
    return db.query(UserStudent).all()


@router.get("/students/{student_id}", response_model=UserStudentDetail, summary="클라이언트 학생 상세 조회")
def get_student(student_id: int, db: Session = Depends(get_user_db)):
    """
    특정 학생의 전체 데이터를 반환합니다.

    - AI 평가 완료 항목은 evaluation과 reason이 포함
    """
    student = db.query(UserStudent).options(
        joinedload(UserStudent.career_hopes),
        joinedload(UserStudent.activities),
        joinedload(UserStudent.subjects),
        joinedload(UserStudent.behaviors),
    ).filter(UserStudent.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="학생을 찾을 수 없습니다.")
    return student


@router.delete("/students/{student_id}", summary="클라이언트 학생 삭제")
def delete_student(student_id: int, db: Session = Depends(get_user_db)):
    """학생과 관련된 모든 클라이언트 데이터를 삭제합니다."""
    student = db.query(UserStudent).filter(UserStudent.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="학생을 찾을 수 없습니다.")
    db.delete(student)
    db.commit()
    return {"message": f"학생 데이터(ID: {student_id})가 삭제되었습니다."}
