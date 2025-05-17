# school_scheduler/logic/__init__.py
from .backtracking import generate_global_schedule, find_optimal_schedule_for_class
from .backtracking import DEFAULT_CLASS_DAILY_LIMIT, DEFAULT_TEACHER_DAILY_LIMIT
from .ortools_solver import solve_schedule_ortools   # добавите файл позже

__all__ = [
    "generate_global_schedule",
    "find_optimal_schedule_for_class",
    "solve_schedule_ortools",
    "DEFAULT_CLASS_DAILY_LIMIT",
    "DEFAULT_TEACHER_DAILY_LIMIT",
]
