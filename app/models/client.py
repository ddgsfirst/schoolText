"""
클라이언트 DB 모델

클라이언트가 업로드한 생기부 PDF의 원문과 AI가 생성한 평가를 저장합니다.
레퍼런스 DB와 동일한 구조이지만 별도 DB에 저장됩니다.

테이블 구조:
    students       → 학생 기본정보
    career_hopes   → 학년별 희망분야
    activities     → 창체 (원문 + AI 평가)
    subjects       → 세특 (원문 + AI 평가)
    behaviors      → 행특 (원문 + AI 평가)
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import UserBase


class UserStudent(UserBase):
    """클라이언트 업로드 학생 기본 정보"""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, comment="학생 성명")
    school = Column(String(100), comment="학교명")
    department = Column(String(100), comment="학과명")
    graduation_year = Column(Integer, comment="졸업연도")
    source_file = Column(String(255), comment="업로드된 PDF 파일명")

    # 관계 설정
    career_hopes = relationship("UserCareerHope", back_populates="student", cascade="all, delete-orphan")
    activities = relationship("UserActivity", back_populates="student", cascade="all, delete-orphan")
    subjects = relationship("UserSubject", back_populates="student", cascade="all, delete-orphan")
    behaviors = relationship("UserBehavior", back_populates="student", cascade="all, delete-orphan")


class UserCareerHope(UserBase):
    """클라이언트 학년별 희망분야"""
    __tablename__ = "career_hopes"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    grade = Column(Integer, nullable=False, comment="학년")
    hope = Column(Text, comment="희망분야")

    student = relationship("UserStudent", back_populates="career_hopes")


class UserActivity(UserBase):
    """
    클라이언트 창의적 체험활동상황

    original_text: PDF에서 추출한 생기부 원문
    evaluation:    AI가 생성한 평가내용
    reason:        AI가 생성한 이유
    """
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(50), nullable=False, comment="활동 유형")
    grade = Column(Integer, nullable=False, comment="학년")
    career_hope = Column(Text, comment="진로활동의 희망분야")

    # 생기부 원문
    original_text = Column(Text, comment="생기부 원문")
    # AI 평가 결과 (나중에 AI 서비스에서 채워짐)
    evaluation = Column(Text, comment="AI 평가내용")
    reason = Column(Text, comment="AI 평가 이유")

    student = relationship("UserStudent", back_populates="activities")


class UserSubject(UserBase):
    """클라이언트 세부능력 및 특기사항"""
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    grade = Column(Integer, nullable=False, comment="학년")
    subject_name = Column(String(200), nullable=False, comment="과목명")

    original_text = Column(Text, comment="세특 원문")
    evaluation = Column(Text, comment="AI 평가내용")
    reason = Column(Text, comment="AI 평가 이유")

    student = relationship("UserStudent", back_populates="subjects")


class UserBehavior(UserBase):
    """클라이언트 행동특성 및 종합의견"""
    __tablename__ = "behaviors"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    grade = Column(Integer, nullable=False, comment="학년")

    original_text = Column(Text, comment="행특 원문")
    evaluation = Column(Text, comment="AI 평가내용")
    reason = Column(Text, comment="AI 평가 이유")

    student = relationship("UserStudent", back_populates="behaviors")
