"""
레퍼런스 API 응답 스키마

레퍼런스 학생 데이터 조회 및 로드 결과에 사용되는 Pydantic 모델입니다.
"""
from pydantic import BaseModel


# ── 레퍼런스 학생 기본정보 ──

class RefCareerHopeOut(BaseModel):
    """학년별 희망분야 응답"""
    id: int
    grade: int
    hope: str | None

    class Config:
        from_attributes = True


class RefActivityOut(BaseModel):
    """창체 활동 응답 (원문 + 평가)"""
    id: int
    category: str
    grade: int
    career_hope: str | None
    original_text: str | None   # 생기부 원문
    evaluation: str | None      # 평가내용
    reason: str | None          # 이유

    class Config:
        from_attributes = True


class RefSubjectOut(BaseModel):
    """세특 응답 (원문 + 평가)"""
    id: int
    grade: int
    subject_name: str
    original_text: str | None   # 세특 원문
    evaluation: str | None      # 평가내용
    reason: str | None          # 이유

    class Config:
        from_attributes = True


class RefBehaviorOut(BaseModel):
    """행특 응답 (원문 + 평가)"""
    id: int
    grade: int
    original_text: str | None   # 행특 원문
    evaluation: str | None      # 평가내용
    reason: str | None          # 이유

    class Config:
        from_attributes = True


class RefStudentOut(BaseModel):
    """레퍼런스 학생 기본 응답"""
    id: int
    name: str
    school: str | None
    department: str | None
    graduation_year: int | None
    source_pdf: str | None
    source_yaml: str | None

    class Config:
        from_attributes = True


class RefStudentDetail(RefStudentOut):
    """레퍼런스 학생 상세 응답 (하위 데이터 포함)"""
    career_hopes: list[RefCareerHopeOut] = []
    activities: list[RefActivityOut] = []
    subjects: list[RefSubjectOut] = []
    behaviors: list[RefBehaviorOut] = []


# ── 로드 결과 ──

class LoadResult(BaseModel):
    """단일 파일 로드 결과"""
    filename: str
    student_name: str | None = None
    student_id: int | None = None
    success: bool
    message: str


class BatchLoadResult(BaseModel):
    """일괄 로드 결과"""
    results: list[LoadResult]
    total: int
    success_count: int
    fail_count: int
