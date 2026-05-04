"""Tests for batch_ops identity unlinking and detached-user sweep."""

from unittest.mock import MagicMock, patch

from src.deletepy.core.auth0_client import APIResponse, Auth0Client
from src.deletepy.operations.batch_ops import (
    _handle_identity_unlinking,
    _lookup_and_delete_detached_user,
    _process_single_identity_unlink,
    _sweep_detached_social_users,
)


def _make_client() -> MagicMock:
    return MagicMock(spec=Auth0Client)


def _empty_results() -> dict[str, int]:
    return {
        "unlinked_count": 0,
        "failed_unlinks": 0,
        "orphaned_users_deleted": 0,
        "orphaned_users_failed": 0,
    }


# ---------- _lookup_and_delete_detached_user ----------


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_found(mock_delete_user):
    """200 → delete invoked and orphaned counter incremented."""
    client = _make_client()
    client.get_user.return_value = APIResponse(
        success=True, status_code=200, data={"user_id": "facebook|123"}
    )
    mock_delete_user.return_value = True
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", client, results)

    client.get_user.assert_called_once_with("facebook%7C123")
    mock_delete_user.assert_called_once_with("facebook|123", client)
    assert results["orphaned_users_deleted"] == 1
    assert results["orphaned_users_failed"] == 0


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_not_found(mock_delete_user):
    """404 → silent no-op; no delete attempted, no failure counted."""
    client = _make_client()
    client.get_user.return_value = APIResponse(
        success=False, status_code=404, error_message="not found"
    )
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", client, results)

    mock_delete_user.assert_not_called()
    assert results["orphaned_users_deleted"] == 0
    assert results["orphaned_users_failed"] == 0


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_lookup_error(mock_delete_user):
    """Non-404 lookup error → counted as failure, no delete attempted."""
    client = _make_client()
    client.get_user.return_value = APIResponse(
        success=False, status_code=500, error_message="server error"
    )
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", client, results)

    mock_delete_user.assert_not_called()
    assert results["orphaned_users_deleted"] == 0
    assert results["orphaned_users_failed"] == 1


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_delete_fails(mock_delete_user):
    """Found but delete_user returns False → counted as failed."""
    client = _make_client()
    client.get_user.return_value = APIResponse(
        success=True, status_code=200, data={"user_id": "facebook|123"}
    )
    mock_delete_user.return_value = False
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", client, results)

    assert results["orphaned_users_deleted"] == 0
    assert results["orphaned_users_failed"] == 1


# ---------- _sweep_detached_social_users ----------


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_sweep_mixed_results(mock_delete_user):
    """Sweep handles mix of found, not-found, and error cases."""
    client = _make_client()
    client.get_user.side_effect = [
        APIResponse(success=True, status_code=200, data={"user_id": "facebook|1"}),
        APIResponse(success=False, status_code=404),
        APIResponse(success=True, status_code=200, data={"user_id": "facebook|3"}),
    ]
    mock_delete_user.return_value = True
    results = _empty_results()

    _sweep_detached_social_users(
        [("facebook", "1"), ("facebook", "2"), ("facebook", "3")],
        client,
        results,
    )

    assert client.get_user.call_count == 3
    assert mock_delete_user.call_count == 2
    assert results["orphaned_users_deleted"] == 2
    assert results["orphaned_users_failed"] == 0


# ---------- _process_single_identity_unlink ----------


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
def test_process_single_identity_unlink_success_appends_target(
    mock_orphan_check, mock_unlink
):
    """Successful unlink appends (connection, social_id) to detached_targets."""
    client = _make_client()
    mock_unlink.return_value = True
    results = _empty_results()
    targets: list[tuple[str, str]] = []
    user = {
        "user_id": "auth0|main",
        "matching_connection": "facebook",
        "social_id": "fb123",
    }

    _process_single_identity_unlink(user, client, results, targets)

    assert results["unlinked_count"] == 1
    assert results["failed_unlinks"] == 0
    assert targets == [("facebook", "fb123")]
    mock_orphan_check.assert_called_once_with("auth0|main", client, results)


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
def test_process_single_identity_unlink_failure_no_target(
    mock_orphan_check, mock_unlink
):
    """Failed unlink does not append a sweep target or call orphan check."""
    client = _make_client()
    mock_unlink.return_value = False
    results = _empty_results()
    targets: list[tuple[str, str]] = []
    user = {
        "user_id": "auth0|main",
        "matching_connection": "facebook",
        "social_id": "fb123",
    }

    _process_single_identity_unlink(user, client, results, targets)

    assert results["unlinked_count"] == 0
    assert results["failed_unlinks"] == 1
    assert targets == []
    mock_orphan_check.assert_not_called()


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
def test_process_single_identity_unlink_exception(mock_unlink):
    """Exception during unlink is caught and counted as failed."""
    client = _make_client()
    mock_unlink.side_effect = RuntimeError("boom")
    results = _empty_results()
    targets: list[tuple[str, str]] = []
    user = {
        "user_id": "auth0|main",
        "matching_connection": "facebook",
        "social_id": "fb123",
    }

    _process_single_identity_unlink(user, client, results, targets)

    assert results["failed_unlinks"] == 1
    assert targets == []


# ---------- _handle_identity_unlinking ----------


def test_handle_identity_unlinking_empty_returns_early():
    """Empty input returns zeros without invoking anything."""
    client = _make_client()

    results = _handle_identity_unlinking([], client)

    assert results == _empty_results()
    client.get_user.assert_not_called()


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
@patch("src.deletepy.operations.batch_ops.delete_user")
def test_handle_identity_unlinking_runs_sweep_after_loop(
    mock_delete_user, mock_orphan_check, mock_unlink
):
    """Sweep runs after the unlink loop and finds detached users via GET-by-id."""
    client = _make_client()
    mock_unlink.return_value = True
    mock_delete_user.return_value = True
    # During the sweep, the first detached user exists (200), the second is
    # already gone (404) — exactly the scenario the prior search-based code
    # missed when Auth0's index lagged behind.
    client.get_user.side_effect = [
        APIResponse(success=True, status_code=200, data={"user_id": "facebook|fb1"}),
        APIResponse(success=False, status_code=404),
    ]
    identities = [
        {
            "user_id": "auth0|main1",
            "matching_connection": "facebook",
            "social_id": "fb1",
        },
        {
            "user_id": "auth0|main2",
            "matching_connection": "facebook",
            "social_id": "fb2",
        },
    ]

    results = _handle_identity_unlinking(identities, client)

    assert results["unlinked_count"] == 2
    assert results["failed_unlinks"] == 0
    assert results["orphaned_users_deleted"] == 1
    assert results["orphaned_users_failed"] == 0
    # Sweep ran exactly once per successful unlink (no per-unlink search calls)
    assert client.get_user.call_count == 2
    mock_delete_user.assert_called_once_with("facebook|fb1", client)


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
@patch("src.deletepy.operations.batch_ops.delete_user")
def test_handle_identity_unlinking_skips_sweep_for_failed_unlinks(
    mock_delete_user, mock_orphan_check, mock_unlink
):
    """Only successful unlinks become sweep targets."""
    client = _make_client()
    mock_unlink.side_effect = [True, False]  # first succeeds, second fails
    client.get_user.return_value = APIResponse(success=False, status_code=404)
    identities = [
        {
            "user_id": "auth0|main1",
            "matching_connection": "facebook",
            "social_id": "fb1",
        },
        {
            "user_id": "auth0|main2",
            "matching_connection": "facebook",
            "social_id": "fb2",
        },
    ]

    results = _handle_identity_unlinking(identities, client)

    assert results["unlinked_count"] == 1
    assert results["failed_unlinks"] == 1
    # Only one sweep lookup, for the successful unlink
    assert client.get_user.call_count == 1
    mock_delete_user.assert_not_called()
