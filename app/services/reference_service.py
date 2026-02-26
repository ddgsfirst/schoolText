"""
레퍼런스 데이터 저장 서비스

생기부 PDF 원문과 YAML 평가 데이터를 레퍼런스 DB(reference)에 저장합니다.
PDF와 YAML은 같은 파일명(s1.pdf ↔ s1.yaml)으로 대응됩니다.
PDF가 없는 경우 YAML만 저장하며, original_text 컬럼은 비워둡니다.
"""
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.reference import (
    RefStudent, RefCareerHope, RefActivity, RefSubject, RefBehavior,
)
from app.parser.yaml_parser import parse_yaml
from app.parser.pdf_parser import parse_pdf


def _pdf_경로_찾기(yaml_filename: str) -> Path | None:
    """
    YAML 파일명에 대응하는 PDF 파일을 찾습니다.
    예: 's1.yaml' → 'data/pdf/s1.pdf'
    """
    stem = Path(yaml_filename).stem  # 'sX'

    data_pdf = Path(settings.DATA_DIR) / "pdf" / f"{stem}.pdf"
    if data_pdf.exists():
        return data_pdf

    return None


def _원문_인덱스_생성(pdf_data: dict | None) -> dict:
    """
    PDF 파싱 결과를 (category, grade) 또는 (subject_name, grade) 키로 인덱싱합니다.
    YAML 평가 데이터와 매칭할 때 빠르게 조회하기 위함입니다.
    """
    인덱스 = {
        "activities": {},   # (category, grade) → original_text
        "subjects": {},     # (subject_name, grade) → original_text
        "behaviors": {},    # grade → original_text
    }

    if not pdf_data:
        return 인덱스

    # 창체: 같은 (category, grade)의 여러 항목을 합쳐서 저장
    # 예: 자율활동 grade=1 가 비공개 항목과 실제 내용 항목으로 나뉠 수 있음
    # 비공개(None)는 실제 내용이 있을 때 무시하고, 없을 때만 None으로 저장
    activities_merged: dict[tuple, list[str]] = {}  # (category, grade) → [text1, text2]
    for item in pdf_data.get("activities", []):
        key = (item["category"], item["grade"])
        text = item.get("original_text") or ""
        if text:
            activities_merged.setdefault(key, []).append(text)
        else:
            # 실제 내용이 없는 항목도 키를 등록해야 나중에 빈 키 처리 가능
            activities_merged.setdefault(key, [])

    for key, texts in activities_merged.items():
        인덱스["activities"][key] = "\n".join(texts) if texts else None

    # 세특: 같은 (과목명, 학년)의 1학기/2학기 내용을 합쳐서 저장
    # PDF에서는 (1학기)국어: 내용1 / (2학기)국어: 내용2 로 분리되지만
    # YAML에서는 과목명 단위로 하나의 항목으로 관리됨
    subjects_merged: dict[tuple, list[str]] = {}  # (subject_name, grade) → [text1, text2]
    for item in pdf_data.get("subjects", []):
        key = (item["subject_name"], item["grade"])
        text = item.get("original_text") or ""
        if text:
            subjects_merged.setdefault(key, []).append(text)

    for key, texts in subjects_merged.items():
        인덱스["subjects"][key] = "\n".join(texts)  # 1학기 + 2학기 합침

    for item in pdf_data.get("behaviors", []):
        인덱스["behaviors"][item["grade"]] = item["original_text"]

    return 인덱스


def 레퍼런스_저장(db: Session, yaml_filepath: Path) -> RefStudent:
    """
    YAML 파일(+ 대응 PDF)을 읽어 레퍼런스 DB에 저장합니다.

    Args:
        db:            레퍼런스 DB 세션
        yaml_filepath: 레퍼런스 YAML 파일 경로

    Returns:
        저장된 RefStudent 인스턴스
    """
    # ── YAML 파싱 ──
    yaml_data = parse_yaml(yaml_filepath)

    # ── PDF 파싱 (없으면 None) ──
    pdf_path = _pdf_경로_찾기(yaml_filepath.name)
    pdf_data = None
    source_pdf = None
    if pdf_path:
        try:
            pdf_data = parse_pdf(pdf_path)
            source_pdf = pdf_path.name
        except ValueError as e:
            # 이미지 기반 PDF 등 파싱 불가 시 경고 출력 후 계속
            print(f"  ⚠ PDF 파싱 건너뜀 ({pdf_path.name}): {e}")

    # PDF 원문 인덱스 생성
    원문_인덱스 = _원문_인덱스_생성(pdf_data)

    # ── 기존 데이터 삭제 (중복 방지) ──
    info = yaml_data["student"]
    existing = db.query(RefStudent).filter(
        RefStudent.name == info["name"],
        RefStudent.source_yaml == yaml_data["source_yaml"],
    ).first()
    if existing:
        db.delete(existing)
        db.flush()

    # ── 학생 저장 ──
    student = RefStudent(
        name=info["name"],
        school=info["school"],
        department=info["department"],
        graduation_year=info["graduation_year"],
        source_pdf=source_pdf,
        source_yaml=yaml_data["source_yaml"],
    )
    db.add(student)
    db.flush()  # ID 확보

    # ── 희망분야 저장 ──
    for ch in yaml_data.get("career_hopes", []):
        db.add(RefCareerHope(
            student_id=student.id,
            grade=ch["grade"],
            hope=ch["hope"],
        ))

    # ── 창체 저장 (원문 + 평가 매칭) ──
    for ae in yaml_data.get("activities", []):
        original_text = 원문_인덱스["activities"].get((ae["category"], ae["grade"]))
        db.add(RefActivity(
            student_id=student.id,
            category=ae["category"],
            grade=ae["grade"],
            career_hope=ae.get("career_hope"),
            original_text=original_text,   # PDF 원문 (없으면 None)
            evaluation=ae.get("evaluation", ""),
            reason=ae.get("reason", ""),
        ))

    # ── 세특 저장 (원문 + 평가 매칭) ──
    for se in yaml_data.get("subjects", []):
        original_text = 원문_인덱스["subjects"].get((se["subject_name"], se["grade"]))
        db.add(RefSubject(
            student_id=student.id,
            grade=se["grade"],
            subject_name=se["subject_name"],
            original_text=original_text,
            evaluation=se.get("evaluation", ""),
            reason=se.get("reason", ""),
        ))

    # ── 행특 저장 (원문 + 평가 매칭) ──
    for be in yaml_data.get("behaviors", []):
        original_text = 원문_인덱스["behaviors"].get(be["grade"])
        db.add(RefBehavior(
            student_id=student.id,
            grade=be["grade"],
            original_text=original_text,
            evaluation=be.get("evaluation", ""),
            reason=be.get("reason", ""),
        ))

    db.commit()
    db.refresh(student)
    return student
