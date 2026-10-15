"""Optional stdlib HTTP server exposing list_processes / run_process."""

from __future__ import annotations

from mcp_plugins.processes import build_process_tools
from mcp_plugins.template.server import main as template_main


def main() -> None:
    template_main(plugin_name="processes", tools=build_process_tools(), port=8093)


if __name__ == "__main__":
    main()
