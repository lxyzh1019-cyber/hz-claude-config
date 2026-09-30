# Hand-off boundaries

| Situation after the grade | Hand to | Why not here |
|---|---|---|
| The question is "has this been broken across every version?" or the artifact has ≥3 versions | hz-outcome-audit | Trajectory analysis, no-build rule, silent-passenger check live there |
| User now wants the change made | hz-plan-regression-guard | Manifest extraction and regression table are its job |
| Grade found Broken/Assumed items inside HTML/JS (listeners, sync, dead code, deploy safety) | hz-web-app-audit | Stack-specific runtime traps, deep mode |
| Fix is large or multi-file | hz-task-planner | Model, effort, chunking |
| SQL/VBA/Excel internals | hz-sql-excel-auditor | Dialect-specific performance work |

State the hand-off in one line. Do not run the specialist's full procedure inside this skill.
