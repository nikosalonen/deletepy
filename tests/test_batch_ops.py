"""Tests for batch_ops identity unlinking and detached-user sweep."""

from unittest.mock import patch

from src.deletepy.core.auth0_client import APIResponse
from src.deletepy.operations.batch_ops import (
    _delete_orphaned_user_if_empty,
    _handle_identity_unlinking,
    _lookup_and_delete_detached_user,
    _process_single_identity_unlink,
    _sweep_detached_social_users,
)


def _empty_results() -> dict[str, int]:
    return {
        "unlinked_count": 0,
        "failed_unlinks": 0,
        "orphaned_users_deleted": 0,
        "orphaned_users_failed": 0,
        "orphaned_users_lookup_failed": 0,
    }


# ---------- _lookup_and_delete_detached_user ----------


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_found(mock_delete_user, mock_client):
    """200 → delete invoked and orphaned counter incremented."""
    mock_client.get_user.return_value = APIResponse(
        success=True, status_code=200, data={"user_id": "facebook|123"}
    )
    mock_delete_user.return_value = True
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", mock_client, results)

    mock_client.get_user.assert_called_once_with("facebook%7C123")
    mock_delete_user.assert_called_once_with("facebook|123", mock_client)
    assert results["orphaned_users_deleted"] == 1
    assert results["orphaned_users_failed"] == 0


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_not_found(mock_delete_user, mock_client):
    """404 → silent no-op; no delete attempted, no failure counted."""
    mock_client.get_user.return_value = APIResponse(
        success=False, status_code=404, error_message="not found"
    )
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", mock_client, results)

    mock_delete_user.assert_not_called()
    assert results["orphaned_users_deleted"] == 0
    assert results["orphaned_users_failed"] == 0


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_lookup_error(mock_delete_user, mock_client):
    """Non-404 lookup error → counted as lookup failure, not delete failure."""
    mock_client.get_user.return_value = APIResponse(
        success=False, status_code=500, error_message="server error"
    )
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", mock_client, results)

    mock_delete_user.assert_not_called()
    assert results["orphaned_users_deleted"] == 0
    assert results["orphaned_users_failed"] == 0
    assert results["orphaned_users_lookup_failed"] == 1


@patch("src.deletepy.operations.batch_ops.print_error")
@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_renders_status_when_no_message(
    mock_delete_user, mock_print_error, mock_client
):
    """Lookup failure with error_message=None logs the HTTP status, not 'None'."""
    mock_client.get_user.return_value = APIResponse(
        success=False, status_code=502, error_message=None
    )
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", mock_client, results)

    logged_message = mock_print_error.call_args.args[0]
    assert "HTTP 502" in logged_message
    assert "None" not in logged_message
    assert results["orphaned_users_lookup_failed"] == 1


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_lookup_and_delete_detached_user_delete_fails(mock_delete_user, mock_client):
    """Found but delete_user returns False → counted as failed."""
    mock_client.get_user.return_value = APIResponse(
        success=True, status_code=200, data={"user_id": "facebook|123"}
    )
    mock_delete_user.return_value = False
    results = _empty_results()

    _lookup_and_delete_detached_user("facebook", "123", mock_client, results)

    assert results["orphaned_users_deleted"] == 0
    assert results["orphaned_users_failed"] == 1


# ---------- _sweep_detached_social_users ----------


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_sweep_mixed_results(mock_delete_user, mock_client):
    """Sweep handles mix of found, not-found, and error cases."""
    mock_client.get_user.side_effect = [
        APIResponse(success=True, status_code=200, data={"user_id": "facebook|1"}),
        APIResponse(success=False, status_code=404),
        APIResponse(success=True, status_code=200, data={"user_id": "facebook|3"}),
    ]
    mock_delete_user.return_value = True
    results = _empty_results()

    _sweep_detached_social_users(
        [("facebook", "1"), ("facebook", "2"), ("facebook", "3")],
        mock_client,
        results,
    )

    assert mock_client.get_user.call_count == 3
    assert mock_delete_user.call_count == 2
    assert results["orphaned_users_deleted"] == 2
    assert results["orphaned_users_failed"] == 0


# ---------- _process_single_identity_unlink ----------


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
def test_process_single_identity_unlink_success_appends_target(
    mock_orphan_check, mock_unlink, mock_client
):
    """Successful unlink appends (connection, social_id) to detached_targets."""
    mock_unlink.return_value = True
    results = _empty_results()
    targets: list[tuple[str, str]] = []
    user = {
        "user_id": "auth0|main",
        "matching_connection": "facebook",
        "social_id": "fb123",
    }

    _process_single_identity_unlink(user, mock_client, results, targets)

    assert results["unlinked_count"] == 1
    assert results["failed_unlinks"] == 0
    assert targets == [("facebook", "fb123")]
    mock_orphan_check.assert_called_once_with("auth0|main", mock_client, results)


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
def test_process_single_identity_unlink_failure_no_target(
    mock_orphan_check, mock_unlink, mock_client
):
    """Failed unlink does not append a sweep target or call orphan check."""
    mock_unlink.return_value = False
    results = _empty_results()
    targets: list[tuple[str, str]] = []
    user = {
        "user_id": "auth0|main",
        "matching_connection": "facebook",
        "social_id": "fb123",
    }

    _process_single_identity_unlink(user, mock_client, results, targets)

    assert results["unlinked_count"] == 0
    assert results["failed_unlinks"] == 1
    assert targets == []
    mock_orphan_check.assert_not_called()


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
def test_process_single_identity_unlink_exception(mock_unlink, mock_client):
    """Exception during unlink is caught and counted as failed."""
    mock_unlink.side_effect = RuntimeError("boom")
    results = _empty_results()
    targets: list[tuple[str, str]] = []
    user = {
        "user_id": "auth0|main",
        "matching_connection": "facebook",
        "social_id": "fb123",
    }

    _process_single_identity_unlink(user, mock_client, results, targets)

    assert results["failed_unlinks"] == 1
    assert targets == []


# ---------- _handle_identity_unlinking ----------


def test_handle_identity_unlinking_empty_returns_early(mock_client):
    """Empty input returns zeros without invoking anything."""
    results = _handle_identity_unlinking([], mock_client)

    assert results == _empty_results()
    mock_client.get_user.assert_not_called()


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
@patch("src.deletepy.operations.batch_ops.delete_user")
def test_handle_identity_unlinking_runs_sweep_after_loop(
    mock_delete_user, mock_orphan_check, mock_unlink, mock_client
):
    """Sweep runs after the unlink loop and finds detached users via GET-by-id."""
    mock_unlink.return_value = True
    mock_delete_user.return_value = True
    # During the sweep, the first detached user exists (200), the second is
    # already gone (404) — exactly the scenario the prior search-based code
    # missed when Auth0's index lagged behind.
    mock_client.get_user.side_effect = [
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

    results = _handle_identity_unlinking(identities, mock_client)

    assert results["unlinked_count"] == 2
    assert results["failed_unlinks"] == 0
    assert results["orphaned_users_deleted"] == 1
    assert results["orphaned_users_failed"] == 0
    # Sweep ran exactly once per successful unlink (no per-unlink search calls)
    assert mock_client.get_user.call_count == 2
    mock_delete_user.assert_called_once_with("facebook|fb1", mock_client)


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
@patch("src.deletepy.operations.batch_ops.delete_user")
def test_handle_identity_unlinking_skips_sweep_for_failed_unlinks(
    mock_delete_user, mock_orphan_check, mock_unlink, mock_client
):
    """Only successful unlinks become sweep targets."""
    mock_unlink.side_effect = [True, False]  # first succeeds, second fails
    mock_client.get_user.return_value = APIResponse(success=False, status_code=404)
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

    results = _handle_identity_unlinking(identities, mock_client)

    assert results["unlinked_count"] == 1
    assert results["failed_unlinks"] == 1
    # Only one sweep lookup, for the successful unlink
    assert mock_client.get_user.call_count == 1
    mock_delete_user.assert_not_called()


# ---------- _delete_orphaned_user_if_empty ----------


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_delete_orphaned_user_if_empty_no_remaining_identities(
    mock_delete_user, mock_client
):
    """count==0 → user is deleted and orphaned_users_deleted is incremented."""
    mock_client.get_user.return_value = APIResponse(
        success=True, status_code=200, data={"identities": []}
    )
    mock_delete_user.return_value = True
    results = _empty_results()

    _delete_orphaned_user_if_empty("auth0|main", mock_client, results)

    mock_delete_user.assert_called_once_with("auth0|main", mock_client)
    assert results["orphaned_users_deleted"] == 1
    assert results["orphaned_users_failed"] == 0
    assert results["orphaned_users_lookup_failed"] == 0


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_delete_orphaned_user_if_empty_still_has_identities(
    mock_delete_user, mock_client
):
    """count>0 → no delete; no counter touched."""
    mock_client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"identities": [{"connection": "auth0"}]},
    )
    results = _empty_results()

    _delete_orphaned_user_if_empty("auth0|main", mock_client, results)

    mock_delete_user.assert_not_called()
    assert results == _empty_results()


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_delete_orphaned_user_if_empty_lookup_failure(mock_delete_user, mock_client):
    """Lookup failure (count is None) → no delete; lookup-failed counter increments."""
    mock_client.get_user.return_value = APIResponse(
        success=False, status_code=500, error_message="server error"
    )
    results = _empty_results()

    _delete_orphaned_user_if_empty("auth0|main", mock_client, results)

    mock_delete_user.assert_not_called()
    assert results["orphaned_users_deleted"] == 0
    assert results["orphaned_users_failed"] == 0
    assert results["orphaned_users_lookup_failed"] == 1


# ---------- collision guard and sweep edge cases ----------


@patch("src.deletepy.operations.batch_ops.unlink_user_identity")
@patch("src.deletepy.operations.batch_ops._delete_orphaned_user_if_empty")
def test_process_single_identity_unlink_skips_target_when_id_matches_primary(
    mock_orphan_check, mock_unlink, mock_client
):
    """No sweep target enqueued when the constructed id equals the primary user_id.

    Protects an active primary social account from accidental deletion if the
    inline orphan check fails transiently.
    """
    mock_unlink.return_value = True
    results = _empty_results()
    targets: list[tuple[str, str]] = []
    user = {
        "user_id": "facebook|fb123",
        "matching_connection": "facebook",
        "social_id": "fb123",
    }

    _process_single_identity_unlink(user, mock_client, results, targets)

    assert results["unlinked_count"] == 1
    assert targets == []


@patch("src.deletepy.operations.batch_ops.delete_user")
def test_sweep_passes_per_target_encoded_id(mock_delete_user, mock_client):
    """Each target's {connection}|{social_id} is URL-encoded and passed to GET."""
    mock_client.get_user.return_value = APIResponse(success=False, status_code=404)
    results = _empty_results()

    _sweep_detached_social_users(
        [("facebook", "fb1"), ("google-oauth2", "abc-xyz")],
        mock_client,
        results,
    )

    call_args = [c.args[0] for c in mock_client.get_user.call_args_list]
    assert call_args == ["facebook%7Cfb1", "google-oauth2%7Cabc-xyz"]


@patch("src.deletepy.operations.batch_ops.shutdown_requested")
@patch("src.deletepy.operations.batch_ops.print_warning")
@patch("src.deletepy.operations.batch_ops.delete_user")
def test_sweep_warns_when_shutdown_aborts_mid_loop(
    mock_delete_user, mock_print_warning, mock_shutdown, mock_client
):
    """Shutdown mid-sweep stops processing and warns about unprocessed targets."""
    # First two iterations proceed; third triggers shutdown before lookup.
    mock_shutdown.side_effect = [False, False, True]
    mock_client.get_user.return_value = APIResponse(success=False, status_code=404)
    results = _empty_results()

    _sweep_detached_social_users(
        [("facebook", "1"), ("facebook", "2"), ("facebook", "3")],
        mock_client,
        results,
    )

    assert mock_client.get_user.call_count == 2
    warning_messages = [c.args[0] for c in mock_print_warning.call_args_list]
    assert any("1 detached user" in msg for msg in warning_messages)
