# igzun-daily-report HTML 데이터 스키마

이 문서는 현재 HTML(`templates/report.html`, `site/YYYY-MM-DD/index.html`)에 주입할 데이터 구조를 정의함.
HTML이 바뀌면 이 문서와 `data/schema.json`도 같이 업데이트해야 함.

## 루트 구조

```json
{
  "date": "2026년 3월 19일 (목) 업데이트",
  "dataByPeriod": {
    "1일": { ... },
    "1주": { ... },
    "1개월": { ... },
    "1년": { ... }
  }
}
```

## period key 규칙
- 예: `1일`, `3일`, `1주`, `1개월`, `3개월`, `1년`
- HTML은 `Object.keys(dataByPeriod)`를 그대로 period chip으로 렌더링함.
- `월`, `년`이 포함되면 거시 분석 모드(`isMacroPeriod`)로 분기함.

## 각 기간(period) 구조

```json
{
  "briefing": {
    "sentiment": {
      "score": 45,
      "status": "중립",
      "desc": "단기적으로 시장이 숨 고르기에 들어갔습니다."
    },
    "forecast": {
      "title": "단기 수급 및 모멘텀 전망",
      "text": "전망 본문"
    },
    "insights": [
      { "category": "일일 시황", "text": "요약 문장" }
    ],
    "indices": [
      { "name": "S&P 500", "price": "5,123.45", "change": "▼ 0.82%", "isUp": false }
    ]
  },
  "newsList": [
    {
      "title": "기사 제목",
      "tags": ["물가 지표", "단기 변동성"],
      "summary": "기사/리포트 요약",
      "impacts": [
        { "sector": "기술 / 성장주", "isPositive": false, "desc": "영향 설명" }
      ]
    }
  ],
  "portfolio": {
    "accountAlert": "상단 강조 문구(html 허용)",
    "accountDetail": "상세 피드백(html 허용)",
    "weeklyReview": {
      "returnRate": "+5.4%",
      "desc": "수익률 설명"
    },
    "holdings": [
      {
        "name": "테슬라",
        "ticker": "TSLA",
        "returnRate": "-2.5%",
        "score": -30,
        "indicators": ["RSI 30 이탈", "단기 매물대 저항"],
        "reason": "보유 종목 평가 설명"
      }
    ],
    "planDesc": "자산배분 설명",
    "allocations": [
      { "name": "현금 대기", "percent": 60, "color": "#E5E8EB", "desc": "방어 목적" }
    ]
  },
  "recommendations": {
    "ideas": [
      {
        "logo": "📉",
        "name": "ProShares Short S&P500",
        "ticker": "SH",
        "action": "단기 헷지 매수",
        "linkedIssue": "단기 금리 상승 우려",
        "reason": "추천 이유"
      }
    ],
    "etfRanking": [
      { "rank": 1, "name": "Energy Select Sector SPDR", "ticker": "XLE", "score": 85 }
    ]
  }
}
```

## 필드 설명 및 추출 원천

### 1. date
- 타입: string
- 용도: 상단 날짜 표시
- 원천: 생성 날짜 / 리포트 기준일

### 2. briefing.sentiment
- `score`: 0~100
- `status`: 문자열 (`침체`, `중립`, `탐욕` 등)
- `desc`: 한 줄 해설
- 원천 후보:
  - 시장 breadth
  - 지수 수익률
  - 변동성(VIX)
  - 금리/달러/원자재 방향

### 3. briefing.forecast
- `title`: 전망 제목
- `text`: 전망 본문
- 원천 후보:
  - 거시 리포트 요약
  - 당일 뉴스 핵심 요약
  - 수급/실적/정책 일정

### 4. briefing.insights[]
- `category`: 예: 일일 시황 / 자금 이동 / 실적 장세 / 매크로
- `text`: 핵심 문장
- 원천 후보:
  - 뉴스 요약
  - 증권사 리포트 bullet
  - 시장 데이터 변화

### 5. briefing.indices[]
- `name`, `price`, `change`, `isUp`
- 원천 후보:
  - S&P 500, Nasdaq, Dow, KOSPI, KOSDAQ, DXY, US10Y, WTI, Gold
- 비고:
  - 현재 HTML은 어떤 지수든 렌더 가능함

### 6. newsList[]
- `title`: 기사/이슈 제목
- `tags[]`: 키워드 태그
- `summary`: 2~4문장 요약
- `impacts[]`: 섹터 영향 분석
- 원천 후보:
  - raw news
  - raw reports
  - 공시/매크로 이벤트

### 7. portfolio.accountAlert / accountDetail
- HTML 허용
- 원천 후보:
  - 포트폴리오 평가 엔진
  - 보유종목/현금비중 분석

### 8. portfolio.weeklyReview
- `returnRate`: 문자열
- `desc`: 성과 설명
- 원천 후보:
  - 계좌 스냅샷
  - 벤치마크 비교

### 9. portfolio.holdings[]
- `name`, `ticker`, `returnRate`, `score`, `indicators[]`, `reason`
- score 범위: -100 ~ 100
- score 해석:
  - -100~-60: 풀매도
  - -59~-20: 매도
  - -19~19: 보유
  - 20~59: 매수
  - 60~100: 풀매수
- 원천 후보:
  - 포트폴리오 보유내역
  - 기술지표
  - 실적/추정치 변화
  - 뉴스 센티먼트

### 10. portfolio.allocations[]
- `name`, `percent`, `color`, `desc`
- 합계는 가능하면 100
- 원천 후보:
  - 모델 포트폴리오
  - 실제 계좌 비중

### 11. recommendations.ideas[]
- 액션성 아이디어
- 원천 후보:
  - 모멘텀 스크리닝
  - 리포트 conviction pick
  - 테마 연결 결과

### 12. recommendations.etfRanking[]
- `rank`, `name`, `ticker`, `score`
- 원천 후보:
  - ETF 팩터 스코어링
  - 성과/변동성/거래량/추세 종합 점수

## 원문(raw) → 스키마 매핑 가이드

### news raw
- 제목 → `newsList[].title`
- 본문 요약 → `newsList[].summary`
- 키워드 추출 → `newsList[].tags[]`
- 기사 영향 해석 → `newsList[].impacts[]`
- 여러 기사 종합 → `briefing.insights[]`, `briefing.forecast.text`

### market raw
- 지수 종가/등락률 → `briefing.indices[]`
- 변동성/금리/환율 → `briefing.sentiment`, `briefing.forecast`, `briefing.insights`
- 기간 수익률 → `recommendations.etfRanking[]` 점수 계산 입력

### reports raw
- 하우스뷰/섹터 뷰 → `briefing.forecast`, `briefing.insights`, `newsList[].impacts[]`
- 종목 의견 → `portfolio.holdings[].reason`, `recommendations.ideas[]`

### portfolio raw
- 계좌 현황 → `portfolio.accountAlert`, `portfolio.accountDetail`
- 종목별 손익 → `portfolio.holdings[].returnRate`
- 비중 → `portfolio.allocations[]`

## 운영 규칙
- HTML이 바뀌면 반드시 아래 3개를 같이 맞춰야 함:
  1. `templates/report.html`
  2. `site/YYYY-MM-DD/index.html` 또는 생성 로직
  3. `data/report_schema.md` + `data/schema.json`
- ETL은 최종적으로 이 구조의 JSON을 생성해야 함.
- 비어 있는 데이터는 빈 배열/빈 문자열로 유지해 UI가 깨지지 않게 해야 함.
