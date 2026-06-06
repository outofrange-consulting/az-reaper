"""The ``reaper`` Azure CLI extension.

Adds ``az reaper`` -- harvest stale git worktrees across your machine, with
Azure DevOps PR-completion awareness. See :mod:`azext_reaper._reaper` for the
engine (which is azure-cli-free and independently testable).
"""

from azure.cli.core import AzCommandsLoader

import azext_reaper._help  # noqa: F401  (registers help entries on import)


class ReaperCommandsLoader(AzCommandsLoader):

    def __init__(self, cli_ctx=None):
        from azure.cli.core.commands import CliCommandType
        custom = CliCommandType(operations_tmpl="azext_reaper.custom#{}")
        super(ReaperCommandsLoader, self).__init__(
            cli_ctx=cli_ctx, custom_command_type=custom)

    def load_command_table(self, args):
        from azext_reaper.commands import load_command_table
        load_command_table(self, args)
        return self.command_table

    def load_arguments(self, command):
        from azext_reaper._params import load_arguments
        load_arguments(self, command)


COMMAND_LOADER_CLS = ReaperCommandsLoader
