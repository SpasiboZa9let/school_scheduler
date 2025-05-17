# school_scheduler/logic/backtracking.py
import time
from copy import deepcopy
from typing import Dict, List, Tuple, Set

from models.constants import days_of_week, periods
from utils.helpers import (
    normalize_text,
    calculate_teacher_gaps,
)

# ------------------------- тонкие настройки ---------------------- #
DEFAULT_TEACHER_DAILY_LIMIT = 6
DEFAULT_CLASS_DAILY_LIMIT = 7
DEFAULT_MAX_SAME_SUBJECT_PER_DAY = 2
DEFAULT_TIMEOUT = 60  # секунд


# --------------------------- ядро -------------------------------- #
def _state_key(i: int, schedule: dict, used: Set[Tuple[str, str]]) -> Tuple:
    """Хэш-ключ для мemoization (перебор)."""
    assignments = []
    for d in sorted(schedule.keys()):
        for p in periods:
            if p in schedule[d]:
                les = schedule[d][p]
                assignments.append((d, p, les.get("subject", ""), les.get("teacher", "")))
    return (i, tuple(assignments), tuple(sorted(used)))


def find_best_schedule(
    subjects: List[str],
    teacher_map: Dict[str, str],
    *,
    teacher_daily_limit: int = DEFAULT_TEACHER_DAILY_LIMIT,
    class_daily_limit: int = DEFAULT_CLASS_DAILY_LIMIT,
    max_same_subject_per_day: int = DEFAULT_MAX_SAME_SUBJECT_PER_DAY,
    initial_schedule: Dict[str, dict] | None = None,
    initial_used_slots: Set[Tuple[str, str]] | None = None,
    global_used: Dict[Tuple[str, str], set] | None = None,
    max_time: int = DEFAULT_TIMEOUT,
) -> Tuple[dict, int | None]:
    """
    Возвращает (best_schedule, gap_score). Если расписания нет — ({}, None).
    """
    start = time.time()
    best_schedule = None
    best_gap = float("inf")

    schedule = initial_schedule or {d: {} for d in days_of_week}
    used = set(initial_used_slots or [])
    global_used = global_used or {}
    cache: Dict[Tuple, int] = {}

    slots = [(d, p) for d in days_of_week for p in periods]

    def backtrack(i: int) -> int | None:
        nonlocal best_schedule, best_gap

        # тайм-аут
        if time.time() - start > max_time:
            return None

        # все предметы расставили
        if i == len(subjects):
            gaps = sum(calculate_teacher_gaps(schedule, periods, days_of_week).values())
            if gaps < best_gap:
                best_gap = gaps
                best_schedule = deepcopy(schedule)
            return gaps

        key = _state_key(i, schedule, used)
        if key in cache:
            return cache[key]

        subj = subjects[i]
        teacher = teacher_map.get(subj) or "не назначен"

        current_min = float("inf")
        for day, period in slots:
            if (day, period) in used:
                continue
            #  ⬇️  ограничения: макс. уроков в день у класса
            if len(schedule[day]) >= class_daily_limit:
                continue
            #  ⬇️  ограничения: макс. этого предмета в день
            subj_cnt = sum(
                1 for les in schedule[day].values() if les.get("subject") == subj
            )
            if subj_cnt >= max_same_subject_per_day:
                continue
            #  ⬇️  ограничения: учитель не должен вести два уpока одновременно
            if teacher != "не назначен" and teacher in global_used.get((day, period), set()):
                continue
            #  ⬇️  ограничения: суточная нагрузка учителя
            if teacher != "не назначен":
                t_daily_cnt = sum(
                    1
                    for les in schedule[day].values()
                    if les.get("teacher") == teacher
                )
                if t_daily_cnt >= teacher_daily_limit:
                    continue

            #  ► ставим урок
            schedule[day][period] = {"subject": subj, "teacher": teacher}
            used.add((day, period))
            if teacher != "не назначен":
                global_used.setdefault((day, period), set()).add(teacher)

            result = backtrack(i + 1)
            if result is not None and result < current_min:
                current_min = result

            #  ◄ снимаем
            used.remove((day, period))
            del schedule[day][period]
            if teacher != "не назначен":
                global_used[(day, period)].remove(teacher)
                if not global_used[(day, period)]:
                    del global_used[(day, period)]

        cache[key] = current_min
        return current_min

    backtrack(0)
    return best_schedule or {}, (None if best_schedule is None else best_gap)


# ----------------- обёртка на класс и всю школу ------------------ #
def find_optimal_schedule_for_class(
    class_record: dict,
    teachers_dict: Dict[str, dict],
    global_used: Dict[Tuple[str, str], set],
    *,
    class_daily_limit: int = DEFAULT_CLASS_DAILY_LIMIT,
) -> Tuple[dict, int | None]:
    """
    Формирует список предметов, маппинг → учитель и запускает find_best_schedule.
    """
    from models.constants import subject_list  # локальный импорт, чтобы избежать циклов

    class_number = normalize_text(class_record["Номер класса"])
    raw_subjects = class_record.get("Список предметов", "")
    subjects: List[str] = []
    for s, cnt in (parse := parse_subjects(raw_subjects)).items():
        subjects.extend([s] * cnt)

    # эвристика: сначала предметы с меньшим количеством доступных учителей
    def teacher_candidates(subj: str) -> int:
        return sum(
            1
            for data in teachers_dict.values()
            if normalize_text(subj) in normalize_text(data["Специализация"])
        )

    subjects.sort(key=teacher_candidates)

    teacher_map = {}
    for subj in subjects:
        for tname, tdata in teachers_dict.items():
            if normalize_text(subj) in normalize_text(tdata["Специализация"]):
                teacher_map[subj] = tname
                break
        else:
            teacher_map[subj] = None  # «не назначен»

    # фиксированные слоты
    schedule0 = {d: {} for d in days_of_week}
    used0: Set[Tuple[str, str]] = set()
    for fs in class_record.get("fixed_slots", []):
        d = normalize_text(fs["day"])
        p = normalize_text(fs["period"])
        schedule0[d][p] = {
            "subject": normalize_text(fs["subject"]),
            "teacher": normalize_text(fs.get("teacher", "")),
        }
        used0.add((d, p))
        if schedule0[d][p]["teacher"]:
            global_used.setdefault((d, p), set()).add(schedule0[d][p]["teacher"])

    return find_best_schedule(
        subjects,
        teacher_map,
        initial_schedule=schedule0,
        initial_used_slots=used0,
        global_used=global_used,
    )


def generate_global_schedule(
    class_records: List[dict],
    teachers_dict: Dict[str, dict],
) -> Dict[str, dict]:
    """
    Обходит все классы и строит их расписание, учитывая глобальные конфликты учителей.
    """
    global_used: Dict[Tuple[str, str], set] = {}
    global_schedule: Dict[str, dict] = {}

    for cr in class_records:
        cls_name = normalize_text(cr["Номер класса"])
        sch, _ = find_optimal_schedule_for_class(cr, teachers_dict, global_used)
        global_schedule[cls_name] = sch

    return global_schedule
