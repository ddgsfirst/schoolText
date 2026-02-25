"""testone YAML 파일 파서"""
import yaml
import re
from pathlib import Path


def _parse_grade(key: str) -> int | None:
    """'1학년', '2학년', '3학년' 또는 숫자 키에서 학년 추출"""
    if isinstance(key, int):
        return key
    m = re.match(r"(\d)", str(key))
    return int(m.group(1)) if m else None


def parse_yaml(filepath: str | Path) -> dict:
    """
    testone YAML 파일을 파싱하여 구조화된 딕셔너리로 반환합니다.

    Returns:
        {
            "student": {"name", "school", "department", "graduation_year"},
            "career_hopes": [{"grade", "hope"}],
            "activity_evals": [{"category", "grade", "career_hope", "evaluation", "reason"}],
            "subject_evals": [{"grade", "subject_name", "evaluation", "reason"}],
            "behavior_evals": [{"grade", "evaluation", "reason"}],
            "source_file": str,
        }
    """
    filepath = Path(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    result = {
        "student": {},
        "career_hopes": [],
        "activity_evals": [],
        "subject_evals": [],
        "behavior_evals": [],
        "source_file": filepath.name,
    }

    # ── 학생정보 ──
    info = data.get("학생정보", {})
    result["student"] = {
        "name": info.get("성명", ""),
        "school": info.get("학교", ""),
        "department": info.get("학과", ""),
        "graduation_year": info.get("졸업연도"),
    }

    # 희망분야
    hopes = info.get("희망분야", {})
    if isinstance(hopes, dict):
        for key, value in hopes.items():
            grade = _parse_grade(key)
            if grade and value and str(value) != "비공개":
                result["career_hopes"].append({
                    "grade": grade,
                    "hope": str(value),
                })

    # ── 창의적 체험활동상황 ──
    activities = data.get("창의적_체험활동상황", {})
    for category, grades_data in activities.items():
        if not isinstance(grades_data, dict):
            continue
        for grade_key, content in grades_data.items():
            grade = _parse_grade(grade_key)
            if not grade:
                continue

            # "비공개" 처리
            if isinstance(content, str):
                if content == "비공개":
                    continue
                # 단순 문자열인 경우
                result["activity_evals"].append({
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

            if isinstance(evaluation, str) and evaluation == "비공개":
                continue

            result["activity_evals"].append({
                "category": category,
                "grade": grade,
                "career_hope": str(career_hope) if career_hope and str(career_hope) != "비공개" else None,
                "evaluation": str(evaluation).strip() if evaluation else "",
                "reason": str(reason).strip() if reason else "",
            })

    # ── 세부능력 및 특기사항 ──
    subjects = data.get("세부능력_및_특기사항", {})
    for grade_key, subjects_data in subjects.items():
        grade = _parse_grade(grade_key)
        if not grade:
            continue

        if not isinstance(subjects_data, dict):
            # "세특_전체: 비공개" 같은 경우
            continue

        for subject_name, content in subjects_data.items():
            if subject_name == "세특_전체":
                continue

            if isinstance(content, str):
                if content == "비공개":
                    continue
                result["subject_evals"].append({
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

            if isinstance(evaluation, str) and evaluation == "비공개":
                continue

            result["subject_evals"].append({
                "grade": grade,
                "subject_name": subject_name,
                "evaluation": str(evaluation).strip() if evaluation else "",
                "reason": str(reason).strip() if reason else "",
            })

    # ── 행동특성 및 종합의견 ──
    behavior = data.get("행동특성_및_종합의견", {})
    for grade_key, content in behavior.items():
        grade = _parse_grade(grade_key)
        if not grade:
            continue

        if isinstance(content, str):
            if content == "비공개":
                continue
            result["behavior_evals"].append({
                "grade": grade,
                "evaluation": content,
                "reason": "",
            })
            continue

        if not isinstance(content, dict):
            continue

        evaluation = content.get("평가내용", "")
        reason = content.get("이유", "")

        if isinstance(evaluation, str) and evaluation == "비공개":
            continue

        result["behavior_evals"].append({
            "grade": grade,
            "evaluation": str(evaluation).strip() if evaluation else "",
            "reason": str(reason).strip() if reason else "",
        })

    return result
