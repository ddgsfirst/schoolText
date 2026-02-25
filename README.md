# 등대 텍스트 처리 API

생기부 PDF에서 원문을 추출하고, 레퍼런스 데이터와 함께 관리하는 백엔드 API.

## 구조

```
app/
├── main.py                  # FastAPI 앱 진입점
├── config.py                # 환경변수 설정
├── database.py              # 이중 DB 엔진 (reference / client)
├── parser/
│   ├── pdf_parser.py        # 생기부 PDF → 창체/세특/행특 원문 추출
│   └── yaml_parser.py       # testone 평가 YAML 파싱
├── models/
│   ├── reference.py         # 레퍼런스 DB 모델 (ref_*)
│   └── client.py            # 클라이언트 DB 모델
├── schemas/
│   ├── reference.py         # 레퍼런스 응답 스키마
│   └── client.py            # 클라이언트 응답 스키마
├── routers/
│   ├── reference.py         # /api/ref/* 엔드포인트
│   └── client.py            # /api/client/* 엔드포인트
├── services/
│   ├── reference_service.py # 레퍼런스 저장 로직
│   └── client_service.py    # 클라이언트 저장 로직
data/
├── yaml/                    # 레퍼런스 평가 YAML (s1.yaml, s2.yaml, ...)
└── pdf/                     # 레퍼런스 생기부 PDF (s1.pdf, s2.pdf, ...)
```

## DB 구조

PostgreSQL 2개 DB를 사용함.

### reference DB

레퍼런스(사전 등록) 데이터. YAML 평가 + PDF 원문.

```
ref_students ─┬── ref_career_hopes (학년별 희망분야)
              ├── ref_activities   (창체: 원문 + 평가)
              ├── ref_subjects     (세특: 원문 + 평가)
              └── ref_behaviors    (행특: 원문 + 평가)
```

### client DB

클라이언트가 업로드한 생기부. PDF 원문 + AI 평가(추후).

```
students ─┬── career_hopes
          ├── activities
          ├── subjects
          └── behaviors
```

## 로직 흐름

### 레퍼런스 등록

1. `data/yaml/`에 평가 YAML, `data/pdf/`에 생기부 PDF를 넣음
2. `POST /api/ref/upload/batch` 호출 → YAML 파싱 후 DB 저장
3. 같은 파일명의 PDF가 있으면(s1.yaml ↔ s1.pdf) 원문도 함께 저장
4. 개별 업로드: `/api/ref/upload/yaml`, `/api/ref/upload/pdf`

### 클라이언트 업로드

1. `POST /api/client/upload`로 PDF 업로드
2. PDF에서 창체/세특/행특 원문 자동 추출 후 DB 저장
3. AI 평가는 추후 별도 API로 생성 예정

### PDF 파싱 방식

- **창체**: `extract_tables()` 기반 (멀티행 테이블 구조 대응)
- **세특/행특**: `extract_text()` + 정규식 기반 (섹션 분할)
- 이미지 기반 PDF는 지원하지 않음

## API 문서

서버 실행 후 `/docs`에서 Swagger UI로 확인.

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

`.env` 파일 생성:

```env
REF_DATABASE_URL=postgresql://user:pass@host:5432/reference
USER_DATABASE_URL=postgresql://user:pass@host:5432/client
```

### 3. 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API 문서: http://localhost:8000/docs
- 테이블은 서버 시작 시 자동 생성됨
