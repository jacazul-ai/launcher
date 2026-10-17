import unittest
from unittest.mock import MagicMock, patch

from jacazul.cli.flow import FlowManager


class TicketLinkTest(unittest.TestCase):
    """Linking a task to a ticket never changes the state of other tasks."""

    def test_ticket_does_not_sync_the_issue(self):
        # sync_issue closes every pending task of a CLOSED issue, so linking
        # three tasks to a closed issue closed the first two.
        broker = MagicMock()
        with (
            patch("jacazul.cli.flow.TaskWrapper"),
            patch("jacazul.cli.flow.FocusManager"),
            patch("jacazul.cli.flow.CacheManager"),
            patch(
                "jacazul.cli.flow.BrokerFactory.get_broker",
                return_value=broker,
            ),
            patch("sys.stdout"),
        ):
            flow = FlowManager()
            flow.tw.export.return_value = [
                {"uuid": "deadbeef-1234", "status": "pending"}
            ]
            flow.resolve_uuid = MagicMock(return_value="deadbeef-1234")
            flow.cmd_ticket("deadbeef", "#135")

        broker.sync_issue.assert_not_called()
        flow.tw.run.assert_any_call(
            ["deadbeef-1234", "modify", "externalid:#135"]
        )


if __name__ == "__main__":
    unittest.main()
