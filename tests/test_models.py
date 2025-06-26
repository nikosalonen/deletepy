"""Tests for data models."""

import pytest
from datetime import datetime
from src.deletepy.models.user import (
    User, 
    UserIdentity, 
    UserOperationResult, 
    BatchOperationResults
)
from src.deletepy.models.config import (
    Auth0Config, 
    APIConfig, 
    ExportConfig, 
    AppConfig
)


class TestUserIdentity:
    """Test UserIdentity model."""
    
    def test_user_identity_creation(self):
        """Test creating a UserIdentity instance."""
        identity = UserIdentity(
            connection="google-oauth2",
            user_id="12345",
            provider="google-oauth2",
            is_social=True
        )
        
        assert identity.connection == "google-oauth2"
        assert identity.user_id == "12345"
        assert identity.provider == "google-oauth2"
        assert identity.is_social is True
        assert identity.access_token is None
        assert identity.profile_data == {}

    def test_user_identity_with_optional_fields(self):
        """Test UserIdentity with optional fields."""
        profile_data = {"name": "John Doe", "email": "john@example.com"}
        identity = UserIdentity(
            connection="auth0",
            user_id="67890",
            provider="auth0",
            access_token="token123",
            profile_data=profile_data
        )
        
        assert identity.access_token == "token123"
        assert identity.profile_data == profile_data


class TestUser:
    """Test User model."""
    
    def test_user_creation(self):
        """Test creating a User instance."""
        user = User(user_id="auth0|123456")
        
        assert user.user_id == "auth0|123456"
        assert user.email is None
        assert user.blocked is False
        assert user.identities == []
        assert user.app_metadata == {}
        assert user.user_metadata == {}

    def test_user_with_full_data(self):
        """Test User with complete data."""
        identity = UserIdentity(
            connection="auth0",
            user_id="123456",
            provider="auth0"
        )
        
        created_at = datetime.now()
        user = User(
            user_id="auth0|123456",
            email="test@example.com",
            identities=[identity],
            blocked=False,
            created_at=created_at,
            logins_count=5
        )
        
        assert user.email == "test@example.com"
        assert len(user.identities) == 1
        assert user.identities[0] == identity
        assert user.created_at == created_at
        assert user.logins_count == 5

    def test_from_auth0_data(self):
        """Test creating User from Auth0 API data."""
        auth0_data = {
            "user_id": "auth0|123456",
            "email": "test@example.com",
            "blocked": False,
            "identities": [
                {
                    "connection": "auth0",
                    "user_id": "123456",
                    "provider": "auth0",
                    "isSocial": False
                }
            ],
            "logins_count": 3,
            "created_at": "2023-01-01T00:00:00.000Z",
            "last_login": "2023-01-02T00:00:00.000Z",
            "app_metadata": {"role": "user"},
            "user_metadata": {"preference": "dark"}
        }
        
        user = User.from_auth0_data(auth0_data)
        
        assert user.user_id == "auth0|123456"
        assert user.email == "test@example.com"
        assert user.blocked is False
        assert len(user.identities) == 1
        assert user.identities[0].connection == "auth0"
        assert user.identities[0].is_social is False
        assert user.logins_count == 3
        assert user.app_metadata == {"role": "user"}
        assert user.user_metadata == {"preference": "dark"}
        assert user.created_at is not None
        assert user.last_login is not None

    def test_to_dict(self):
        """Test converting User to dictionary."""
        user = User(
            user_id="auth0|123456",
            email="test@example.com",
            blocked=True
        )
        
        result = user.to_dict()
        
        assert result["user_id"] == "auth0|123456"
        assert result["email"] == "test@example.com"
        assert result["blocked"] is True
        assert result["identities"] == []

    def test_is_social_user(self):
        """Test checking if user has only social identities."""
        social_identity = UserIdentity(
            connection="google-oauth2",
            user_id="123",
            provider="google-oauth2",
            is_social=True
        )
        
        # User with one social identity
        social_user = User(
            user_id="google-oauth2|123",
            identities=[social_identity]
        )
        assert social_user.is_social_user() is True
        
        # User with no identities
        no_identity_user = User(user_id="auth0|123")
        assert no_identity_user.is_social_user() is False
        
        # User with non-social identity
        non_social_identity = UserIdentity(
            connection="auth0",
            user_id="123",
            provider="auth0",
            is_social=False
        )
        non_social_user = User(
            user_id="auth0|123",
            identities=[non_social_identity]
        )
        assert non_social_user.is_social_user() is False

    def test_has_multiple_identities(self):
        """Test checking if user has multiple identities."""
        identity1 = UserIdentity(connection="auth0", user_id="123", provider="auth0")
        identity2 = UserIdentity(connection="google-oauth2", user_id="456", provider="google-oauth2")
        
        # User with multiple identities
        multi_user = User(
            user_id="auth0|123",
            identities=[identity1, identity2]
        )
        assert multi_user.has_multiple_identities() is True
        
        # User with single identity
        single_user = User(
            user_id="auth0|123",
            identities=[identity1]
        )
        assert single_user.has_multiple_identities() is False

    def test_get_primary_identity(self):
        """Test getting primary identity."""
        identity = UserIdentity(connection="auth0", user_id="123", provider="auth0")
        user = User(user_id="auth0|123", identities=[identity])
        
        assert user.get_primary_identity() == identity
        
        # User with no identities
        empty_user = User(user_id="auth0|123")
        assert empty_user.get_primary_identity() is None

    def test_get_social_identities(self):
        """Test getting social identities."""
        social_identity = UserIdentity(
            connection="google-oauth2",
            user_id="123",
            provider="google-oauth2",
            is_social=True
        )
        non_social_identity = UserIdentity(
            connection="auth0",
            user_id="456",
            provider="auth0",
            is_social=False
        )
        
        user = User(
            user_id="auth0|123",
            identities=[social_identity, non_social_identity]
        )
        
        social_identities = user.get_social_identities()
        assert len(social_identities) == 1
        assert social_identities[0] == social_identity


class TestUserOperationResult:
    """Test UserOperationResult model."""
    
    def test_operation_result_creation(self):
        """Test creating UserOperationResult."""
        result = UserOperationResult(
            user_id="auth0|123",
            operation="delete",
            success=True
        )
        
        assert result.user_id == "auth0|123"
        assert result.operation == "delete"
        assert result.success is True
        assert result.error_message is None
        assert result.timestamp is not None

    def test_operation_result_with_error(self):
        """Test UserOperationResult with error."""
        result = UserOperationResult(
            user_id="auth0|123",
            operation="delete",
            success=False,
            error_message="User not found"
        )
        
        assert result.success is False
        assert result.error_message == "User not found"

    def test_operation_result_str(self):
        """Test string representation of UserOperationResult."""
        success_result = UserOperationResult(
            user_id="auth0|123",
            operation="delete",
            success=True
        )
        assert "delete auth0|123: SUCCESS" in str(success_result)
        
        error_result = UserOperationResult(
            user_id="auth0|123",
            operation="delete",
            success=False,
            error_message="User not found"
        )
        assert "delete auth0|123: FAILED - User not found" in str(error_result)


class TestBatchOperationResults:
    """Test BatchOperationResults model."""
    
    def test_batch_results_creation(self):
        """Test creating BatchOperationResults."""
        results = BatchOperationResults(
            operation="delete",
            total_users=10
        )
        
        assert results.operation == "delete"
        assert results.total_users == 10
        assert results.processed_count == 0
        assert results.skipped_count == 0
        assert results.not_found_users == []
        assert results.invalid_user_ids == []
        assert results.multiple_users == {}
        assert results.operation_results == []

    def test_success_rate(self):
        """Test calculating success rate."""
        results = BatchOperationResults(
            operation="delete",
            total_users=10,
            processed_count=8
        )
        
        assert results.success_rate == 80.0
        
        # Test zero division
        empty_results = BatchOperationResults(
            operation="delete",
            total_users=0
        )
        assert empty_results.success_rate == 0.0

    def test_add_result(self):
        """Test adding operation results."""
        batch_results = BatchOperationResults(
            operation="delete",
            total_users=2
        )
        
        success_result = UserOperationResult(
            user_id="auth0|123",
            operation="delete",
            success=True
        )
        
        failure_result = UserOperationResult(
            user_id="auth0|456",
            operation="delete",
            success=False,
            error_message="User not found"
        )
        
        batch_results.add_result(success_result)
        batch_results.add_result(failure_result)
        
        assert batch_results.processed_count == 1
        assert batch_results.skipped_count == 1
        assert len(batch_results.operation_results) == 2

    def test_get_summary(self):
        """Test getting batch operation summary."""
        results = BatchOperationResults(
            operation="delete",
            total_users=10,
            processed_count=8,
            skipped_count=2,
            not_found_users=["user1@example.com"],
            invalid_user_ids=["invalid_id"]
        )
        
        summary = results.get_summary()
        
        assert summary["operation"] == "delete"
        assert summary["total_users"] == 10
        assert summary["processed_count"] == 8
        assert summary["skipped_count"] == 2
        assert summary["success_rate"] == 80.0
        assert summary["not_found_users_count"] == 1
        assert summary["invalid_user_ids_count"] == 1


class TestAuth0Config:
    """Test Auth0Config model."""
    
    def test_auth0_config_creation(self):
        """Test creating Auth0Config."""
        config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        assert config.domain == "test.auth0.com"
        assert config.client_id == "test_client_id"
        assert config.client_secret == "test_secret"
        assert config.environment == "dev"
        assert config.base_url == "https://test.auth0.com"

    def test_auth0_config_post_init(self):
        """Test __post_init__ sets base_url."""
        config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        assert config.base_url == "https://test.auth0.com"

    def test_from_env_vars(self):
        """Test creating Auth0Config from environment variables."""
        env_vars = {
            "DEV_AUTH0_DOMAIN": "test.auth0.com",
            "DEV_AUTH0_CLIENT_ID": "test_client_id",
            "DEV_AUTH0_CLIENT_SECRET": "test_secret"
        }
        
        config = Auth0Config.from_env_vars(env_vars, "dev")
        
        assert config.domain == "test.auth0.com"
        assert config.client_id == "test_client_id"
        assert config.client_secret == "test_secret"
        assert config.environment == "dev"

    def test_from_env_vars_missing_domain(self):
        """Test Auth0Config creation with missing domain."""
        env_vars = {
            "DEV_AUTH0_CLIENT_ID": "test_client_id",
            "DEV_AUTH0_CLIENT_SECRET": "test_secret"
        }
        
        with pytest.raises(ValueError, match="Missing DEV_AUTH0_DOMAIN"):
            Auth0Config.from_env_vars(env_vars, "dev")

    def test_to_dict(self):
        """Test converting Auth0Config to dictionary."""
        config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        result = config.to_dict()
        
        assert result["domain"] == "test.auth0.com"
        assert result["client_id"] == "test_client_id"
        assert result["client_secret"] == "***REDACTED***"
        assert result["environment"] == "dev"

    def test_get_token_url(self):
        """Test getting token URL."""
        config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        assert config.get_token_url() == "https://test.auth0.com/oauth/token"

    def test_get_api_url(self):
        """Test getting API URL."""
        config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        assert config.get_api_url() == "https://test.auth0.com/api/v2"
        assert config.get_api_url("users") == "https://test.auth0.com/api/v2/users"
        assert config.get_api_url("/users") == "https://test.auth0.com/api/v2/users"

    def test_validate(self):
        """Test Auth0Config validation."""
        valid_config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        assert valid_config.validate() is True
        
        # Invalid domain
        invalid_domain_config = Auth0Config(
            domain="invalid-domain.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        assert invalid_domain_config.validate() is False
        
        # Invalid environment
        invalid_env_config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="invalid"
        )
        assert invalid_env_config.validate() is False


class TestAPIConfig:
    """Test APIConfig model."""
    
    def test_api_config_creation(self):
        """Test creating APIConfig with defaults."""
        config = APIConfig()
        
        assert config.rate_limit == 0.5
        assert config.timeout == 30
        assert config.max_retries == 3

    def test_get_requests_per_second(self):
        """Test calculating requests per second."""
        config = APIConfig(rate_limit=0.5)
        assert config.get_requests_per_second() == 2.0
        
        zero_limit_config = APIConfig(rate_limit=0)
        assert config.get_requests_per_second() == 2.0  # Should still be 2.0 from previous

    def test_is_safe_for_auth0(self):
        """Test checking if rate limit is safe for Auth0."""
        safe_config = APIConfig(rate_limit=0.5)  # 2 req/sec
        assert safe_config.is_safe_for_auth0() is True
        
        unsafe_config = APIConfig(rate_limit=0.1)  # 10 req/sec
        assert unsafe_config.is_safe_for_auth0() is False


class TestExportConfig:
    """Test ExportConfig model."""
    
    def test_export_config_creation(self):
        """Test creating ExportConfig with defaults."""
        config = ExportConfig()
        
        assert config.default_batch_size == 50
        assert config.max_batch_size == 100
        assert config.large_dataset_threshold == 1000

    def test_get_optimal_batch_size(self):
        """Test calculating optimal batch size."""
        config = ExportConfig()
        
        assert config.get_optimal_batch_size(100) == 100  # Small dataset
        assert config.get_optimal_batch_size(750) == 50   # Medium dataset
        assert config.get_optimal_batch_size(1500) == 25  # Large dataset


class TestAppConfig:
    """Test AppConfig model."""
    
    def test_app_config_creation(self):
        """Test creating AppConfig."""
        auth0_config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        config = AppConfig(auth0=auth0_config)
        
        assert config.auth0 == auth0_config
        assert config.api is not None
        assert config.export is not None
        assert config.debug is False

    def test_app_config_post_init(self):
        """Test AppConfig __post_init__ creates defaults."""
        auth0_config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        config = AppConfig(auth0=auth0_config)
        
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.export, ExportConfig)

    def test_create_for_environment(self):
        """Test creating AppConfig for environment."""
        env_vars = {
            "DEV_AUTH0_DOMAIN": "test.auth0.com",
            "DEV_AUTH0_CLIENT_ID": "test_client_id",
            "DEV_AUTH0_CLIENT_SECRET": "test_secret"
        }
        
        config = AppConfig.create_for_environment("dev", env_vars)
        
        assert config.auth0.environment == "dev"
        assert config.debug is True  # dev environment

    def test_validate(self):
        """Test AppConfig validation."""
        auth0_config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        config = AppConfig(auth0=auth0_config)
        assert config.validate() is True

    def test_to_dict(self):
        """Test converting AppConfig to dictionary."""
        auth0_config = Auth0Config(
            domain="test.auth0.com",
            client_id="test_client_id",
            client_secret="test_secret",
            environment="dev"
        )
        
        config = AppConfig(auth0=auth0_config, debug=True)
        result = config.to_dict()
        
        assert "auth0" in result
        assert "api" in result
        assert "export" in result
        assert result["debug"] is True