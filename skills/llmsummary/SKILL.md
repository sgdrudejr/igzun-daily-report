---
name: llmsummary
description: Use this skill whenever the user asks for a deep research style Korean market summary, a manual LLM summary, today's upgraded investment briefing, a rebalancing review, or a "what should I do now?" interpretation using the accumulated data inside igzun-daily-report without paid API calls. This skill is for human-in-the-loop analysis: it packages the latest local market data, horizon summaries, portfolio state, valuation, signals, and collected documents into a brief and then produces a richer Korean analyst-style report.
---

# Manual Deep Summary

This skill is for the semi-automatic workflow:

- daily data collection and analysis already run automatically
- a human explicitly asks for a richer summary
- Codex or Claude reads the local accumulated data and writes the final Korean deep analysis

## Workflow

1. Use `/Users/seo/igzun-daily-report` as the workspace root.
2. Decide the target date.
If the user did not specify a date, use the latest available date.
3. Run:

```bash
source /Users/seo/igzun-daily-report/.venv/bin/activate && \
python /Users/seo/igzun-daily-report/scripts/build_manual_summary_brief.py --date YYYY-MM-DD --base-dir /Users/seo/igzun-daily-report
```

4. Read the generated brief:

```text
/Users/seo/igzun-daily-report/data/manual_summary/YYYY-MM-DD.md
```

5. If the user wants more depth, also inspect:

```text
/Users/seo/igzun-daily-report/data/research_context/YYYY-MM-DD.json
/Users/seo/igzun-daily-report/site/YYYY-MM-DD/result.json
/Users/seo/igzun-daily-report/data/valuation/YYYY-MM-DD.json
/Users/seo/igzun-daily-report/data/signals/YYYY-MM-DD.json
/Users/seo/igzun-daily-report/site/horizon_index.json
```

## Output Rules

- Write in Korean.
- Do not produce a shallow article summary.
- Separate `1일 / 1주 / 1개월 / 3개월 / 6개월` interpretations.
- Tie market interpretation to portfolio action.
- Include `ISA / 토스증권 / 연금저축` account-specific action points when relevant.
- Explain whether the user should buy now, wait, reduce, or split-buy.
- Use accumulated evidence, not just same-day headlines.
- Mention source groups naturally when useful, for example `연준 연설`, `네이버 리서치`, `OpenDART`, `FRED`, `ECOS`.

## Recommended Response Shape

1. 시장 총평
2. 단기 대응
3. 중기 전략
4. 계좌별 액션 플랜
5. ETF/섹터 아이디어
6. 가장 중요한 리스크와 확인 포인트

## Guardrails

- Do not claim that a paid LLM API generated the result if this workflow is manual.
- Prefer the generated manual brief over ad hoc file hunting.
- If numbers conflict, trust the latest `site/YYYY-MM-DD/result.json` and `data/research_context/YYYY-MM-DD.json` first.
