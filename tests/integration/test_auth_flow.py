"""
Integration tests for authentication flow.
"""
import pytest
from fastapi import status
from fastapi.testclient import TestClient


class TestAuthenticationFlow:
    """Test authentication endpoints and flows."""

    def test_user_registration_success(self, client: TestClient, sample_user_data):
        """Test successful user registration."""
        response = client.post("/api/v1/auth/register", json=sample_user_data)

        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_user_registration_duplicate_email(self, client: TestClient, test_user, sample_user_data):
        """Test registration with existing email."""
        sample_user_data["email"] = test_user.email

        response = client.post("/api/v1/auth/register", json=sample_user_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["detail"]

    def test_user_registration_invalid_password(self, client: TestClient, sample_user_data):
        """Test registration with invalid password."""
        sample_user_data["password"] = "weak"

        response = client.post("/api/v1/auth/register", json=sample_user_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_user_login_success(self, client: TestClient, test_user):
        """Test successful user login."""
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }

        response = client.post("/api/v1/auth/login-json", json=login_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_user_login_invalid_credentials(self, client: TestClient, test_user):
        """Test login with invalid credentials."""
        login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }

        response = client.post("/api/v1/auth/login-json", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect email or password" in response.json()["detail"]

    def test_user_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }

        response = client.post("/api/v1/auth/login-json", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_success(self, client: TestClient, test_user_headers):
        """Test getting current user info."""
        response = client.get("/api/v1/auth/me", headers=test_user_headers)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "subscription_tier" in data
        assert "created_at" in data

    def test_get_current_user_invalid_token(self, client: TestClient):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}

        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_no_token(self, client: TestClient):
        """Test getting current user without token."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh_success(self, client: TestClient, test_user):
        """Test token refresh."""
        # First login to get tokens
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }

        login_response = client.post("/api/v1/auth/login-json", json=login_data)
        tokens = login_response.json()

        # Refresh token
        refresh_data = {
            "refresh_token": tokens["refresh_token"]
        }

        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_token_refresh_invalid_token(self, client: TestClient):
        """Test token refresh with invalid token."""
        refresh_data = {
            "refresh_token": "invalid_refresh_token"
        }

        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_success(self, client: TestClient, test_user_headers):
        """Test user logout."""
        response = client.post("/api/v1/auth/logout", headers=test_user_headers)

        assert response.status_code == status.HTTP_200_OK
        assert "Successfully logged out" in response.json()["message"]

    def test_password_change_success(self, client: TestClient, test_user_headers):
        """Test successful password change."""
        password_data = {
            "current_password": "testpassword",
            "new_password": "newtestpassword123"
        }

        response = client.post(
            "/api/v1/users/me/change-password",
            json=password_data,
            headers=test_user_headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert "Password changed successfully" in response.json()["message"]

    def test_password_change_wrong_current_password(self, client: TestClient, test_user_headers):
        """Test password change with wrong current password."""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newtestpassword123"
        }

        response = client.post(
            "/api/v1/users/me/change-password",
            json=password_data,
            headers=test_user_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Current password is incorrect" in response.json()["detail"]


class TestAuthenticationIntegration:
    """Test authentication integration scenarios."""

    def test_complete_registration_to_usage_flow(self, client: TestClient, sample_user_data, mock_ai_service):
        """Test complete flow from registration to using the API."""
        # 1. Register user
        registration_response = client.post("/api/v1/auth/register", json=sample_user_data)
        assert registration_response.status_code == status.HTTP_201_CREATED

        tokens = registration_response.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # 2. Get user profile
        profile_response = client.get("/api/v1/users/me", headers=headers)
        assert profile_response.status_code == status.HTTP_200_OK

        # 3. Try to add a paper
        paper_url = "https://arxiv.org/abs/2301.00001"
        paper_response = client.post(
            "/api/v1/papers/",
            params={"paper_url": paper_url},
            headers=headers
        )
        # This might fail due to mocking, but should at least authenticate
        assert paper_response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

    def test_token_expiration_handling(self, client: TestClient, test_user):
        """Test handling of expired tokens."""
        # This would require manipulating token expiration
        # For now, just test with invalid token format
        headers = {"Authorization": "Bearer expired.token.here"}

        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_multiple_concurrent_logins(self, client: TestClient, test_user):
        """Test multiple concurrent login sessions."""
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }

        # Create multiple sessions
        responses = []
        for _ in range(3):
            response = client.post("/api/v1/auth/login-json", json=login_data)
            assert response.status_code == status.HTTP_200_OK
            responses.append(response.json())

        # All tokens should be valid
        for tokens in responses:
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            profile_response = client.get("/api/v1/users/me", headers=headers)
            assert profile_response.status_code == status.HTTP_200_OK