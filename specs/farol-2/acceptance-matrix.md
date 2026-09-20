# Matriz de aceite Farol 2.0

Gerado por `scripts/check_acceptance_matrix.py`. Cada AC deriva seu estado
dos tickets cobertos por `acceptance_refs` (excluindo o guarda-chuva
`TK-020`). `verified` exige que todo ticket cobertor
esteja `verified`; qualquer cobertura `in_progress` mantém o AC em
`in_progress`, com o blocker registrado no ticket/evidência.

Resumo: {"verified": 33}

Sem ticket dedicado (só o guarda-chuva): nenhum

| AC | Tickets cobertores | Estado | Evidência |
| --- | --- | --- | --- |
| AC-001 | TK-002, TK-020 | verified | specs/farol-2/evidence/TK-002.md, specs/farol-2/evidence/TK-020.md |
| AC-002 | TK-002, TK-016, TK-020 | verified | specs/farol-2/evidence/TK-002.md, specs/farol-2/evidence/TK-016.md, specs/farol-2/evidence/TK-020.md |
| AC-003 | TK-002, TK-020 | verified | specs/farol-2/evidence/TK-002.md, specs/farol-2/evidence/TK-020.md |
| AC-004 | TK-004, TK-005, TK-006, TK-007, TK-008, TK-020 | verified | specs/farol-2/evidence/TK-004.md, specs/farol-2/evidence/TK-005.md, specs/farol-2/evidence/TK-006.md, specs/farol-2/evidence/TK-007.md, specs/farol-2/evidence/TK-008.md, specs/farol-2/evidence/TK-020.md |
| AC-005 | TK-006, TK-018, TK-020 | verified | specs/farol-2/evidence/TK-006.md, specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-020.md |
| AC-006 | TK-001, TK-007, TK-018, TK-020 | verified | specs/farol-2/evidence/TK-001.md, specs/farol-2/evidence/TK-007.md, specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-020.md |
| AC-007 | TK-008, TK-018, TK-020 | verified | specs/farol-2/evidence/TK-008.md, specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-020.md |
| AC-008 | TK-009, TK-018, TK-020 | verified | specs/farol-2/evidence/TK-009.md, specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-020.md |
| AC-009 | TK-004, TK-005, TK-006, TK-007, TK-008, TK-009, TK-020 | verified | specs/farol-2/evidence/TK-004.md, specs/farol-2/evidence/TK-005.md, specs/farol-2/evidence/TK-006.md, specs/farol-2/evidence/TK-007.md, specs/farol-2/evidence/TK-008.md, specs/farol-2/evidence/TK-009.md, specs/farol-2/evidence/TK-020.md |
| AC-010 | TK-010, TK-020 | verified | specs/farol-2/evidence/TK-010.md, specs/farol-2/evidence/TK-020.md |
| AC-011 | TK-010, TK-011, TK-020 | verified | specs/farol-2/evidence/TK-010.md, specs/farol-2/evidence/TK-011.md, specs/farol-2/evidence/TK-020.md |
| AC-012 | TK-011, TK-020 | verified | specs/farol-2/evidence/TK-011.md, specs/farol-2/evidence/TK-020.md |
| AC-013 | TK-004, TK-011, TK-018, TK-020 | verified | specs/farol-2/evidence/TK-004.md, specs/farol-2/evidence/TK-011.md, specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-020.md |
| AC-014 | TK-011, TK-020 | verified | specs/farol-2/evidence/TK-011.md, specs/farol-2/evidence/TK-020.md |
| AC-015 | TK-012, TK-014, TK-020 | verified | specs/farol-2/evidence/TK-012.md, specs/farol-2/evidence/TK-014.md, specs/farol-2/evidence/TK-020.md |
| AC-016 | TK-012, TK-014, TK-018, TK-020 | verified | specs/farol-2/evidence/TK-012.md, specs/farol-2/evidence/TK-014.md, specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-020.md |
| AC-017 | TK-012, TK-014, TK-020 | verified | specs/farol-2/evidence/TK-012.md, specs/farol-2/evidence/TK-014.md, specs/farol-2/evidence/TK-020.md |
| AC-018 | TK-011, TK-012, TK-020 | verified | specs/farol-2/evidence/TK-011.md, specs/farol-2/evidence/TK-012.md, specs/farol-2/evidence/TK-020.md |
| AC-019 | TK-001, TK-013, TK-020 | verified | specs/farol-2/evidence/TK-001.md, specs/farol-2/evidence/TK-013.md, specs/farol-2/evidence/TK-020.md |
| AC-020 | TK-001, TK-003, TK-013, TK-014, TK-018, TK-020 | verified | specs/farol-2/evidence/TK-001.md, specs/farol-2/evidence/TK-003.md, specs/farol-2/evidence/TK-013.md, specs/farol-2/evidence/TK-014.md, specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-020.md |
| AC-021 | TK-003, TK-004, TK-013, TK-014, TK-019, TK-020 | verified | specs/farol-2/evidence/TK-003.md, specs/farol-2/evidence/TK-004.md, specs/farol-2/evidence/TK-013.md, specs/farol-2/evidence/TK-014.md, specs/farol-2/evidence/TK-019.md, specs/farol-2/evidence/TK-020.md |
| AC-022 | TK-003, TK-013, TK-020 | verified | specs/farol-2/evidence/TK-003.md, specs/farol-2/evidence/TK-013.md, specs/farol-2/evidence/TK-020.md |
| AC-023 | TK-003, TK-013, TK-020 | verified | specs/farol-2/evidence/TK-003.md, specs/farol-2/evidence/TK-013.md, specs/farol-2/evidence/TK-020.md |
| AC-024 | TK-015, TK-020 | verified | specs/farol-2/evidence/TK-015.md, specs/farol-2/evidence/TK-020.md |
| AC-025 | TK-010, TK-015, TK-020 | verified | specs/farol-2/evidence/TK-010.md, specs/farol-2/evidence/TK-015.md, specs/farol-2/evidence/TK-020.md |
| AC-026 | TK-015, TK-018, TK-020 | verified | specs/farol-2/evidence/TK-015.md, specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-020.md |
| AC-027 | TK-002, TK-016, TK-017, TK-019, TK-020 | verified | specs/farol-2/evidence/TK-002.md, specs/farol-2/evidence/TK-016.md, specs/farol-2/evidence/TK-017.md, specs/farol-2/evidence/TK-019.md, specs/farol-2/evidence/TK-020.md |
| AC-028 | TK-017, TK-020 | verified | specs/farol-2/evidence/TK-017.md, specs/farol-2/evidence/TK-020.md |
| AC-029 | TK-018, TK-019, TK-020 | verified | specs/farol-2/evidence/TK-018.md, specs/farol-2/evidence/TK-019.md, specs/farol-2/evidence/TK-020.md |
| AC-030 | TK-005, TK-007, TK-020 | verified | specs/farol-2/evidence/TK-005.md, specs/farol-2/evidence/TK-007.md, specs/farol-2/evidence/TK-020.md |
| AC-031 | TK-020, TK-021 | verified | specs/farol-2/evidence/TK-020.md, specs/farol-2/evidence/TK-021.md |
| AC-032 | TK-005, TK-020 | verified | specs/farol-2/evidence/TK-005.md, specs/farol-2/evidence/TK-020.md |
| AC-033 | TK-005, TK-009, TK-020 | verified | specs/farol-2/evidence/TK-005.md, specs/farol-2/evidence/TK-009.md, specs/farol-2/evidence/TK-020.md |
