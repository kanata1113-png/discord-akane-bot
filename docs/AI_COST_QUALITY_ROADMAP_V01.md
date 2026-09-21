# AI Cost & Quality Roadmap v0.1

Implemented on the Response Style branch:

1. Response Style v0.1 — Luna ~420 / Terra ~840 / Sol ~1680 Japanese characters.
2. Output Budget v0.2 — model/detail-aware token ceilings.
3. Detail Intent — compact/default/expanded detection independent of routing.
4. Sol Promotion Gate v0.2 — Sol requires explicit deep-complexity evidence; otherwise demote to Terra.
5. Real Cost Telemetry — metadata-only actual token usage when the Responses API exposes usage.
6. Cost Dashboard — in-memory bounded aggregate for operator visibility; no message bodies or identity data.
7. Quality Regression Benchmark — fixed routing/detail fixtures for repeatable CI/replay.

Safety principles:
- character targets are soft; no destructive text truncation;
- explicit user format/detail requests take precedence;
- no online self-modification;
- no prompt/message body in cost telemetry;
- database/schema remain unchanged;
- provider currency pricing is not invented: dashboard reports actual token counts and calibrated relative cost units.
