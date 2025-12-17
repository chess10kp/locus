from typing import final
import os


@final
class HabitManager:
    def __init__(self):
        HOME = os.path.expanduser("~")
        CACHE_DIR = f"{HOME}/.cache/dashboard"
        self.habit_file = os.path.join(CACHE_DIR, "habit_cache")
        self.habits = self.read_habits()

    def read_habits(self) -> list[dict[str, str | int | list[int]]]:
        # Initialize the habit file if it doesn't exist
        if not os.path.exists(self.habit_file):
            with open(self.habit_file or self.get_habit_file(), "w") as file:
                _ = file.write("")  # Create an empty file

        habits: list[dict[str, str | int | list[int]]] = []
        with open(self.habit_file, "r") as file:
            all_parts = map(str.split, file.readlines())
            for parts in all_parts:
                habit_name, best_streak, current_streak, latest_date, week = parts
                habits.append(
                    {
                        "name": habit_name,
                        "best_streak": int(best_streak),
                        "current_streak": int(current_streak),
                        "latest_date": latest_date,
                        "week": list(map(int, week.split(","))),
                    }
                )

        return habits

    def get_habits(self) -> list[dict[str, str | int | list[int]]]:
        return self.habits

    def get_habit_file(self) -> str:
        return self.habit_file

    def update_habits(self, habits: str) -> int:
        with open(self.habit_file, "w") as file:
            return file.write(habits)

    def add_habit(self, habit: str) -> int:
        with open(self.habit_file, "a") as file:
            return file.write(habit)
