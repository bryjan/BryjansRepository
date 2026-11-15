"""Small input helpers shared by interactive command modules."""


def read_nonempty(prompt):
    """Read a trimmed command or menu value, rejecting blank input."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print()
