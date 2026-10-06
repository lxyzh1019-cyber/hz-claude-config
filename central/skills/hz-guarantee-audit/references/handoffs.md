# Hand-off boundaries

(v3.1.30: names follow the current account skills; hz-outcome-audit, hz-web-app-audit, hz-task-planner and hz-sql-excel-auditor were merged into hz-reviewer and hz-planner.)

| Situation after the grade | Hand to | Why not here |
|---|---|---|
| The question is "has this been broken across every version?" or the artifact has ≥3 versions | hz-reviewer (History mode) | Trajectory analysis, no-build rule, silent-passenger check live there |
| User now wants the change made | hz-plan-regression-guard | Manifest extraction and regression table are its job |
| Grade found Broken/Assumed items inside HTML/JS (listeners, sync, dead code, deploy safety) | hz-reviewer (web-app checklist) | Stack-specific runtime traps, deep mode |
| Fix is large or multi-file | hz-planner | Model, effort, chunking |
| SQL/VBA/Excel internals | hz-reviewer (SQL and Excel checklist) | Dialect-specific performance work |

State the hand-off in one line. Do not run the specialist's full procedure inside this skill.
