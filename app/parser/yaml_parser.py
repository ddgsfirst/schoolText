"""
YAML 평가 파일 파서 (testone 디렉토리)

testone/*.yaml 파일을 읽어 창체/세특/행특 평가 데이터를 구조화합니다.
YAML 파일 구조:
    학생정보: 성명, 학교, 학과, 졸업연도, 희망분야
    창의적_체험활동상황: 자율/동아리/진로 × 학년 × 평가내용/이유
    세부능력_및_특기사항: 학년 × 과목 × 평가내용/이유
    행동특성_및_종합의견: 학년 × 평가내용/이유

'비공개' 값은 자동으로 건너뜁니다.
"""
import yaml
import re
from pathlib import Path


def _학년_파싱(key: str) -> int | None:
    """
    학년 키에서 숫자를 추출합니다.
    예: '1학년' → 1, '2학년' → 2, 숫자 1 → 1
    """
    if isinstance(key, int):
        return key
    m = re.match(r"(\d)", str(key))
    return int(m.group(1)) if m else None


def _비공개인지(value) -> bool:
    """값이 '비공개'인지 확인합니다."""
    return isinstance(value, str) and value.strip() == "비공개"


def parse_yaml(filepath: str | Path) -> dict:
    """
    testone YAML 파일을 파싱하여 구조화된 딕셔너리로 반환합니다.

    Args:
        filepath: YAML 파일 경로

    Returns:
        {
            "student":       {name, school, department, graduation_year},
            "career_hopes":  [{grade, hope}],
            "activities":    [{category, grade, career_hope, evaluation, reason}],
            "subjects":      [{grade, subject_name, evaluation, reason}],
            "behaviors":     [{grade, evaluation, reason}],
            "source_yaml":   str (파일명),
        }
    """
    filepath = Path(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    result = {
        "student": {},
        "career_hopes": [],
        "activities": [],
        "subjects": [],
        "behaviors": [],
        "source_yaml": filepath.name,
    }

    # ── 학생 기본정보 파싱 ──
    info = data.get("학생정보", {})
    result["student"] = {
        "name": info.get("성명", ""),
        "school": info.get("학교", ""),
        "department": info.get("학과", ""),
        "graduation_year": info.get("졸업연도"),
    }

    # 희망분야 (학년별)
    hopes = info.get("희망분야", {})
    if isinstance(hopes, dict):
        for key, value in hopes.items():
            grade = _학년_파싱(key)
            if grade and value and not _비공개인지(value):
                result["career_hopes"].append({
                    "grade": grade,
                    "hope": str(value),
                })

    # ── 창의적 체험활동상황 파싱 ──
    activities = data.get("창의적_체험활동상황", {})
    for category, grades_data in activities.items():
        if not isinstance(grades_data, dict):
            continue

        for grade_key, content in grades_data.items():
            grade = _학년_파싱(grade_key)
            if not grade:
                continue
            if _비공개인지(content):
                continue

            if isinstance(content, str):
                # 단순 텍스트인 경우
                result["activities"].append({
                    "category": category,
                    "grade": grade,
                    "career_hope": None,
                    "evaluation": content,
                    "reason": "",
                })
                continue

            if not isinstance(content, dict):
                continue

            evaluation = content.get("평가내용", "")
            reason = content.get("이유", "")
            career_hope = content.get("희망분야")

            if _비공개인지(evaluation):
                continue

            result["activities"].append({
                "category": category,
                "grade": grade,
                "career_hope": str(career_hope) if career_hope and not _비공개인지(career_hope) else None,
                "evaluation": str(evaluation).strip() if evaluation else "",
                "reason": str(reason).strip() if reason else "",
            })

    # ── 세부능력 및 특기사항 파싱 ──
    subjects = data.get("세부능력_및_특기사항", {})
    for grade_key, subjects_data in subjects.items():
        grade = _학년_파싱(grade_key)
        if not grade:
            continue

        # '세특_전체: 비공개' 같은 비공개 처리
        if not isinstance(subjects_data, dict):
            continue

        for subject_name, content in subjects_data.items():
            # 전체 비공개 키 건너뜀
            if subject_name == "세특_전체":
                continue
            if _비공개인지(content):
                continue

            if isinstance(content, str):
                result["subjects"].append({
                    "grade": grade,
                    "subject_name": subject_name,
                    "evaluation": content,
                    "reason": "",
                })
                continue

            if not isinstance(content, dict):
                continue

            evaluation = content.get("평가내용", "")
            reason = content.get("이유", "")

            if _비공개인지(evaluation):
                continue

            result["subjects"].append({
                "grade": grade,
                "subject_name": subject_name,
                "evaluation": str(evaluation).strip() if evaluation else "",
                "reason": str(reason).strip() if reason else "",
            })

    # ── 행동특성 및 종합의견 파싱 ──
    behavior = data.get("행동특성_및_종합의견", {})
    for grade_key, content in behavior.items():
        grade = _학년_파싱(grade_key)
        if not grade:
            continue
        if _비공개인지(content):
            continue

        if isinstance(content, str):
            result["behaviors"].append({
                "grade": grade,
                "evaluation": content,
                "reason": "",
            })
            continue

        if not isinstance(content, dict):
            continue

        evaluation = content.get("평가내용", "")
        reason = content.get("이유", "")

        if _비공개인지(evaluation):
            continue

        result["behaviors"].append({
            "grade": grade,
            "evaluation": str(evaluation).strip() if evaluation else "",
            "reason": str(reason).strip() if reason else "",
        })

    return result
