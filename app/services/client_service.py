"""
클라이언트 生기부 저장 서비스

클라이언트가 업로드한 생기부 PDF 원문을 클라이언트 DB(client)에 저장합니다.
AI 평가(evaluation, reason)는 이 단계에서는 비워두고,
추후 AI 평가 서비스에서 채워집니다.
"""
from sqlalchemy.orm import Session

from app.models.client import (
    UserStudent, UserCareerHope, UserActivity, UserSubject, UserBehavior,
)
from app.parser.pdf_parser import parse_pdf


def 클라이언트_생기부_저장(db: Session, pdf_path, filename: str) -> UserStudent:
    """
    클라이언트가 업로드한 PDF를 파싱하여 클라이언트 DB에 저장합니다.

    Args:
        db:       클라이언트 DB 세션
        pdf_path: 저장된 PDF 파일 경로
        filename: 원본 업로드 파일명

    Returns:
        저장된 UserStudent 인스턴스

    Raises:
        ValueError: 이미지 기반 PDF 등 파싱 불가 시
    """
    # PDF 파싱
    pdf_data = parse_pdf(pdf_path)

    # 기본 정보 추출 (PDF에서는 학생 이름/학교 등을 파싱하기 어려울 수 있음)
    # 우선 파일명 기준으로 저장하고 나중에 업데이트 가능
    student = UserStudent(
        name="미확인",           # TODO: PDF personal 섹션에서 추출
        school=None,
        department=None,
        graduation_year=None,
        source_file=filename,
    )
    db.add(student)
    db.flush()

    # ── 창체 원문 저장 ──
    for ae in pdf_data.get("activities", []):
        db.add(UserActivity(
            student_id=student.id,
            category=ae["category"],
            grade=ae["grade"],
            career_hope=ae.get("career_hope"),   # 테이블 파싱에서 추출
            original_text=ae.get("original_text"),
            # AI 평가는 아직 비워둠
            evaluation=None,
            reason=None,
        ))

    # ── 세특 원문 저장 ──
    for se in pdf_data.get("subjects", []):
        db.add(UserSubject(
            student_id=student.id,
            grade=se["grade"],
            subject_name=se["subject_name"],
            original_text=se.get("original_text"),
            evaluation=None,
            reason=None,
        ))

    # ── 행특 원문 저장 ──
    for be in pdf_data.get("behaviors", []):
        db.add(UserBehavior(
            student_id=student.id,
            grade=be["grade"],
            original_text=be.get("original_text"),
            evaluation=None,
            reason=None,
        ))

    db.commit()
    db.refresh(student)
    return student
