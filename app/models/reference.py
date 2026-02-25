"""
레퍼런스 DB 모델

사전 등록된 생기부 원문과 testone 평가 데이터를 함께 저장합니다.
각 테이블에 original_text(생기부 원문)와 evaluation/reason(평가 데이터)이 공존합니다.

테이블 구조:
    ref_students      → 학생 기본정보
    ref_career_hopes   → 학년별 희망분야
    ref_activities     → 창체 (원문 + 평가)
    ref_subjects       → 세특 (원문 + 평가)
    ref_behaviors      → 행특 (원문 + 평가)
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import RefBase


class RefStudent(RefBase):
    """레퍼런스 학생 기본 정보"""
    __tablename__ = "ref_students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, comment="학생 성명")
    school = Column(String(100), comment="학교명")
    department = Column(String(100), comment="학과명")
    graduation_year = Column(Integer, comment="졸업연도")
    source_pdf = Column(String(255), comment="원본 PDF 파일명")
    source_yaml = Column(String(255), comment="평가 YAML 파일명")

    # 관계 설정 (학생 삭제 시 하위 데이터도 함께 삭제)
    career_hopes = relationship("RefCareerHope", back_populates="student", cascade="all, delete-orphan")
    activities = relationship("RefActivity", back_populates="student", cascade="all, delete-orphan")
    subjects = relationship("RefSubject", back_populates="student", cascade="all, delete-orphan")
    behaviors = relationship("RefBehavior", back_populates="student", cascade="all, delete-orphan")


class RefCareerHope(RefBase):
    """레퍼런스 학년별 희망분야"""
    __tablename__ = "ref_career_hopes"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("ref_students.id", ondelete="CASCADE"), nullable=False)
    grade = Column(Integer, nullable=False, comment="학년 (1, 2, 3)")
    hope = Column(Text, comment="희망분야")

    student = relationship("RefStudent", back_populates="career_hopes")


class RefActivity(RefBase):
    """
    레퍼런스 창의적 체험활동상황

    original_text: PDF에서 추출한 생기부 원문
    evaluation:    testone YAML의 평가내용
    reason:        testone YAML의 이유
    """
    __tablename__ = "ref_activities"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("ref_students.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(50), nullable=False, comment="활동 유형 (자율활동/동아리활동/진로활동)")
    grade = Column(Integer, nullable=False, comment="학년")
    career_hope = Column(Text, comment="진로활동의 희망분야")

    # 생기부 원문 (PDF에서 추출)
    original_text = Column(Text, comment="생기부 원문 텍스트")
    # 평가 데이터 (testone YAML에서 로드)
    evaluation = Column(Text, comment="평가내용")
    reason = Column(Text, comment="이유")

    student = relationship("RefStudent", back_populates="activities")


class RefSubject(RefBase):
    """
    레퍼런스 세부능력 및 특기사항

    original_text: PDF에서 추출한 세특 원문
    evaluation:    testone YAML의 평가내용
    reason:        testone YAML의 이유
    """
    __tablename__ = "ref_subjects"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("ref_students.id", ondelete="CASCADE"), nullable=False)
    grade = Column(Integer, nullable=False, comment="학년")
    subject_name = Column(String(200), nullable=False, comment="과목명")

    # 생기부 원문 (PDF에서 추출)
    original_text = Column(Text, comment="세특 원문 텍스트")
    # 평가 데이터 (testone YAML에서 로드)
    evaluation = Column(Text, comment="평가내용")
    reason = Column(Text, comment="이유")

    student = relationship("RefStudent", back_populates="subjects")


class RefBehavior(RefBase):
    """
    레퍼런스 행동특성 및 종합의견

    original_text: PDF에서 추출한 행특 원문
    evaluation:    testone YAML의 평가내용
    reason:        testone YAML의 이유
    """
    __tablename__ = "ref_behaviors"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("ref_students.id", ondelete="CASCADE"), nullable=False)
    grade = Column(Integer, nullable=False, comment="학년")

    # 생기부 원문 (PDF에서 추출)
    original_text = Column(Text, comment="행특 원문 텍스트")
    # 평가 데이터 (testone YAML에서 로드)
    evaluation = Column(Text, comment="평가내용")
    reason = Column(Text, comment="이유")

    student = relationship("RefStudent", back_populates="behaviors")
