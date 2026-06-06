"""Command table for the ``az reaper`` command group."""


def load_command_table(self, _args):
    with self.command_group("reaper") as g:
        g.custom_command("list", "reaper_list")
        g.custom_command("reap", "reaper_reap")
