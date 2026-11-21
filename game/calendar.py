"""The calendar: Pulses, Cycles, Reckons, Judgments, Duels and Turns.

A Pulse is a day. 9 Pulses (Emu ... Neu) make a Cycle, 9 Cycles a Reckon,
12 Reckons a Judgment, 4 Judgments a Duel. A Turn is the Light Duel, 4
intercalary Pulses, the Dark Duel, and 4 more intercalary Pulses: holidays
to celebrate surviving a Duel and prepare for the next.

The game counts Pulses (engine.day = 1, 2, 3...): contracts and saves use
that. This module turns that count into a date. A Pulse passes with every move
from one area to another; a completed hunt is a whole Cycle (see Engine).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Date:
    turn: int
    duel: str            # "Light Duel" / "Dark Duel"
    intercalary: int     # 0 inside a Duel; 1-4 for the holiday Pulses after it
    judgment: int = 0    # 1-4 (inside a Duel)
    reckon: int = 0      # 1-12
    cycle: int = 0       # 1-9
    pulse: str = ""      # Emu ... Neu
    pulse_number: int = 0  # 1-9

    @property
    def short(self) -> str:
        """One line: 'Light Duel: Emu, C1, R1, J1, T211' or 'Holiday 2/4 after the Light Duel, T211'."""
        if self.intercalary:
            return f"Holiday {self.intercalary}/4 after the {self.duel}, T{self.turn}"
        return f"{self.duel}: {self.pulse}, C{self.cycle}, R{self.reckon}, J{self.judgment}, T{self.turn}"

    @property
    def lines(self) -> list[str]:
        """Two short lines for the side panel (each fits in 21 characters)."""
        if self.intercalary:
            return [f"Holiday {self.intercalary}/4, T{self.turn}", f"after the {self.duel}"]
        return [f"{self.duel}: {self.pulse}", f"C{self.cycle}, R{self.reckon}, J{self.judgment}, T{self.turn}"]

    @property
    def long(self) -> str:
        if self.intercalary:
            return f"holiday Pulse {self.intercalary} of 4 after the {self.duel}, Turn {self.turn}"
        return (f"{self.pulse}, Cycle {self.cycle}, Reckon {self.reckon}, Judgment {self.judgment} "
                f"of the {self.duel}, Turn {self.turn}")


class Calendar:
    def __init__(self, path: str | Path) -> None:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        self.pulses = d["pulses"]
        self.cycles = d["cycles_per_reckon"]
        self.reckons = d["reckons_per_judgment"]
        self.judgments = d["judgments_per_duel"]
        self.intercalary = d["intercalary_pulses"]
        self.duels = d["duels"]
        self.start_turn = d.get("start_turn", 1)
        self.start_offset = d.get("start_pulse_of_turn", 1) - 1
        self.per_cycle = len(self.pulses)
        self.per_reckon = self.per_cycle * self.cycles
        self.per_judgment = self.per_reckon * self.reckons
        self.per_duel = self.per_judgment * self.judgments
        self.per_half = self.per_duel + self.intercalary          # a Duel and its holiday
        self.per_turn = self.per_half * len(self.duels)

    def date(self, day: int) -> Date:
        """The date of game day `day` (1 = the first day of the game)."""
        index = self.start_offset + day - 1
        turn = self.start_turn + index // self.per_turn
        half, i = divmod(index % self.per_turn, self.per_half)
        duel = self.duels[half]
        if i >= self.per_duel:
            return Date(turn, duel, i - self.per_duel + 1)
        return Date(turn, duel, 0,
                    judgment=i // self.per_judgment + 1,
                    reckon=i % self.per_judgment // self.per_reckon + 1,
                    cycle=i % self.per_reckon // self.per_cycle + 1,
                    pulse=self.pulses[i % self.per_cycle],
                    pulse_number=i % self.per_cycle + 1)

    def turning_point(self, day: int) -> str | None:
        """A line for the log when this day starts a Duel or its holiday."""
        d = self.date(day)
        if d.intercalary == 1:
            return f"The {d.duel} is survived. Four holiday Pulses begin."
        if not d.intercalary and (d.judgment, d.reckon, d.cycle, d.pulse_number) == (1, 1, 1, 1):
            return f"The {d.duel} of Turn {d.turn} begins."
        return None
