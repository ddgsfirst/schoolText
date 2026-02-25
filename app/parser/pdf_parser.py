"""
생기부 PDF 파서 v3 - 전체 텍스트 섹션 기반

핵심 전략:
    1. 모든 페이지 텍스트를 하나로 합침 → 페이지 경계 문제 완전 제거
    2. 정규식으로 섹션(창체/세특/행특) 경계 탐색
    3. 각 섹션 블록 내에서 패턴 파싱

이 방식으로 해결되는 문제들:
    - 표가 페이지 중간에 잘림 → 전체 텍스트이므로 무관
    - 학생마다 표 행 수가 다름 → 패턴 기반이므로 무관
    - 추가 소제목·칸막이 → 텍스트 속에 녹아들어 무관
    - PDF 버전마다 헤더 형식 다름 → 느슨한 정규식으로 처리

이미지 기반 PDF는 ValueError를 발생시킵니다.
"""
import re
from pathlib import Path

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# ══════════════════════════════════════════════════════
# 내부 유틸
# ══════════════════════════════════════════════════════

def _전체_텍스트_추출(filepath: Path) -> str:
    """
    모든 페이지 텍스트를 하나의 문자열로 합칩니다.
    페이지 간 \n으로 구분하여 경계를 자연스럽게 처리합니다.
    """
    with pdfplumber.open(filepath) as pdf:
        # 이미지 기반 PDF 감지
        sample = "".join((p.extract_text() or "") for p in pdf.pages[:2]).strip()
        if len(sample) < 50:
            raise ValueError(f"{filepath.name}은 이미지 기반 PDF입니다 (텍스트 추출 불가)")
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _공백_정제(text: str) -> str:
    """연속 공백/개행/\r을 단일 공백으로 정리합니다."""
    return re.sub(r"[ \t\r]+", " ", text).strip()


def _비공개(text: str) -> bool:
    """비공개 처리된 항목인지 판단합니다."""
    return "공공기관의 정보공개" in text or "비공개" in text


def _문서_꼬리(text: str) -> bool:
    """
    문서 하단의 잡음 정보(학교명+날짜, 발급번호, IP, 전화번호, 서명란 등)인지 판단합니다.
    행특/세특 내용에서 이런 줄은 제거해야 합니다.
    """
    노이즈_패턴 = [
        r"(고등학교|학교)\s+\d{4}년\s+\d+월",   # 학교명 + 날짜 (세특 헤더 제외하려면 연도+월 필수)
        r"발급번호\s*:",                         # 발급번호
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", # IP 주소
        r"전화번호\s+\d{2,3}-",                  # 전화번호
        r"담\s*당\s*자|담당부서",                 # 담당자 정보
        r"학\s*교\s*생\s*활\s*기\s*록\s*부",      # 생기부 제목
        r"주민등록번호",                          # 개인정보
        r"고\s*등\s*학\s*교\s*장",               # 학교장 서명
    ]
    return any(re.search(p, text) for p in 노이즈_패턴)


def _섹션_추출(full_text: str, 시작_패턴: str, 종료_패턴: str) -> str:
    """
    전체 텍스트에서 시작_패턴 ~ 종료_패턴 사이의 블록을 추출합니다.
    종료 패턴이 없으면 끝까지 반환합니다.
    re.DOTALL을 사용하여 개행도 패턴에 포함합니다.
    """
    m_start = re.search(시작_패턴, full_text, re.DOTALL)
    if not m_start:
        return ""
    body = full_text[m_start.end():]
    m_end = re.search(종료_패턴, body)  # 종료 패턴은 줄 단위
    return body[: m_end.start()] if m_end else body



# ══════════════════════════════════════════════════════
# 창체 파싱
# ══════════════════════════════════════════════════════

_활동_타입 = {"자율활동", "동아리활동", "진로활동"}


def _정제_창체_내용(content: str) -> str:
    """
    창체 셀 텍스트에서 노이즈를 제거합니다.
    extract_tables 셀 내용에 남아 있을 수 있는 헤더/꼬리 제거.
    """
    lines = []
    for line in content.split("\n"):
        line_s = line.strip().replace("\r", "")
        if not line_s:
            continue
        if "당해학년도" in line_s or "내부검토 중" in line_s:
            continue
        if _비공개(line_s):
            continue
        if _문서_꼬리(line_s):
            continue
        if re.match(r"^(학년|영역|시간|특기사항|창의적|창 의 적)\s*$", line_s):
            continue
        if re.search(r"창\s*의\s*적\s*체\s*험\s*활\s*동\s*상\s*황", line_s):
            continue
        if re.match(r"^(반|번호|이름|\d+\s*반)", line_s):
            continue
        if re.match(r".*영역\s+시간\s+특기사항", line_s):
            continue
        lines.append(line_s)
    return " ".join(lines).strip()


def _창체_테이블_파싱(pdf) -> list[dict]:
    """
    pdfplumber.extract_tables()를 이용하여 창체 섹션을 셀 단위로 추출합니다.

    테이블 구조 (실제 extract_tables 출력):
        Row 2: ["1", "진로활동", "53", "희망분야", "백엔드 개발자"]  ← 헤더 행
        Row 3: ["", "", "", "아동·청소년 성격유형검사...(411자)", ""]  ← 내용 행
        Row 4: ["2", "자율활동", "97", "", ""]                       ← 다음 활동 헤더

    핵심: 헤더 행과 내용 행이 분리되어 있으므로
    current_activity 상태를 추적하여 내용 행을 올바른 활동에 귀속시킵니다.

    Returns: [{category, grade, career_hope, original_text}]
    """
    결과: dict[tuple, dict] = {}   # (grade, category) -> item
    current_grade = 1
    current_activity = None
    창체_시작됨 = False

    for page in pdf.pages:
        page_text = page.extract_text() or ""

        # 창체 섹션 진입 감지
        if re.search(r"창\s*의\s*적\s*체\s*험\s*활\s*동\s*상\s*황", page_text):
            창체_시작됨 = True

        # 창체 섹션 종료 감지
        if 창체_시작됨 and re.search(
            r"(?:봉\s*사\s*활\s*동\s*실\s*적|교\s*과\s*학\s*습\s*발\s*달\s*상\s*황)",
            page_text,
        ):
            창체_시작됨 = False

        if not 창체_시작됨:
            if not re.search(r"창\s*의\s*적\s*체\s*험\s*활\s*동\s*상\s*황", page_text):
                continue

        tables = page.extract_tables()
        for table in tables:
            if not table:
                continue

            # 이 테이블이 창체 테이블인지 확인
            flat = " ".join(str(c or "") for row in table for c in row)
            if not any(t in flat for t in _활동_타입):
                continue

            for row in table:
                if not row:
                    continue
                cells = [str(c or "").strip().replace("\r", "") for c in row]

                # 완전히 빈 행 스킵
                if all(c == "" for c in cells):
                    continue

                # 학년 갱신 (1~3 단독 숫자 셀)
                for c in cells:
                    if re.match(r"^[123]$", c):
                        current_grade = int(c)
                        break

                # 활동 영역 감지 -> current_activity 갱신
                activity = next((c for c in cells if c in _활동_타입), None)
                if activity:
                    current_activity = activity

                if not current_activity:
                    continue

                key = (current_grade, current_activity)

                # -- 희망분야 추출 (진로활동만) --
                # 형태 1: 별도 셀 ["희망분야", "백엔드 개발자"]
                career_hope = None
                career_hope_value = None
                if current_activity == "진로활동":
                    for i, c in enumerate(cells):
                        if c == "희망분야" and i + 1 < len(cells) and cells[i + 1]:
                            career_hope = cells[i + 1]
                            career_hope_value = career_hope
                            break

                # -- 내용 셀 수집 --
                skip = _활동_타입 | {"학년", "영역", "시간", "특기사항", "희망분야", ""}
                content_cells = [
                    c for c in cells
                    if c not in skip
                    and c != career_hope_value            # 희망분야 값 제외
                    and not re.match(r"^[123]$", c)       # 학년
                    and not re.match(r"^\d{1,3}$", c)     # 시간
                ]

                # 내용 중에서 가장 긴 셀 선택
                content = ""
                if content_cells:
                    content_raw = max(content_cells, key=len)

                    # 형태 2: 내용 텍스트 안에 "희망분야 값" 라인이 있는 경우
                    if current_activity == "진로활동" and not career_hope:
                        hope_m = re.search(
                            r"희망분야[\s\t]+(.+?)(?:\n|$)", content_raw
                        )
                        if hope_m:
                            career_hope = hope_m.group(1).strip()
                            content_raw = (
                                content_raw[: hope_m.start()]
                                + content_raw[hope_m.end() :]
                            )

                    content = _정제_창체_내용(content_raw)

                # -- 결과 저장/병합 --
                item_base = {
                    "category": current_activity,
                    "grade": current_grade,
                    "original_text": content if len(content) > 15 else None,
                }
                # career_hope는 진로활동에만 존재
                if current_activity == "진로활동":
                    item_base["career_hope"] = career_hope

                if key not in 결과:
                    결과[key] = item_base
                else:
                    # career_hope 갱신 (진로활동만)
                    if current_activity == "진로활동" and career_hope and not 결과[key].get("career_hope"):
                        결과[key]["career_hope"] = career_hope
                    # 내용 병합 (같은 활동이 여러 행에 분산된 경우)
                    if content:
                        existing = 결과[key]["original_text"] or ""
                        if content not in existing:
                            merged = (existing + " " + content).strip()
                            결과[key]["original_text"] = (
                                merged if len(merged) > 15 else None
                            )

    # 정렬: 학년 -> 자율/동아리/진로 순
    순서 = {"자율활동": 0, "동아리활동": 1, "진로활동": 2}
    return sorted(
        결과.values(),
        key=lambda x: (x["grade"], 순서.get(x["category"], 9)),
    )

def _창체_파싱(full_text: str) -> list[dict]:
    """
    창의적 체험활동상황 섹션에서 활동별 원문을 추출합니다.

    섹션 추출 전략:
        시작: "창의적 체험활동상황" (스페이스 허용)
        종료: 봉사활동 / 교과학습 / 독서활동 중 첫 번째

    활동 항목 패턴 (두 가지 형태):
        형태 A: "영역명 시간\n내용" (시간이 줄 끝)
            예: "자율활동 105\n2학기 학급회장으로서..."
        형태 B: "학년 영역명 시간\n내용"
            예: "1 자율활동 53\n희망분야 백엔드 개발자\n..."
        → 공통: (자율활동|동아리활동|진로활동) + 숫자(시간) 이후 내용

    Returns: [{category, grade, original_text}]
    """
    결과 = []

    # 창체 섹션 추출
    # 종료: 섹션 번호 있는 봉사활동 또는 봉사활동 실적 테이블 헤더 또는 교과학습
    블록 = _섹션_추출(
        full_text,
        시작_패턴=r"창\s*의\s*적\s*체\s*험\s*활\s*동\s*상\s*황",
        종료_패턴=r"(\n\d+\.\s*(?:봉사활동|교과학습|독서활동|행동특성)|봉\s*사\s*활\s*동\s*실\s*적)",
    )
    if not 블록:
        return []

    # PDF에서 단어 중간에 \r이 삽입된 경우 정규화 (예: '동아리\r활동', '진로\r활동')
    # 이를 제거하지 않으면 분할 패턴이 매칭 실패함
    블록 = 블록.replace('\r', '')


    # 패턴: 선택적 학년 + 활동명 + 시간(숫자)
    분할_패턴 = re.compile(
        r"\n(\d)?\s*(자율활동|동아리활동|진로활동)\s+(\d+)\s*\n",
    )

    # 분할 패턴 매칭 (match 객체 저장 → 정확한 start/end 계산)
    matches = list(분할_패턴.finditer(블록))

    current_grade = 1
    segments = []  # [(grade, category, content_start, match_obj)]

    for m in matches:
        if m.group(1):
            current_grade = int(m.group(1))
        segments.append((current_grade, m.group(2), m.end(), m))

    클럽_마커 = re.compile(r"\([가-힣][가-힣\s·:]*\)\s*\(\d+시간\)")
    페이지_헤더 = re.compile(r"창\s*의\s*적\s*체\s*험\s*활\s*동\s*상\s*황")

    # ── 1단계: content_raw 수집 + 재분배 ──
    raws: list[tuple[int, str, str]] = []
    pending: str = ""

    # 첫 번째 활동 헤더 이전 내용 → 첫 활동에 귀속 (예: "체육 한마당...")
    if matches:
        pending = 블록[:matches[0].start()]

    for i, (grade, category, start, _) in enumerate(segments):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(블록)
        content_raw = pending + 블록[start:end]
        pending = ""

        봉사_m = re.search(r"봉\s*사\s*활\s*동\s*실\s*적", content_raw)
        if 봉사_m:
            content_raw = content_raw[:봉사_m.start()]

        # 자율→동아리: 클럽마커 기준 분리
        if (category == "자율활동" and
                i + 1 < len(segments) and segments[i + 1][1] == "동아리활동"):
            m = 클럽_마커.search(content_raw)
            if m:
                pending = content_raw[m.start():]
                content_raw = content_raw[:m.start()]

        # 페이지 헤더 기준 분리: 헤더 이후 내용은 다음 활동에 귀속
        # (첫 세그먼트 제외: 첫 페이지의 "창의적 체험활동상황"은 섹션 제목)
        if i > 0 and i + 1 < len(segments):
            pm = 페이지_헤더.search(content_raw)
            if pm:
                pending = content_raw[pm.end():]
                content_raw = content_raw[:pm.start()]

        raws.append((grade, category, content_raw))

    # ── 2단계: 라인 필터 ──
    for grade, category, content_raw in raws:
        content_lines = []
        for line in content_raw.split("\n"):
            line_s = line.strip()
            if not line_s: continue
            if "당해학년도" in line_s or "내부검토 중" in line_s: continue
            if _비공개(line_s): continue
            if _문서_꼬리(line_s): continue
            # 단일 헤더 단어
            if re.match(r"^(학년|영역|시간|특기사항|창의적|창 의 적)\s*$", line_s): continue
            if re.search(r"창\s*의\s*적\s*체\s*험\s*활\s*동\s*상\s*황", line_s): continue
            if re.match(r"^(반|번호|이름|\d+\s*반)", line_s): continue
            # 테이블 헤더가 한 줄로 합쳐진 경우
            if re.match(r".*영역\s+시간\s+특기사항", line_s): continue
            # 진로 메타 라인 (career_hope는 별도 필드)
            if re.match(r"^희망분야", line_s): continue
            content_lines.append(line_s)

        content = " ".join(content_lines).strip()

        if len(content) > 15:
            결과.append({"category": category, "grade": grade, "original_text": content})
        else:
            결과.append({"category": category, "grade": grade, "original_text": None})

    return 결과


# ══════════════════════════════════════════════════════
# 세특 파싱
# ══════════════════════════════════════════════════════

def _세특_파싱(full_text: str) -> list[dict]:
    """
    교과학습발달상황 내 세부능력 및 특기사항을 파싱합니다.

    섹션 추출:
        시작: "과목 세부능력 및 특기사항" 또는 "과 목 세 부 능 력..." (스페이스 변형)
        종료: 독서활동 / 행동특성

    항목 패턴:
        "(N학기)과목명: 내용" 형태
        학년은 "[N학년]" 헤더로 탐지

    Returns: [{grade, subject_name, original_text}]
    """
    결과 = []

    # 세특 섹션은 여러 학년에 걸쳐 있음
    # "[N학년]" 기준으로 분리 후 각각 파싱
    세특_전체 = _섹션_추출(
        full_text,
        시작_패턴=r"과[\s\r]*목[\s\r]+세[\s\r]*부[\s\r]*능[\s\r]*력[\s\r]*및[\s\r]*특[\s\r]*기[\s\r]*사[\s\r]*항",
        종료_패턴=r"\n\d+\.\s*(?:독서활동|행동특성)",
    )
    # 폴백: 위 패턴이 안 잡히면 (1학기) 패턴이 처음 나오는 위치부터 추출
    if not 세특_전체:
        m_fallback = re.search(r"\(1학기\)", full_text)
        if m_fallback:
            body = full_text[m_fallback.start():]
            m_end = re.search(r"\n\d+\.\s*(?:독서활동|행동특성)", body)
            세특_전체 = body[:m_end.start()] if m_end else body
    if not 세특_전체:
        return []


    # 학년 블록 분리: [N학년] 헤더 기준
    학년_블록_패턴 = re.compile(r"\[(\d)학년\]\r?")
    학년_매치 = list(학년_블록_패턴.finditer(세특_전체))

    # 파싱할 블록 목록: (grade, start, end)
    블록_목록: list[tuple[int, int, int]] = []

    if not 학년_매치:
        # [N학년] 헤더가 전혀 없으면 전체를 1학년으로
        블록_목록.append((1, 0, len(세특_전체)))
    else:
        # 첫 헤더 이전 본문 (의미 있는 내용이 있을 때만)
        if 학년_매치[0].start() > 200:
            pre_grade = max(1, int(학년_매치[0].group(1)) - 1)
            블록_목록.append((pre_grade, 0, 학년_매치[0].start()))
        # [N학년] 헤더별 블록
        for i, m in enumerate(학년_매치):
            s = m.end()
            e = 학년_매치[i + 1].start() if i + 1 < len(학년_매치) else len(세특_전체)
            블록_목록.append((int(m.group(1)), s, e))

    # 각 블록 파싱
    for grade, start, end in 블록_목록:
        블록 = 세특_전체[start:end]
        if _비공개(블록):
            continue

        # (N학기)과목명: 내용 패턴
        과목_패턴 = re.compile(
            r"\((\d)학기\)(.*?)(?:\s*[\[【][^】\]]*[\]】])?\s*[:：]\s*(.+?)(?=\(\d학기\)|\Z)",
            re.DOTALL,
        )

        for m in 과목_패턴.finditer(블록):
            subject_raw = _공백_정제(m.group(2))
            content_raw = m.group(3)

            # 과목명 정제
            subject_name = re.sub(r"\s*[\[【][^】\]]*[\]】]\s*", "", subject_raw)
            subject_name = _공백_정제(subject_name)
            if not subject_name or len(subject_name) > 30:
                continue

            # 내용 정제 (학교명/날짜/반번호/잡음 행 제거)
            content_lines = []
            for line in content_raw.split("\n"):
                line_s = line.strip()
                if not line_s or _비공개(line_s):
                    continue
                if _문서_꼬리(line_s):
                    continue
                if re.match(r"^\s*(과\s*목|세\s*부\s*능\s*력)\s*$", line_s):
                    continue
                content_lines.append(line_s)

            content = " ".join(content_lines).strip()
            if len(content) < 20:
                continue

            결과.append({
                "grade": grade,
                "subject_name": subject_name,
                "original_text": content[:3000],
            })

    return 결과


# ══════════════════════════════════════════════════════
# 행특 파싱
# ══════════════════════════════════════════════════════

def _행특_파싱(full_text: str) -> list[dict]:
    """
    행동특성 및 종합의견 섹션에서 학년별 원문을 추출합니다.

    섹션 추출:
        시작: "행동특성 및 종합의견" (스페이스 변형 허용)
        종료: 문서 끝

    학년 분리:
        "\n1 " 또는 "\n2 " 형태의 줄 시작으로 분리
        단, 학년 헤더 줄은 제외

    Returns: [{grade, original_text}]
    """
    결과 = []

    블록 = _섹션_추출(
        full_text,
        시작_패턴=r"\d+\.\s*행\s*동\s*특\s*성\s*및\s*종\s*합\s*의\s*견",
        종료_패턴=r"\n\d+\.\s*[가-힣]",  # 다음 섹션 (사실상 문서 끝)
    )
    if not 블록:
        return []

    # "학년 행동특성 및 종합의견" 헤더 줄 제거
    블록 = re.sub(r"학\s*년\s+행\s*동\s*특\s*성\s*및\s*종\s*합\s*의\s*견\s*\n?", "", 블록)

    # 학년 분리 전략:
    # s1유형: "\'\n1\n내용..." (학년 숫자가 독립 1줄)
    # s2유형: "...\n1 내용..." (학년 숫자가 줄 앞에 붙어 있음)
    학년_매치 = list(re.finditer(
        r"(?:^|\n)(\d)(?=\s*\n|\s+[^\/\d])",  # 1~3개 학년, 다음이 \n 또는 한글 내용
        블록,
        re.MULTILINE,
    ))
    # 학년 다중 정의 방지: 1~3만 허용
    학년_매치 = [
        m for m in 학년_매치
        if m.group(1).isdigit() and 1 <= int(m.group(1)) <= 3
    ]

    for m in 학년_매치:
        grade_str = m.group(1)
        grade = int(grade_str)
        # 내용: 학년 숫자 다음부터 다음 학년 주설 전까지
        start_idx = m.end()
        # 다음 학년 주설 위치 (없으면 끝까지)
        next_matches = [nm for nm in 학년_매치 if nm.start() > m.start()]
        end_idx = next_matches[0].start() if next_matches else len(블록)
        content_raw = 블록[start_idx:end_idx]

        content_lines = []
        for line in content_raw.split("\n"):
            line_s = line.strip()
            if not line_s or _비공개(line_s):
                continue
            if _문서_꼬리(line_s):
                continue
            if re.match(r"^(학년|반|번호|이름|\d+\s*반)\s*$", line_s):
                continue
            content_lines.append(line_s)

        content = " ".join(content_lines).strip()
        if len(content) > 20:
            결과.append({
                "grade": grade,
                "original_text": content[:3000],
            })

    # 중복 제거 (같은 학년 중복 데이터)
    seen = set()
    정렸 = []
    for item in 결과:
        k = item["grade"]
        if k not in seen:
            seen.add(k)
            정렸.append(item)
    return 정렸


# ══════════════════════════════════════════════════════
# 메인 파싱 함수
# ══════════════════════════════════════════════════════

def parse_pdf(filepath: str | Path) -> dict:
    """
    생기부 PDF에서 창체/세특/행특 원문을 추출합니다.

    창체는 extract_tables() 기반으로 파싱합니다.
    (extract_text()로 멀티행 테이블을 읽으면 행 헤더와 내용이 뒤섞이는
     문제를 근본적으로 해결하기 위함입니다.)
    세특/행특은 기존 텍스트 기반 파싱을 유지합니다.

    Args:
        filepath: PDF 파일 경로

    Returns:
        {
            "activities":  [{category, grade, career_hope, original_text}],
            "subjects":    [{grade, subject_name, original_text}],
            "behaviors":   [{grade, original_text}],
            "source_pdf":  str (파일명),
        }

    Raises:
        ValueError: pdfplumber 미설치 또는 이미지 기반 PDF인 경우
    """
    if not PDF_AVAILABLE:
        raise ValueError("pdfplumber가 설치되지 않았습니다: pip install pdfplumber")

    filepath = Path(filepath)

    with pdfplumber.open(filepath) as pdf:
        # 이미지 기반 PDF 감지
        sample = "".join((p.extract_text() or "") for p in pdf.pages[:2]).strip()
        if len(sample) < 50:
            raise ValueError(f"{filepath.name}은 이미지 기반 PDF입니다 (텍스트 추출 불가)")

        # 창체: 테이블 기반 파싱 (primary)
        activities = _창체_테이블_파싱(pdf)

        # 학생 이름 추출 (테이블에서 "이름" 셀 검색)
        student_name = None
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                for row in (table or []):
                    cells = [str(c or "").strip() for c in row]
                    for i, c in enumerate(cells):
                        if c == "이름" and i + 1 < len(cells) and cells[i + 1]:
                            student_name = cells[i + 1]
                            break
                    if student_name:
                        break
                if student_name:
                    break
            if student_name:
                break

        # 세특/행특: 텍스트 기반 파싱 (기존 방식 유지)
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    subjects = _세특_파싱(full_text)
    behaviors = _행특_파싱(full_text)

    # 폴백: 테이블 추출이 실패한 경우 텍스트 기반으로 재시도
    if not activities:
        activities = _창체_파싱(full_text)

    return {
        "student_name": student_name,
        "activities": activities,
        "subjects":   subjects,
        "behaviors":  behaviors,
        "source_pdf": filepath.name,
    }
