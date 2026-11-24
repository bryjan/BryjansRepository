"""Paginated objective and squad-request menu beside the strategic map."""

import textwrap

from .. import objectives
from ..ui import tactical as pv


def _page(match, title, lines, page, prompt):
    wrapped = [part for line in lines for part in (textwrap.wrap(line, pv.SIDE_PANEL_WIDTH) or [""])]
    size = max(1, match.windowHeight - 3)
    pages = max(1, (len(wrapped) + size - 1) // size)
    page = max(0, min(page, pages - 1))
    pv.print_overview(match, command_text=prompt,
                      right_panel=(f"{title} {page + 1}/{pages}", wrapped[page * size:(page + 1) * size]))
    return page


def objectiveMenu(match):
    page = 0
    while True:
        entries = objectives.items(match, match.pov.squad)
        lines = [f"Requests addressed to: {match.pov.squad.name}", "Main objectives, then squad requests:"]
        lines.extend(f"'{index}' {entry.title} [{entry.status}]" for index, entry in enumerate(entries, 1))
        page = _page(match, "OBJECTIVES", lines, page,
                     "Objectives: enter a number for details | 'n' next page | 'p' previous | 'x' back")
        choice = input("Objectives: ").strip().lower()
        if choice in {"", "x"}:
            return
        if choice in {"n", "p"}:
            page += 1 if choice == "n" else -1
        elif choice.isdigit() and 1 <= int(choice) <= len(entries):
            _details(match, entries[int(choice) - 1])


def _details(match, item):
    page = 0
    while True:
        extra = " | 'd' dismiss request" if item.request is not None else ""
        page = _page(match, "OBJECTIVE DETAILS", [item.title, f"Status: {item.status}", *item.details], page,
                     f"Details: 'n' next page | 'p' previous{extra} | 'x' back")
        choice = input("Objective details: ").strip().lower()
        if choice in {"", "x"}:
            return
        if choice == "d" and item.request is not None:
            item.request.dismissed = True
            return
        if choice in {"n", "p"}:
            page += 1 if choice == "n" else -1
