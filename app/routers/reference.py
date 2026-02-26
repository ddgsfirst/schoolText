"""
레퍼런스 API 라우터

레퍼런스 생기부(PDF 원문 + 평가)를 reference DB에 로드하고 조회하는 엔드포인트입니다.

엔드포인트:
    # 파일 업로드
    POST /api/ref/upload/batch        - data/ 폴더 레퍼런스 일괄 로드
    POST /api/ref/upload/yaml         - 단일 YAML 파일 업로드
    POST /api/ref/upload/pdf          - PDF 업로드 (파일명 기반 학생 매칭)

    # 조회
    GET  /api/ref/students            - 레퍼런스 학생 목록
    GET  /api/ref/students/{id}       - 레퍼런스 학생 상세 (원문 + 평가 포함)
    DELETE /api/ref/students/{id}     - 레퍼런스 학생 삭제
"""
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from app.database import get_ref_db
from app.config import settings
from app.models.reference import RefStudent, RefActivity, RefSubject, RefBehavior
from app.schemas.reference import (
    RefStudentOut, RefStudentDetail, LoadResult, BatchLoadResult,
)
from app.services.reference_service import 레퍼런스_저장
from app.parser.yaml_parser import parse_yaml
from app.parser.pdf_parser import parse_pdf

router = APIRouter(prefix="/api/ref", tags=["레퍼런스"])


def _data_yaml_dir() -> Path:
    """data/yaml 디렉토리 경로"""
    return Path(settings.DATA_DIR) / "yaml"


def _data_pdf_dir() -> Path:
    """data/pdf 디렉토리 경로"""
    return Path(settings.DATA_DIR) / "pdf"


# ══════════════════════════════════════════════
# 파일 업로드
# ══════════════════════════════════════════════

@router.post("/upload/batch", response_model=BatchLoadResult, summary="레퍼런스 일괄 로드")
def upload_batch(db: Session = Depends(get_ref_db)):
    """
    서버의 data/ 폴더에서 레퍼런스 파일을 일괄 로드합니다.

    - data/yaml/ 의 모든 YAML 파일을 순서대로 파싱하여 DB에 저장
    - data/pdf/ 에 같은 파일명의 PDF가 있으면 원문도 함께 저장
    - 기존 동일 학생 데이터는 덮어쓰기
    """
    yaml_dir = _data_yaml_dir()
    if not yaml_dir.exists():
        raise HTTPException(status_code=404, detail=f"디렉토리를 찾을 수 없습니다: {yaml_dir}")

    yaml_files = sorted(yaml_dir.glob("*.yaml")) + sorted(yaml_dir.glob("*.yml"))
    if not yaml_files:
        raise HTTPException(status_code=404, detail="data/yaml/ 에 YAML 파일이 없습니다.")

    results = []
    for yaml_file in yaml_files:
        try:
            student = 레퍼런스_저장(db, yaml_file)
            has_pdf = student.source_pdf is not None
            results.append(LoadResult(
                filename=yaml_file.name,
                student_name=student.name,
                student_id=student.id,
                success=True,
                message=f"'{student.name}' 저장 완료" + (" (PDF 원문 포함)" if has_pdf else " (YAML만)"),
            ))
        except Exception as e:
            db.rollback()
            results.append(LoadResult(
                filename=yaml_file.name,
                success=False,
                message=f"오류: {str(e)}",
            ))

    success_count = sum(1 for r in results if r.success)
    return BatchLoadResult(
        results=results,
        total=len(results),
        success_count=success_count,
        fail_count=len(results) - success_count,
    )


@router.post("/upload/yaml", response_model=LoadResult, summary="레퍼런스 YAML 업로드")
def upload_yaml(
    file: UploadFile = File(..., description="평가 YAML 파일 (.yaml)"),
    db: Session = Depends(get_ref_db),
):
    """
    레퍼런스 YAML 파일을 업로드하고 DB에 저장합니다.

    - data/yaml/ 에 저장 후 파싱
    - data/pdf/ 에 같은 파일명의 PDF가 있으면 원문도 함께 저장
    - 기존 동일 학생 데이터는 덮어쓰기
    """
    if not file.filename.lower().endswith((".yaml", ".yml")):
        raise HTTPException(status_code=400, detail="YAML 파일(.yaml, .yml)만 업로드 가능합니다.")

    # data/yaml/ 에 저장
    save_path = _data_yaml_dir() / file.filename
    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 저장 실패: {e}")

    try:
        student = 레퍼런스_저장(db, save_path)
        has_pdf = student.source_pdf is not None
        return LoadResult(
            filename=file.filename,
            student_name=student.name,
            student_id=student.id,
            success=True,
            message=f"'{student.name}' 레퍼런스 저장 완료" + (" (PDF 원문 포함)" if has_pdf else " (YAML만)"),
        )
    except Exception as e:
        db.rollback()
        return LoadResult(filename=file.filename, success=False, message=f"오류: {str(e)}")


@router.post("/upload/pdf", response_model=LoadResult, summary="레퍼런스 PDF 업로드")
def upload_pdf(
    file: UploadFile = File(..., description="생기부 PDF 파일 (.pdf)"),
    db: Session = Depends(get_ref_db),
):
    """
    레퍼런스 PDF를 업로드하고 파일명 기준으로 학생을 매칭합니다.

    - data/pdf/ 에 저장 후 파싱
    - 파일명 stem으로 기존 학생 매칭 (s1.pdf → s1.yaml 학생)
    - 매칭 성공 시 original_text 업데이트, 실패 시 새 학생 생성
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    # data/pdf/ 에 저장
    save_path = _data_pdf_dir() / file.filename
    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 저장 실패: {e}")

    # PDF 파싱
    try:
        pdf_data = parse_pdf(save_path)
    except ValueError as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"PDF 파싱 오류: {e}")

    # 파일명 stem으로 기존 학생 매칭 (s1.pdf → s1)
    stem = Path(file.filename).stem
    student = db.query(RefStudent).filter(
        RefStudent.source_yaml.like(f"{stem}.%"),
    ).first()

    if student:
        # ── 기존 학생에 원문 매칭 업데이트 ──
        for pdf_item in pdf_data.get("activities", []):
            db_item = db.query(RefActivity).filter(
                RefActivity.student_id == student.id,
                RefActivity.category == pdf_item["category"],
                RefActivity.grade == pdf_item["grade"],
            ).first()
            if db_item:
                db_item.original_text = pdf_item.get("original_text")

        for pdf_item in pdf_data.get("subjects", []):
            db_item = db.query(RefSubject).filter(
                RefSubject.student_id == student.id,
                RefSubject.grade == pdf_item["grade"],
                RefSubject.subject_name == pdf_item["subject_name"],
            ).first()
            if db_item:
                db_item.original_text = pdf_item.get("original_text")

        for pdf_item in pdf_data.get("behaviors", []):
            db_item = db.query(RefBehavior).filter(
                RefBehavior.student_id == student.id,
                RefBehavior.grade == pdf_item["grade"],
            ).first()
            if db_item:
                db_item.original_text = pdf_item.get("original_text")

        student.source_pdf = file.filename
        db.commit()

        활동수 = len(pdf_data.get("activities", []))
        세특수 = len(pdf_data.get("subjects", []))
        행특수 = len(pdf_data.get("behaviors", []))
        message = f"'{student.name}' 학생에 PDF 원문 매칭 완료 — 창체 {활동수}개, 세특 {세특수}개, 행특 {행특수}개"
    else:
        # ── 새 학생 생성 (원문만, 평가 없음) ──
        student_name = pdf_data.get("student_name") or "미확인"
        student = RefStudent(
            name=student_name,
            source_pdf=file.filename,
        )
        db.add(student)
        db.flush()

        for item in pdf_data.get("activities", []):
            db.add(RefActivity(
                student_id=student.id,
                category=item["category"],
                grade=item["grade"],
                career_hope=item.get("career_hope"),
                original_text=item.get("original_text"),
            ))

        for item in pdf_data.get("subjects", []):
            db.add(RefSubject(
                student_id=student.id,
                grade=item["grade"],
                subject_name=item["subject_name"],
                original_text=item.get("original_text"),
            ))

        for item in pdf_data.get("behaviors", []):
            db.add(RefBehavior(
                student_id=student.id,
                grade=item["grade"],
                original_text=item.get("original_text"),
            ))

        db.commit()
        message = f"새 학생 '{student.name}' 생성 완료 (PDF 원문만 — 같은 stem의 YAML을 업로드하면 평가가 추가됩니다)"

    return LoadResult(
        filename=file.filename,
        student_name=student.name,
        student_id=student.id,
        success=True,
        message=message,
    )


# ══════════════════════════════════════════════
# 조회 / 삭제
# ══════════════════════════════════════════════

@router.get("/students", response_model=list[RefStudentOut], summary="레퍼런스 학생 목록 조회")
def list_students(db: Session = Depends(get_ref_db)):
    """레퍼런스 DB의 전체 학생 목록을 반환합니다."""
    return db.query(RefStudent).all()


@router.get("/students/{student_id}", response_model=RefStudentDetail, summary="레퍼런스 학생 상세 조회")
def get_student(student_id: int, db: Session = Depends(get_ref_db)):
    """
    특정 학생의 전체 데이터를 반환합니다.

    - 창체/세특/행특 항목에 생기부 원문과 평가가 함께 포함
    """
    student = db.query(RefStudent).options(
        joinedload(RefStudent.career_hopes),
        joinedload(RefStudent.activities),
        joinedload(RefStudent.subjects),
        joinedload(RefStudent.behaviors),
    ).filter(RefStudent.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="학생을 찾을 수 없습니다.")
    return student


@router.delete("/students/{student_id}", summary="레퍼런스 학생 삭제")
def delete_student(student_id: int, db: Session = Depends(get_ref_db)):
    """학생과 관련된 모든 레퍼런스 데이터를 삭제합니다."""
    student = db.query(RefStudent).filter(RefStudent.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="학생을 찾을 수 없습니다.")
    name = student.name
    db.delete(student)
    db.commit()
    return {"message": f"'{name}' 학생의 레퍼런스 데이터가 삭제되었습니다."}
