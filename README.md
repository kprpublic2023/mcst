# 정부조직 SNS 운영현황·성과 분석기

19부 6처 19청 6위원회의 **YouTube · Instagram · X · Facebook · 블로그** 운영현황과
성과 지표를 정기 수집·비교·시각화하는 도구입니다.

## 주요 기능

- 시드 YAML(`data/gov_orgs.yaml`)로 기관·계정을 관리 (검토·수정 가능)
- 플랫폼별 수집기 (API 키 우선, 없으면 공개 페이지 폴백)
- SQLite에 시계열 스냅샷을 적재해 트렌드/성장률 산출
- 활성도 점수 (게시 빈도 + 신선도 + 인게이지율) 기반 비교·랭킹
- Streamlit 대시보드 + CSV 묶음 + 공유용 HTML + PDF 리포트

## 설치

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # API 키가 있으면 채워주세요. 없어도 동작합니다.
```

## 1분 데모 (API 키 없이 동작 확인)

```bash
python -m mcst.cli demo --weeks 8        # 8주치 가상 트렌드 데이터 시드
streamlit run dashboard/app.py
```

## 핸들 시드 채우기

세 가지 방법을 선택해서/조합해서 사용할 수 있습니다.

```bash
# 방법1) 큐레이션된 핸들을 일괄 적용 (오프라인, 권장 시작점)
python scripts/apply_known_handles.py            # dry-run
python scripts/apply_known_handles.py --apply    # 실제 반영
python scripts/apply_known_handles.py --apply --min-confidence medium

# 방법2) 각 기관 홈페이지를 크롤링해서 자동 발견 (네트워크 필요)
python scripts/discover_handles.py               # dry-run
python scripts/discover_handles.py --apply       # 실제 반영
python scripts/discover_handles.py --apply --org moef --org moe   # 일부만

# 방법3) 직접 수정
$EDITOR data/gov_orgs.yaml
```

세 방법 모두 **이미 채워진 값은 덮어쓰지 않습니다**. 검토가 끝난 항목은
`verified: true` 로 표시해 두면 좋습니다.

## 실 수집

1. `data/gov_orgs.yaml` 의 각 기관 `accounts` 항목을 채우고 `verified: true` 로 변경
2. `.env` 에 사용 가능한 API 키 입력 (없으면 공개페이지 폴백 시도)
3. 수집 실행

```bash
python -m mcst.cli collect                 # 모든 플랫폼
python -m mcst.cli collect --platform youtube
```

## 정기 수집 (cron)

```bash
# 매일 03:00 (KST)
0 3 * * * /path/to/mcst/scripts/schedule.sh >> /path/to/mcst/data/cron.log 2>&1
```

## 리포트 생성

```bash
python -m mcst.cli report --out reports/output --pdf
# reports/output/
#   ├── report.html        # 공유용 정적 페이지
#   ├── report.pdf         # PDF (WeasyPrint)
#   └── *.csv              # 플랫폼/분류 요약, 활성도/팔로워 랭킹, 성장률
```

대시보드의 **리포트** 탭에서도 HTML/CSV.zip/PDF 를 즉시 다운로드 받을 수 있습니다.

## 디렉터리

```
mcst/
├── data/gov_orgs.yaml          # 기관·계정 시드 (사용자가 수정)
├── mcst/
│   ├── config.py               # 환경설정·시드 로더
│   ├── storage.py              # SQLite 스냅샷
│   ├── collectors/             # YouTube / Instagram / X / Facebook / Blog
│   ├── analysis/               # 지표·비교·랭킹·성장률
│   ├── reports/                # CSV / HTML(Jinja2) / PDF(WeasyPrint)
│   └── cli.py                  # collect / report / demo
├── dashboard/app.py            # Streamlit
├── scripts/schedule.sh         # cron 예시
└── reports/output/             # 생성된 산출물 (gitignored)
```

## 분석 지표

| 지표 | 정의 |
|---|---|
| `activity_score` | 30일 게시(40) + 90일 게시(20) + 신선도(20) + 인게이지율(20). 0~100 |
| `efficiency` | 팔로워 1만 명당 평균 인게이지(좋아요+댓글) |
| `engagement_rate` | (좋아요+댓글)/팔로워, 게시 평균 |
| `tier` | 활성도 기반 등급 — 휴면(≤20) / 저조(≤50) / 보통(≤75) / 우수(>75) |
| `multi_platform_score` | 기관이 운영 중인 플랫폼 수 / 5 × 100 |
| `composite_score` | 평균활성도×0.5 + 멀티플랫폼×0.3 + 인게이지율×0.2 |
| `growth_pct` | 지정 기간(기본 30일) 동안의 팔로워 증감률 |

세부 임계값:
- 30일에 12건 이상 게시 시 만점(40)
- 마지막 게시일이 60일 이상 지나면 신선도 0
- 인게이지율 5% 이상이면 만점

## API 키 안내

| 플랫폼 | API | 폴백 |
|---|---|---|
| YouTube | YouTube Data API v3 (무료 쿼터) | 채널 페이지 메타 파싱 |
| Instagram | Meta Graph API + IG Business 연결 토큰 | og:description (불안정) |
| X | API v2 Bearer (유료 등급) | nitter 미러 (가용성↓) |
| Facebook | Graph API + 페이지 토큰 | 비로그인 페이지 |
| 블로그 | (없음) | RSS (네이버/티스토리/브런치 자동 추정) |

폴백은 공식 채널이 차단/변경 시 부분 실패할 수 있습니다. 안정 운영에는 API 키를 권장합니다.

## 라이선스 / 면책

- 본 도구는 공개 정보·공식 API를 통한 분석 목적입니다.
- 각 플랫폼 이용약관 및 개인정보 처리방침을 준수하여 사용해 주세요.
