from unittest.mock import MagicMock, patch

from src.deletepy.core.auth0_client import APIResponse, Auth0Client
from src.deletepy.operations.user_ops import (
    UserOperationOptions,
    _execute_user_operation,
    _fetch_users_by_email,
    batch_user_operations_with_checkpoints,
    block_user,
    delete_user,
    get_user_details,
    get_user_email,
    get_user_id_from_email,
    revoke_user_grants,
    revoke_user_sessions,
    set_requires_additional_verification,
    unlink_user_identity,
)


def _make_client() -> MagicMock:
    """Create a mock Auth0Client for testing."""
    return MagicMock(spec=Auth0Client)


def test_delete_user():
    client = _make_client()

    # Mock get_user_sessions (called by revoke_user_sessions via _fetch_user_sessions)
    # Return no sessions so the session revocation path is simple
    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )

    # Mock delete_user response
    client.delete_user.return_value = APIResponse(success=True, status_code=204)

    result = delete_user("auth0|test_user_id", client)

    assert result is True

    # Verify get_user_sessions was called with encoded user ID
    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")

    # Verify delete_user was called with encoded user ID
    client.delete_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_delete_user_failure():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )
    client.delete_user.return_value = APIResponse(
        success=False, status_code=500, error_message="Internal server error"
    )

    result = delete_user("auth0|test_user_id", client)

    assert result is False
    client.delete_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_block_user():
    client = _make_client()

    # Mock session and grant revocation
    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )
    client.delete_user_grants.return_value = APIResponse(success=True, status_code=204)

    # Mock block_user response
    client.block_user.return_value = APIResponse(success=True, status_code=200)

    result = block_user("auth0|test_user_id", client)

    assert result is True

    # Verify revoke_user_sessions was triggered (get_user_sessions called)
    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")

    # Verify revoke_user_grants was triggered (delete_user_grants called)
    client.delete_user_grants.assert_called_once_with("auth0|test_user_id")

    # Verify block_user was called with encoded user ID
    client.block_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_block_user_failure():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )
    client.delete_user_grants.return_value = APIResponse(success=True, status_code=204)
    client.block_user.return_value = APIResponse(
        success=False, status_code=400, error_message="Bad request"
    )

    result = block_user("auth0|test_user_id", client)

    assert result is False
    client.block_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_block_user_with_rotate_password():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )
    client.delete_user_grants.return_value = APIResponse(success=True, status_code=204)
    client.block_user.return_value = APIResponse(success=True, status_code=200)

    with patch("src.deletepy.operations.user_ops.rotate_user_password") as mock_rotate:
        result = block_user("auth0|test_user_id", client, rotate_password=True)

        assert result is True
        mock_rotate.assert_called_once_with("auth0|test_user_id", client)

    client.block_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_set_requires_additional_verification():
    client = _make_client()

    client.update_user.return_value = APIResponse(success=True, status_code=200)

    result = set_requires_additional_verification("auth0|test_user_id", client)

    assert result is True
    client.update_user.assert_called_once_with(
        "auth0%7Ctest_user_id",
        {"app_metadata": {"requiresAdditionalVerification": True}},
    )


def test_set_requires_additional_verification_failure():
    client = _make_client()

    client.update_user.return_value = APIResponse(
        success=False, status_code=400, error_message="Bad request"
    )

    result = set_requires_additional_verification("auth0|test_user_id", client)

    assert result is False
    client.update_user.assert_called_once_with(
        "auth0%7Ctest_user_id",
        {"app_metadata": {"requiresAdditionalVerification": True}},
    )


def test_execute_user_operation_force_otp_revoke_grants():
    client = _make_client()

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification"
        ) as mock_force_otp,
        patch(
            "src.deletepy.operations.user_ops.revoke_user_sessions", return_value=True
        ),
        patch("src.deletepy.operations.user_ops.revoke_user_grants", return_value=True),
    ):
        result = _execute_user_operation(
            "revoke-grants-only",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
        )

        assert result is True
        mock_force_otp.assert_called_once_with("auth0|test_user_id", client)


def test_execute_user_operation_force_otp_skipped_for_delete():
    client = _make_client()

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification"
        ) as mock_force_otp,
        patch("src.deletepy.operations.user_ops.delete_user", return_value=True),
    ):
        result = _execute_user_operation(
            "delete",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
        )

        assert result is True
        mock_force_otp.assert_not_called()


def test_execute_user_operation_force_otp_block():
    """force_otp is applied for the block operation (Gap C)."""
    client = _make_client()

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification",
            return_value=True,
        ) as mock_force_otp,
        patch("src.deletepy.operations.user_ops.block_user", return_value=True),
    ):
        result = _execute_user_operation(
            "block",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
        )

        assert result is True
        mock_force_otp.assert_called_once_with("auth0|test_user_id", client)


def test_execute_user_operation_force_otp_failure_does_not_gate_success():
    """A failed force_otp PATCH must not fail the primary operation (Gap B)."""
    client = _make_client()
    results: dict = {}

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification",
            return_value=False,
        ),
        patch("src.deletepy.operations.user_ops.block_user", return_value=True),
    ):
        result = _execute_user_operation(
            "block",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
            results,
        )

        # Primary operation still succeeds...
        assert result is True
        # ...but the failure is recorded so it can be surfaced in the summary.
        assert results["force_otp_failed"] == ["auth0|test_user_id"]


def test_execute_user_operation_force_otp_success_not_recorded():
    """A successful force_otp PATCH leaves the failure list untouched."""
    client = _make_client()
    results: dict = {}

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification",
            return_value=True,
        ),
        patch("src.deletepy.operations.user_ops.block_user", return_value=True),
    ):
        result = _execute_user_operation(
            "block",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
            results,
        )

        assert result is True
        assert "force_otp_failed" not in results


def test_execute_user_operation_force_otp_failure_not_recorded_when_primary_fails():
    """force_otp_failed only lists users whose primary operation succeeded.

    The summary bucket reads "primary operation succeeded but the flag could
    not be set", so a user whose block failed must not appear there — that
    failure is already surfaced through the skipped/failed counts.
    """
    client = _make_client()
    results: dict = {}

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification",
            return_value=False,
        ),
        patch("src.deletepy.operations.user_ops.block_user", return_value=False),
    ):
        result = _execute_user_operation(
            "block",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
            results,
        )

        assert result is False
        assert "force_otp_failed" not in results


def test_batch_force_otp_persisted_in_checkpoint_config():
    """force_otp is written into the checkpoint's additional_params (Gap A)."""
    client = _make_client()

    with (
        patch(
            "src.deletepy.operations.user_ops.load_or_create_checkpoint"
        ) as mock_load,
        patch(
            "src.deletepy.operations.user_ops."
            "_process_batch_user_operations_with_checkpoints",
            return_value=None,
        ) as mock_process,
    ):
        checkpoint_result = MagicMock()
        checkpoint_result.is_resuming = False
        checkpoint_result.checkpoint = MagicMock()
        checkpoint_result.checkpoint_manager = MagicMock()
        mock_load.return_value = checkpoint_result

        batch_user_operations_with_checkpoints(
            user_ids=["auth0|1"],
            client=client,
            operation="block",
            env="dev",
            options=UserOperationOptions(force_otp=True),
        )

        config = mock_load.call_args.kwargs["config"]
        assert config.additional_params["force_otp"] is True
        # And it is threaded into the processing options.
        assert mock_process.call_args.kwargs["options"].force_otp is True


def test_batch_force_otp_restored_from_checkpoint_on_resume():
    """Persisted force_otp wins over the caller's value when resuming (Gap A)."""
    client = _make_client()

    with (
        patch(
            "src.deletepy.operations.user_ops.load_or_create_checkpoint"
        ) as mock_load,
        patch(
            "src.deletepy.operations.user_ops."
            "_process_batch_user_operations_with_checkpoints",
            return_value=None,
        ) as mock_process,
    ):
        checkpoint = MagicMock()
        checkpoint.config.environment = "dev"
        checkpoint.config.additional_params = {
            "operation": "block",
            "rotate_password": False,
            "force_otp": True,
        }
        checkpoint_result = MagicMock()
        checkpoint_result.is_resuming = True
        checkpoint_result.checkpoint = checkpoint
        checkpoint_result.checkpoint_manager = MagicMock()
        mock_load.return_value = checkpoint_result

        # Caller passes force_otp=False, but the persisted True must win.
        batch_user_operations_with_checkpoints(
            user_ids=["auth0|1"],
            client=client,
            operation="block",
            env="dev",
            resume_checkpoint_id="cp-123",
            options=UserOperationOptions(force_otp=False),
        )

        assert mock_process.call_args.kwargs["options"].force_otp is True


def test_get_user_id_from_email():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[{"user_id": "test_user_id"}],
    )

    result = get_user_id_from_email("test@example.com", client)

    assert result == ["test_user_id"]
    client.get_users_by_email.assert_called_once_with("test@example.com")


def test_get_user_id_from_email_multiple_users():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[
            {"user_id": "test_user_id_1"},
            {"user_id": "test_user_id_2"},
        ],
    )

    result = get_user_id_from_email("test@example.com", client)

    assert result == ["test_user_id_1", "test_user_id_2"]
    client.get_users_by_email.assert_called_once_with("test@example.com")


def test_get_user_id_from_email_not_found():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[],
    )

    result = get_user_id_from_email("test@example.com", client)

    assert result is None


def test_get_user_id_from_email_with_connection_filter():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[
            {
                "user_id": "auth0|user1",
                "identities": [{"connection": "Username-Password-Authentication"}],
            },
            {
                "user_id": "google-oauth2|user2",
                "identities": [{"connection": "google-oauth2"}],
            },
        ],
    )

    result = get_user_id_from_email(
        "test@example.com", client, connection="google-oauth2"
    )

    assert result == ["google-oauth2|user2"]


def test_get_user_id_from_email_api_failure():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=False,
        status_code=500,
        error_message="Internal server error",
    )

    result = get_user_id_from_email("test@example.com", client)

    assert result is None


def test_fetch_users_by_email_empty_response():
    """Test _fetch_users_by_email handles empty response array consistently."""
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[],
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result == []  # Should return empty list, not None
    client.get_users_by_email.assert_called_once_with("test@example.com")


def test_fetch_users_by_email_none_response():
    """Test _fetch_users_by_email handles None data from API."""
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=None,
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result == []  # Should return empty list for consistency


def test_fetch_users_by_email_request_failure():
    """Test _fetch_users_by_email handles request failure."""
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=False,
        status_code=0,
        error_message="Connection failed",
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result is None  # Should return None for request failures


def test_fetch_users_by_email_non_list_response():
    """Test _fetch_users_by_email handles non-list response."""
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"error": "Invalid request"},
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result == []  # Should return empty list for non-list responses


def test_fetch_users_by_email_successful_response():
    """Test _fetch_users_by_email handles successful response with users."""
    client = _make_client()

    expected_users = [{"user_id": "test_user_1"}, {"user_id": "test_user_2"}]
    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=expected_users,
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result == expected_users
    client.get_users_by_email.assert_called_once_with("test@example.com")


def test_revoke_user_sessions():
    client = _make_client()

    # Mock fetching sessions - returns dict with sessions key
    client.get_user_sessions.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"sessions": [{"id": "session1"}, {"id": "session2"}]},
    )

    # Mock deleting sessions
    client.delete_session.return_value = APIResponse(success=True, status_code=204)

    revoke_user_sessions("auth0|test_user_id", client)

    # Verify GET sessions was called with encoded user ID
    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")

    # Verify DELETE was called for each session
    assert client.delete_session.call_count == 2
    client.delete_session.assert_any_call("session1")
    client.delete_session.assert_any_call("session2")


def test_revoke_user_sessions_no_sessions():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"sessions": []},
    )

    revoke_user_sessions("auth0|test_user_id", client)

    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")
    client.delete_session.assert_not_called()


def test_revoke_user_sessions_fetch_failure():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=False,
        status_code=500,
        error_message="Server error",
    )

    revoke_user_sessions("auth0|test_user_id", client)

    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")
    client.delete_session.assert_not_called()


def test_revoke_user_sessions_delete_failure():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"sessions": [{"id": "session1"}]},
    )
    client.delete_session.return_value = APIResponse(
        success=False, status_code=403, error_message="Forbidden"
    )

    # Should not raise, just prints warning
    revoke_user_sessions("auth0|test_user_id", client)

    client.delete_session.assert_called_once_with("session1")


def test_revoke_user_sessions_session_without_id():
    """Test that sessions without an 'id' key are skipped."""
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"sessions": [{"id": "session1"}, {"no_id": "bad_session"}]},
    )
    client.delete_session.return_value = APIResponse(success=True, status_code=204)

    revoke_user_sessions("auth0|test_user_id", client)

    # Only the valid session should be deleted
    client.delete_session.assert_called_once_with("session1")


def test_revoke_user_grants():
    client = _make_client()

    client.delete_user_grants.return_value = APIResponse(success=True, status_code=204)

    revoke_user_grants("auth0|test_user_id", client)

    client.delete_user_grants.assert_called_once_with("auth0|test_user_id")


def test_revoke_user_grants_failure():
    client = _make_client()

    client.delete_user_grants.return_value = APIResponse(
        success=False, status_code=500, error_message="Server error"
    )

    # Should not raise, just prints error
    revoke_user_grants("auth0|test_user_id", client)

    client.delete_user_grants.assert_called_once_with("auth0|test_user_id")


def test_get_user_email():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"email": "test@example.com"},
    )

    result = get_user_email("auth0|test_user_id", client)

    assert result == "test@example.com"
    client.get_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_get_user_email_not_found():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=False,
        status_code=404,
        error_message="User not found",
    )

    result = get_user_email("auth0|test_user_id", client)

    assert result is None


def test_get_user_email_no_email_field():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"user_id": "auth0|test_user_id"},
    )

    result = get_user_email("auth0|test_user_id", client)

    assert result is None


def test_get_user_details():
    client = _make_client()

    expected_data = {
        "user_id": "auth0|test_user_id",
        "identities": [{"connection": "test-connection"}],
    }
    client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data=expected_data,
    )

    result = get_user_details("auth0|test_user_id", client)

    assert result == expected_data
    client.get_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_get_user_details_not_found():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=False,
        status_code=404,
        error_message="User not found",
    )

    result = get_user_details("auth0|test_user_id", client)

    assert result is None


def test_get_user_details_none_data():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data=None,
    )

    result = get_user_details("auth0|test_user_id", client)

    assert result is None


def test_unlink_user_identity_success():
    client = _make_client()

    client.unlink_identity.return_value = APIResponse(success=True, status_code=200)

    result = unlink_user_identity("auth0|123", "google-oauth2", "google123", client)

    assert result is True
    client.unlink_identity.assert_called_once_with(
        "auth0%7C123", "google-oauth2", "google123"
    )


def test_unlink_user_identity_failure():
    client = _make_client()

    client.unlink_identity.return_value = APIResponse(
        success=False,
        status_code=400,
        error_message="Bad request",
    )

    result = unlink_user_identity("auth0|123", "google-oauth2", "google123", client)

    assert result is False
    client.unlink_identity.assert_called_once_with(
        "auth0%7C123", "google-oauth2", "google123"
    )


def test_execute_user_operation_records_orphan_when_primary_fails():
    """Flag set + primary failed is recorded so the mutation is not silent.

    The PATCH runs before the primary operation, so a failed block leaves the
    user flagged but not blocked. That user must not disappear into the
    anonymous skipped_count.
    """
    client = _make_client()
    results: dict = {}

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification",
            return_value=True,
        ),
        patch("src.deletepy.operations.user_ops.block_user", return_value=False),
    ):
        ok = _execute_user_operation(
            "block",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
            results,
        )

    assert ok is False
    assert results["force_otp_orphaned"] == ["auth0|test_user_id"]
    assert "force_otp_failed" not in results


def test_execute_user_operation_no_orphan_when_flag_also_failed():
    """Primary failed and flag failed mutates nothing, so nothing is recorded."""
    client = _make_client()
    results: dict = {}

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification",
            return_value=False,
        ),
        patch("src.deletepy.operations.user_ops.block_user", return_value=False),
    ):
        ok = _execute_user_operation(
            "block",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
            results,
        )

    assert ok is False
    assert "force_otp_orphaned" not in results
    assert "force_otp_failed" not in results


def test_execute_user_operation_force_otp_revoke_failure_recorded():
    """revoke-grants-only's compound primary_ok gates recording correctly."""
    client = _make_client()
    results: dict = {}

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification",
            return_value=False,
        ),
        patch(
            "src.deletepy.operations.user_ops.revoke_user_sessions", return_value=True
        ),
        patch(
            "src.deletepy.operations.user_ops.revoke_user_grants", return_value=False
        ),
    ):
        ok = _execute_user_operation(
            "revoke-grants-only",
            "auth0|test_user_id",
            client,
            UserOperationOptions(force_otp=True),
            results,
        )

    # grants_ok False => primary failed => flag failure is not claimed as a
    # standalone force-OTP failure, and nothing was mutated to orphan.
    assert ok is False
    assert "force_otp_failed" not in results
    assert "force_otp_orphaned" not in results


def test_set_requires_additional_verification_rejects_bad_id_without_raising():
    """An unencodable user ID returns False rather than aborting the batch."""
    client = _make_client()

    assert set_requires_additional_verification("", client) is False
    client.update_user.assert_not_called()


def test_force_otp_failures_reach_checkpoint_and_summary(tmp_path):
    """End-to-end: a failed flag PATCH reaches checkpoint.results and the summary.

    Covers the batch_results -> tracking_state -> results_update ->
    checkpoint.results -> summary chain, which unit tests on
    _execute_user_operation alone do not exercise.
    """
    from src.deletepy.utils.checkpoint_manager import CheckpointManager

    client = _make_client()
    manager = CheckpointManager(checkpoint_dir=str(tmp_path))

    with (
        patch(
            "src.deletepy.operations.user_ops.set_requires_additional_verification",
            return_value=False,
        ),
        patch("src.deletepy.operations.user_ops.block_user", return_value=True),
        patch(
            "src.deletepy.operations.user_ops._print_user_operation_summary"
        ) as mock_summary,
    ):
        batch_user_operations_with_checkpoints(
            user_ids=["auth0|1", "auth0|2"],
            client=client,
            operation="block",
            env="dev",
            checkpoint_manager=manager,
            options=UserOperationOptions(force_otp=True),
        )

    saved = manager.list_checkpoints()
    assert len(saved) == 1
    checkpoint = manager.load_checkpoint(saved[0].checkpoint_id)
    assert checkpoint.results.force_otp_failed == ["auth0|1", "auth0|2"]

    # And the summary was handed the same (cumulative) list, not an empty one.
    mock_summary.assert_called_once()
    assert mock_summary.call_args.args[6] == ["auth0|1", "auth0|2"]


def test_summary_reports_cumulative_lists_not_session_lists(tmp_path):
    """The summary reads checkpoint.results, so a resume does not under-report.

    tracking_state is reset on every invocation; pairing it with the cumulative
    processed_count would hide failures recorded before the interruption.
    """
    from src.deletepy.models.checkpoint import CheckpointStatus
    from src.deletepy.operations.user_ops import _finalize_batch_processing
    from src.deletepy.utils.checkpoint_manager import CheckpointManager

    client = _make_client()
    manager = MagicMock(spec=CheckpointManager)

    checkpoint = MagicMock()
    checkpoint.results.processed_count = 5000
    checkpoint.results.skipped_count = 0
    checkpoint.results.not_found_users = []
    checkpoint.results.invalid_user_ids = []
    checkpoint.results.multiple_users = {}
    checkpoint.results.force_otp_failed = ["auth0|earlier-run"]
    checkpoint.results.force_otp_orphaned = []

    # Empty tracking_state stands in for a resumed run whose own batches were clean.
    tracking_state = {
        "multiple_users": {},
        "not_found_users": [],
        "invalid_user_ids": [],
        "force_otp_failed": [],
        "force_otp_orphaned": [],
    }

    with patch(
        "src.deletepy.operations.user_ops._print_user_operation_summary"
    ) as mock_summary:
        _finalize_batch_processing(checkpoint, manager, "block", tracking_state, client)

    assert checkpoint.status == CheckpointStatus.COMPLETED
    assert mock_summary.call_args.args[6] == ["auth0|earlier-run"]


def _summary_output(**kwargs) -> str:
    """Render _print_user_operation_summary and capture its warning lines."""
    from src.deletepy.operations.user_ops import _print_user_operation_summary

    defaults = {
        "processed_count": 1,
        "skipped_count": 0,
        "not_found_users": [],
        "invalid_user_ids": [],
        "multiple_users": {},
        "client": _make_client(),
    }
    defaults.update(kwargs)

    lines: list[str] = []
    with (
        patch(
            "src.deletepy.operations.user_ops.print_warning",
            side_effect=lambda msg, *a, **kw: lines.append(str(msg)),
        ),
        patch("src.deletepy.operations.user_ops.print_info"),
    ):
        _print_user_operation_summary(**defaults)
    return "\n".join(lines)


def test_summary_reports_force_otp_failures():
    output = _summary_output(force_otp_failed=["auth0|1", "auth0|2"])

    assert "Force-OTP failures (2)" in output
    assert "auth0|1" in output
    assert "auth0|2" in output


def test_summary_reports_force_otp_orphans_distinctly():
    """Orphans read as 'flagged but NOT acted on', not as a flag failure."""
    output = _summary_output(force_otp_orphaned=["auth0|9"])

    assert "Force-OTP orphaned (1)" in output
    assert "auth0|9" in output
    assert "Force-OTP failures" not in output


def test_summary_omits_force_otp_sections_when_clean():
    output = _summary_output()

    assert "Force-OTP" not in output
