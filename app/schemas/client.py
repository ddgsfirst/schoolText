"""
클라이언트 API 응답 스키마

클라이언트가 업로드한 생기부 데이터 조회에 사용되는 Pydantic 모델입니다.
"""
from pydantic import BaseModel


class UserCareerHopeOut(BaseModel):
    id: int
    grade: int
    hope: str | None

    class Config:
        from_attributes = True


class UserActivityOut(BaseModel):
    """창체 활동 응답 (원문 + AI 평가)"""
    id: int
    category: str
    grade: int
    career_hope: str | None
    original_text: str | None
    evaluation: str | None      # AI가 생성 (초기에는 비어있음)
    reason: str | None

    class Config:
        from_attributes = True


class UserSubjectOut(BaseModel):
    """세특 응답 (원문 + AI 평가)"""
    id: int
    grade: int
    subject_name: str
    original_text: str | None
    evaluation: str | None
    reason: str | None

    class Config:
        from_attributes = True


class UserBehaviorOut(BaseModel):
    """행특 응답 (원문 + AI 평가)"""
    id: int
    grade: int
    original_text: str | None
    evaluation: str | None
    reason: str | None

    class Config:
        from_attributes = True


class UserStudentOut(BaseModel):
    """클라이언트 학생 기본 응답"""
    id: int
    name: str
    school: str | None
    department: str | None
    graduation_year: int | None
    source_file: str | None

    class Config:
        from_attributes = True


class UserStudentDetail(UserStudentOut):
    """클라이언트 학생 상세 응답"""
    career_hopes: list[UserCareerHopeOut] = []
    activities: list[UserActivityOut] = []
    subjects: list[UserSubjectOut] = []
    behaviors: list[UserBehaviorOut] = []


class UploadResult(BaseModel):
    """PDF 업로드 결과"""
    filename: str
    student_name: str | None = None
    student_id: int | None = None
    success: bool
    message: str
