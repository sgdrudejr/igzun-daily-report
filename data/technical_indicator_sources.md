# 기술지표 대체 데이터 소스

현재 기본 원칙은 Yahoo Finance 기반 계산임.
부족한 지표가 있으면 아래 소스를 우선 검토함.

## 1. Alpha Vantage
- 제공 가능: RSI, SMA, EMA, MACD, ADX 등 다수 기술지표
- 방식: API
- 장점: 지표 엔드포인트가 직접 존재함
- 단점: 무료 호출 제한 강함

## 2. Twelve Data
- 제공 가능: RSI, MACD, EMA, SMA, ADX, Stochastic 등
- 방식: API
- 장점: 기술지표 API가 직관적
- 단점: 무료 제한 존재

## 3. Stooq + 로컬 계산
- 제공 가능: 가격 시계열 기반으로 RSI/ADX/이평선/모멘텀 직접 계산 가능
- 방식: CSV 다운로드 + 로컬 pandas 계산
- 장점: 외부 지표 API 의존도 낮음
- 단점: 구현 필요

## 4. Polygon / Finnhub
- 제공 가능: 가격/거래량/일부 고급 데이터
- 방식: API
- 장점: 품질 우수
- 단점: 유료 또는 제한 큼

## 권장 우선순위
1. Yahoo Finance 가격 시계열 확보
2. 로컬 계산으로 RSI/SMA/EMA/Momentum/Volatility 구현
3. ADX 등 부족 지표는 Alpha Vantage 또는 Twelve Data 보강
