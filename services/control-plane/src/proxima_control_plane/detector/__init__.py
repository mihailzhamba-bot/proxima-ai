"""Детектор нормы SCN-001 на фактах лестницы: шаг прогона `brief` (AD-19, Story 4.1).

Читает `fact_nm_daily_current`, `dim_nm_subject_current` и - только для этапа
воронки - `fact_funnel_daily_current` под ролью `proxima_job_norm`; норма SKU и
категории - медиана 14 полных дней перед оцениваемым (D21/D27); выход - сигналы
по `contracts/signal.schema.json` v1 внутри `brief_daily.payload.signals[]` (AD-9).
Порог не применяется (решение 6а, Story 4.2/4.4): кандидат - каждое отклонение
ниже нормы, порядок - по деньгам под риском.
"""
