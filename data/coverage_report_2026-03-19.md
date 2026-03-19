# 2026-03-19 데이터 커버리지 보고

- 실제 계좌 원본(보유종목별 실현/평가손익, 비중)이 없어 portfolio.holdings/weeklyReview 일부를 모델 기반으로 채움
- 뉴스/리포트 요약 본문 추출이 비어 있는 원문이 많아 newsList.summary 일부는 placeholder로 채움
- 1주, 3개월, 1년 기간 데이터는 아직 미생성
- 개별 종목 지표(RSI, MACD 등)의 실제 계산 원본이 없어 indicators 일부는 규칙 기반 문구로 대체
- ETF ranking 점수는 정식 팩터 모델이 아니라 현재 원문 테마 강도 기반 임시 점수임
