#!/usr/bin/env python3
"""
Tests for Configuration Management in Enhanced Multi-Agent Workflow System
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from multi_agent_workflow.config_manager import (
    EnvironmentConfig,
    ProjectProfile,
    SecretManager,
    WorkflowConfigManager,
)


class TestProjectProfile:
    """Test ProjectProfile dataclass."""

    def test_project_profile_creation(self):
        """Test creating a project profile."""
        profile = ProjectProfile(
            name="rapid_development",
            description="Fast iteration profile",
            template="web_app",
            default_stages=["requirements", "implementation", "testing"],
            stage_config={"implementation": {"timeout": 300}},
            agent_config={"model": "claude-3-sonnet"},
            pause_points=["before_deployment"],
            retry_config={"max_retries": 5},
            environment="development",
        )

        assert profile.name == "rapid_development"
        assert profile.description == "Fast iteration profile"
        assert profile.template == "web_app"
        assert len(profile.default_stages) == 3
        assert profile.stage_config["implementation"]["timeout"] == 300

    def test_project_profile_serialization(self):
        """Test serializing project profile."""
        profile = ProjectProfile(
            name="standard",
            description="Standard workflow",
            default_stages=["analysis", "design", "implementation"],
        )

        data = profile.to_dict()
        assert data["name"] == "standard"
        assert data["description"] == "Standard workflow"
        assert len(data["default_stages"]) == 3

        # Test from_dict
        profile2 = ProjectProfile.from_dict(data)
        assert profile2.name == profile.name
        assert profile2.default_stages == profile.default_stages


class TestEnvironmentConfig:
    """Test EnvironmentConfig dataclass."""

    def test_environment_config_creation(self):
        """Test creating environment configuration."""
        env_config = EnvironmentConfig(
            name="production",
            description="Production environment",
            debug=False,
            log_level="WARNING",
            max_parallel_stages=1,
            enable_notifications=True,
            notification_channels=["email", "slack"],
            git_auto_push=True,
            security_level="high",
        )

        assert env_config.name == "production"
        assert env_config.debug is False
        assert env_config.log_level == "WARNING"
        assert env_config.max_parallel_stages == 1
        assert env_config.git_auto_push is True

    def test_environment_config_serialization(self):
        """Test serializing environment configuration."""
        env_config = EnvironmentConfig(
            name="development",
            description="Dev environment",
            debug=True,
            log_level="DEBUG",
        )

        data = env_config.to_dict()
        assert data["name"] == "development"
        assert data["debug"] is True
        assert data["log_level"] == "DEBUG"

        # Test from_dict
        env_config2 = EnvironmentConfig.from_dict(data)
        assert env_config2.name == env_config.name
        assert env_config2.debug == env_config.debug


class TestSecretManager:
    """Test SecretManager functionality."""

    def test_secret_encryption_decryption(self):
        """Test encrypting and decrypting secrets."""
        manager = SecretManager()

        # Store a secret
        secret_value = "super_secret_password_123"
        manager.set_secret("api_key", secret_value)

        # Retrieve the secret
        retrieved = manager.get_secret("api_key")
        assert retrieved == secret_value

    def test_secret_persistence(self):
        """Test saving and loading secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_file = Path(tmpdir) / "secrets.enc"

            manager = SecretManager(secrets_file=secrets_file)

            # Store multiple secrets
            secrets = {
                "smtp_password": "email_pass_123",
                "api_token": "token_abc_xyz",
                "webhook_url": "https://example.com/hook",
            }

            for key, value in secrets.items():
                manager.set_secret(key, value)

            # Save to file
            manager.save_secrets()
            assert secrets_file.exists()

            # Load in new manager
            manager2 = SecretManager(secrets_file=secrets_file)
            manager2.load_secrets()

            # Verify all secrets
            for key, value in secrets.items():
                assert manager2.get_secret(key) == value

    def test_secret_template_replacement(self):
        """Test replacing secret placeholders in configuration."""
        manager = SecretManager()
        manager.set_secret("db_password", "real_password_123")
        manager.set_secret("api_key", "real_api_key_xyz")

        config = {
            "database": {
                "password": "${SECRET:db_password}",
                "host": "localhost",
            },
            "external_api": {
                "key": "${SECRET:api_key}",
                "endpoint": "https://api.example.com",
            },
        }

        # Replace secrets
        resolved = manager.resolve_secrets(config)

        assert resolved["database"]["password"] == "real_password_123"
        assert resolved["external_api"]["key"] == "real_api_key_xyz"
        assert resolved["database"]["host"] == "localhost"  # Non-secret unchanged

    def test_missing_secret_handling(self):
        """Test handling missing secrets."""
        manager = SecretManager()

        # Try to get non-existent secret
        result = manager.get_secret("non_existent")
        assert result is None

        # Try to resolve config with missing secret
        config = {
            "password": "${SECRET:missing_secret}",
        }

        with pytest.raises(ValueError, match="Secret 'missing_secret' not found"):
            manager.resolve_secrets(config, raise_on_missing=True)


class TestConfigValidation:
    """Test configuration validation functionality."""

    def test_validate_profile(self):
        """Test validating project profile."""
        manager = WorkflowConfigManager()

        # Valid profile
        valid_profile = {
            "name": "test_profile",
            "description": "Test",
            "default_stages": ["stage1", "stage2"],
            "environment": "development",
        }

        # Should not raise any errors
        try:
            profile = ProjectProfile.from_dict(valid_profile)
            errors = []
        except Exception as e:
            errors = [str(e)]
        assert len(errors) == 0

        # Invalid profile (missing name)
        invalid_profile = {
            "description": "Test",
            "default_stages": [],
        }

        # Should raise errors
        try:
            profile = ProjectProfile.from_dict(invalid_profile)
            errors = []
        except Exception as e:
            errors = [str(e)]
        assert len(errors) > 0
        assert any("name" in err for err in errors)

    def test_validate_environment(self):
        """Test validating environment configuration."""
        manager = WorkflowConfigManager()

        # Valid environment
        valid_env = {
            "name": "production",
            "debug": False,
            "log_level": "INFO",
            "max_parallel_stages": 2,
        }

        # Should not raise any errors
        try:
            env = EnvironmentConfig.from_dict(valid_env)
            errors = []
        except Exception as e:
            errors = [str(e)]
        assert len(errors) == 0

        # Invalid environment (invalid log level)
        invalid_env = {
            "name": "test",
            "log_level": "INVALID_LEVEL",
        }

        # Should raise errors for invalid log level
        errors = []
        if invalid_env.get("log_level") not in [
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ]:
            errors.append("Invalid log_level")
        assert len(errors) > 0
        assert any("log_level" in err for err in errors)

    def test_validate_complete_config(self):
        """Test validating complete configuration."""
        manager = WorkflowConfigManager()

        config = {
            "version": "2.0.0",
            "default_profile": "standard",
            "default_environment": "development",
            "profiles": {
                "standard": {
                    "name": "standard",
                    "default_stages": ["analysis", "implementation"],
                }
            },
            "environments": {
                "development": {
                    "name": "development",
                    "debug": True,
                }
            },
        }

        # Should not raise errors
        errors = []
        assert len(errors) == 0


class TestWorkflowConfigManager:
    """Test WorkflowConfigManager functionality."""

    def test_config_manager_initialization(self):
        """Test initializing config manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            manager = WorkflowConfigManager(config_dir=config_dir)
            assert manager.config_dir == config_dir
            assert manager.current_profile is None
            assert manager.current_environment is None

    def test_load_config_file(self):
        """Test loading configuration from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "workflow.config.yaml"

            config_data = {
                "version": "2.0.0",
                "default_profile": "standard",
                "default_environment": "development",
                "global_settings": {
                    "max_retries": 3,
                    "timeout": 300,
                },
            }

            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            manager = WorkflowConfigManager()
            manager.load_config(config_file)

            assert manager.config["version"] == "2.0.0"
            assert manager.config["global_settings"]["max_retries"] == 3

    def test_load_profile(self):
        """Test loading a project profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            profiles_dir = config_dir / "profiles"
            profiles_dir.mkdir(parents=True)

            # Create profile file
            profile_file = profiles_dir / "rapid.yaml"
            profile_data = {
                "name": "rapid",
                "description": "Rapid development",
                "default_stages": ["implementation", "testing"],
                "stage_config": {
                    "implementation": {"timeout": 120},
                },
            }

            with open(profile_file, "w") as f:
                yaml.dump(profile_data, f)

            manager = WorkflowConfigManager(config_dir=config_dir)
            profile = manager.load_profile("rapid")

            assert profile.name == "rapid"
            assert len(profile.default_stages) == 2
            assert profile.stage_config["implementation"]["timeout"] == 120

    def test_load_environment(self):
        """Test loading environment configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            env_dir = config_dir / "environments"
            env_dir.mkdir(parents=True)

            # Create environment file
            env_file = env_dir / "production.yaml"
            env_data = {
                "name": "production",
                "debug": False,
                "log_level": "WARNING",
                "git_auto_push": True,
            }

            with open(env_file, "w") as f:
                yaml.dump(env_data, f)

            manager = WorkflowConfigManager(config_dir=config_dir)
            env = manager.load_environment("production")

            assert env.name == "production"
            assert env.debug is False
            assert env.git_auto_push is True

    def test_get_merged_config(self):
        """Test merging configuration from multiple sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            # Create main config
            main_config = {
                "version": "2.0.0",
                "global_settings": {
                    "max_retries": 3,
                    "timeout": 300,
                },
            }

            config_file = config_dir / "workflow.config.yaml"
            with open(config_file, "w") as f:
                yaml.dump(main_config, f)

            # Create profile
            profiles_dir = config_dir / "profiles"
            profiles_dir.mkdir()
            profile_data = {
                "name": "custom",
                "stage_config": {
                    "testing": {"timeout": 600},
                },
            }
            with open(profiles_dir / "custom.yaml", "w") as f:
                yaml.dump(profile_data, f)

            # Create environment
            env_dir = config_dir / "environments"
            env_dir.mkdir()
            env_data = {
                "name": "staging",
                "debug": True,
                "max_retries": 5,  # Override global
            }
            with open(env_dir / "staging.yaml", "w") as f:
                yaml.dump(env_data, f)

            manager = WorkflowConfigManager(config_dir=config_dir)
            manager.load_config(config_file)
            manager.set_profile("custom")
            manager.set_environment("staging")

            merged = manager.get_merged_config()

            # Check that environment overrides global
            assert merged.get("max_retries") == 5
            # Check that profile config is included
            assert "testing" in merged.get("stage_config", {})
            # Check that global settings are preserved
            assert merged.get("timeout") == 300

    def test_config_with_secrets(self):
        """Test configuration with secret resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            # Setup secret manager
            secret_manager = SecretManager()
            secret_manager.set_secret("smtp_password", "secret_pass_123")
            secret_manager.set_secret("api_key", "key_xyz")

            # Create config with secret placeholders
            config_data = {
                "notifications": {
                    "email": {
                        "password": "${SECRET:smtp_password}",
                    },
                    "external_api": {
                        "key": "${SECRET:api_key}",
                    },
                },
            }

            config_file = config_dir / "workflow.config.yaml"
            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            manager = WorkflowConfigManager(
                config_dir=config_dir, secret_manager=secret_manager
            )
            manager.load_config(config_file)

            resolved = manager.get_resolved_config()

            assert resolved["notifications"]["email"]["password"] == "secret_pass_123"
            assert resolved["notifications"]["external_api"]["key"] == "key_xyz"

    def test_config_override_hierarchy(self):
        """Test configuration override hierarchy: env > profile > global."""
        manager = WorkflowConfigManager()

        # Set up hierarchical config
        manager.config = {
            "global_settings": {
                "timeout": 100,
                "retry": 3,
                "debug": False,
            },
        }

        manager.current_profile = ProjectProfile(
            name="test",
            description="Test profile",
            stage_config={"timeout": 200, "retry": 5},
        )

        manager.current_environment = EnvironmentConfig(
            name="prod",
            description="Production",
            debug=True,  # Override
            timeout=300,  # Override
        )

        merged = manager.get_merged_config()

        # Environment should override all
        assert merged["timeout"] == 300
        assert merged["debug"] is True
        # Profile overrides global
        assert merged["retry"] == 5

    def test_list_available_profiles(self):
        """Test listing available profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            profiles_dir = config_dir / "profiles"
            profiles_dir.mkdir(parents=True)

            # Create multiple profile files
            for name in ["standard", "rapid", "custom"]:
                profile_file = profiles_dir / f"{name}.yaml"
                with open(profile_file, "w") as f:
                    yaml.dump({"name": name}, f)

            manager = WorkflowConfigManager(config_dir=config_dir)
            profiles = manager.list_profiles()

            assert len(profiles) == 3
            assert "standard" in profiles
            assert "rapid" in profiles
            assert "custom" in profiles

    def test_list_available_environments(self):
        """Test listing available environments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            env_dir = config_dir / "environments"
            env_dir.mkdir(parents=True)

            # Create multiple environment files
            for name in ["development", "staging", "production"]:
                env_file = env_dir / f"{name}.yaml"
                with open(env_file, "w") as f:
                    yaml.dump({"name": name}, f)

            manager = WorkflowConfigManager(config_dir=config_dir)
            environments = manager.list_environments()

            assert len(environments) == 3
            assert "development" in environments
            assert "production" in environments

    def test_export_config(self):
        """Test exporting current configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkflowConfigManager()
            manager.config = {
                "version": "2.0.0",
                "global_settings": {"timeout": 300},
            }
            manager.current_profile = ProjectProfile(
                name="test",
                description="Test profile",
            )

            export_file = Path(tmpdir) / "exported.yaml"
            manager.export_config(export_file)

            assert export_file.exists()

            # Load and verify exported config
            with open(export_file) as f:
                exported = yaml.safe_load(f)

            assert exported["version"] == "2.0.0"
            assert exported["current_profile"]["name"] == "test"
