# school_scheduler/utils/helpers.py
import unicodedata
from typing import Dict, List, Tuple

# ------------------------ базовые строки ------------------------- #
def normalize_text(text: str) -> str:
    """
    Приводит строку к NFKC-норме, убирает пробелы по краям и переводит в lower-case.
    """
    return unicodedata.normalize("NFKC", text).strip().lower()


# --------------------- парсинг предметов ------------------------- #
def parse_subjects(raw: str) -> Dict[str, int]:
    """
    "математика:3, физика:2" → {"математика": 3, "физика": 2}
    Без числа → 1.
    """
    result: Dict[str, int] = {}
    if not raw:
        return result

    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if ":" in piece:
            subj, cnt = piece.split(":", 1)
            result[normalize_text(subj)] = int(cnt)
        else:
            result[normalize_text(piece)] = 1
    return result


# ----------------------- фикс-слоты ------------------------------ #
def validate_fixed_slots(fixed_slots: List[dict]) -> List[dict]:
    """
    Проверяет, что нет дублей (день+урок). Логирует конфликт, возвращает список как есть.
    """
    seen = {}
    for fs in fixed_slots:
        key = (normalize_text(fs.get("day", "")), normalize_text(fs.get("period", "")))
        if key in seen:
            # вы можете подключить logging; пока просто print
            print(f"[validate_fixed_slots] конфликт для {key}: {seen[key]} vs {fs}")
        else:
            seen[key] = fs
    return fixed_slots


# -------------------- подсчёт «окон» учителя --------------------- #
def calculate_teacher_gaps(schedule: dict, periods: List[str], days_of_week: List[str]) -> Dict[str, int]:
    teacher_gaps: Dict[str, int] = {}
    for day in days_of_week:
        day_sched = schedule.get(day, {})
        per_indices: Dict[str, List[int]] = {}
        for period, lesson in day_sched.items():
            teacher = lesson.get("teacher", "")
            if teacher:
                per_indices.setdefault(teacher, []).append(periods.index(period))
        for t, idx_list in per_indices.items():
            idx_list.sort()
            gaps = sum(idx_list[i] - idx_list[i - 1] - 1 for i in range(1, len(idx_list)))
            teacher_gaps[t] = teacher_gaps.get(t, 0) + gaps
    return teacher_gaps


# ------------------ распределение уроков ------------------------ #
def count_lessons_in_schedule(global_schedule: dict,
                              periods: List[str],
                              days_of_week: List[str]) -> Dict[str, Dict[str, int]]:
    """
    Возвращает {класс: {предмет: кол-во}} по всему расписанию.
    """
    out: Dict[str, Dict[str, int]] = {}
    for cls, sched in global_schedule.items():
        subj_counts: Dict[str, int] = {}
        for day in days_of_week:
            for period in periods:
                subject = sched.get(day, {}).get(period, {}).get("subject", "")
                if subject:
                    subj_counts[subject] = subj_counts.get(subject, 0) + 1
        out[cls] = subj_counts
    return out
