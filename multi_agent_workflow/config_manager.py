#!/usr/bin/env python3
"""
Configuration Management for Enhanced Multi-Agent Workflow System

This module provides configuration management, project profiles,
environment-specific settings, and secret management capabilities.
"""

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


@dataclass
class ProjectProfile:
    """Project-specific configuration profile."""

    name: str
    description: str = ""
    template: Optional[str] = None
    default_stages: list[str] = field(default_factory=list)
    stage_config: dict[str, Any] = field(default_factory=dict)
    agent_config: dict[str, Any] = field(default_factory=dict)
    pause_points: list[str] = field(default_factory=list)
    retry_config: dict[str, int] = field(default_factory=dict)
    notification_config: dict[str, Any] = field(default_factory=dict)
    git_config: dict[str, Any] = field(default_factory=dict)
    environment: str = "development"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "default_stages": self.default_stages,
            "stage_config": self.stage_config,
            "agent_config": self.agent_config,
            "pause_points": self.pause_points,
            "retry_config": self.retry_config,
            "notification_config": self.notification_config,
            "git_config": self.git_config,
            "environment": self.environment,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectProfile":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class EnvironmentConfig:
    """Environment-specific configuration settings."""

    name: str
    base_url: Optional[str] = None
    api_endpoints: dict[str, str] = field(default_factory=dict)
    timeouts: dict[str, float] = field(default_factory=dict)
    retry_limits: dict[str, int] = field(default_factory=dict)
    resource_limits: dict[str, Any] = field(default_factory=dict)
    feature_flags: dict[str, bool] = field(default_factory=dict)
    logging_level: str = "INFO"
    debug_mode: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "api_endpoints": self.api_endpoints,
            "timeouts": self.timeouts,
            "retry_limits": self.retry_limits,
            "resource_limits": self.resource_limits,
            "feature_flags": self.feature_flags,
            "logging_level": self.logging_level,
            "debug_mode": self.debug_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentConfig":
        """Create from dictionary."""
        return cls(**data)


class SecretManager:
    """Manages encrypted storage and retrieval of secrets."""

    def __init__(self, key_file: Optional[Path] = None):
        """
        Initialize secret manager.

        Args:
            key_file: Path to encryption key file (generated if doesn't exist)
        """
        if key_file:
            self.key_file = key_file
        else:
            self.key_file = Path.home() / ".config" / "github-agent" / "secrets.key"

        self.key_file.parent.mkdir(parents=True, exist_ok=True)

        # Load or generate encryption key
        self._load_or_generate_key()

        # Initialize cipher
        self.cipher = Fernet(self.key)

    def _load_or_generate_key(self):
        """Load existing key or generate new one."""
        if self.key_file.exists():
            try:
                with open(self.key_file, "rb") as f:
                    self.key = f.read()
                logger.info("Loaded encryption key from file")
            except Exception as e:
                logger.error(f"Failed to load encryption key: {e}")
                self._generate_new_key()
        else:
            self._generate_new_key()

    def _generate_new_key(self):
        """Generate new encryption key and save it."""
        self.key = Fernet.generate_key()
        try:
            with open(self.key_file, "wb") as f:
                f.write(self.key)
            # Set restrictive permissions
            self.key_file.chmod(0o600)
            logger.info(f"Generated new encryption key: {self.key_file}")
        except Exception as e:
            logger.error(f"Failed to save encryption key: {e}")
            raise

    def encrypt_secret(self, secret: str) -> str:
        """
        Encrypt a secret string.

        Args:
            secret: Secret string to encrypt

        Returns:
            Base64-encoded encrypted secret
        """
        try:
            encrypted = self.cipher.encrypt(secret.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt secret: {e}")
            raise

    def decrypt_secret(self, encrypted_secret: str) -> str:
        """
        Decrypt a secret string.

        Args:
            encrypted_secret: Base64-encoded encrypted secret

        Returns:
            Decrypted secret string
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_secret.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            raise

    def store_secret(
        self, key: str, secret: str, secrets_file: Optional[Path] = None
    ) -> bool:
        """
        Store an encrypted secret in a file.

        Args:
            key: Secret key identifier
            secret: Secret value to encrypt and store
            secrets_file: Optional custom secrets file path

        Returns:
            True if successful, False otherwise
        """
        if secrets_file is None:
            secrets_file = self.key_file.parent / "secrets.json"

        try:
            # Load existing secrets
            if secrets_file.exists():
                with open(secrets_file) as f:
                    secrets_data = json.load(f)
            else:
                secrets_data = {}

            # Encrypt and store secret
            encrypted_secret = self.encrypt_secret(secret)
            secrets_data[key] = encrypted_secret

            # Save back to file
            with open(secrets_file, "w") as f:
                json.dump(secrets_data, f, indent=2)

            # Set restrictive permissions
            secrets_file.chmod(0o600)

            logger.info(f"Stored encrypted secret: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to store secret {key}: {e}")
            return False

    def retrieve_secret(
        self, key: str, secrets_file: Optional[Path] = None
    ) -> Optional[str]:
        """
        Retrieve and decrypt a secret from file.

        Args:
            key: Secret key identifier
            secrets_file: Optional custom secrets file path

        Returns:
            Decrypted secret value or None if not found
        """
        if secrets_file is None:
            secrets_file = self.key_file.parent / "secrets.json"

        try:
            if not secrets_file.exists():
                logger.warning(f"Secrets file not found: {secrets_file}")
                return None

            with open(secrets_file) as f:
                secrets_data = json.load(f)

            if key not in secrets_data:
                logger.warning(f"Secret key not found: {key}")
                return None

            encrypted_secret = secrets_data[key]
            return self.decrypt_secret(encrypted_secret)

        except Exception as e:
            logger.error(f"Failed to retrieve secret {key}: {e}")
            return None

    def list_secret_keys(self, secrets_file: Optional[Path] = None) -> list[str]:
        """
        List all secret keys in the file.

        Args:
            secrets_file: Optional custom secrets file path

        Returns:
            List of secret key identifiers
        """
        if secrets_file is None:
            secrets_file = self.key_file.parent / "secrets.json"

        try:
            if not secrets_file.exists():
                return []

            with open(secrets_file) as f:
                secrets_data = json.load(f)

            return list(secrets_data.keys())

        except Exception as e:
            logger.error(f"Failed to list secret keys: {e}")
            return []

    def delete_secret(self, key: str, secrets_file: Optional[Path] = None) -> bool:
        """
        Delete a secret from the file.

        Args:
            key: Secret key identifier
            secrets_file: Optional custom secrets file path

        Returns:
            True if successful, False otherwise
        """
        if secrets_file is None:
            secrets_file = self.key_file.parent / "secrets.json"

        try:
            if not secrets_file.exists():
                logger.warning(f"Secrets file not found: {secrets_file}")
                return False

            with open(secrets_file) as f:
                secrets_data = json.load(f)

            if key not in secrets_data:
                logger.warning(f"Secret key not found: {key}")
                return False

            del secrets_data[key]

            # Save back to file
            with open(secrets_file, "w") as f:
                json.dump(secrets_data, f, indent=2)

            logger.info(f"Deleted secret: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete secret {key}: {e}")
            return False


class WorkflowConfigManager:
    """Manages workflow configuration, profiles, and environments."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory for configuration files
        """
        if config_dir:
            self.config_dir = config_dir
        else:
            self.config_dir = Path(__file__).parent / "config"

        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Configuration files
        self.main_config_file = self.config_dir / "workflow.config.yaml"
        self.profiles_dir = self.config_dir / "profiles"
        self.environments_dir = self.config_dir / "environments"

        # Create subdirectories
        self.profiles_dir.mkdir(exist_ok=True)
        self.environments_dir.mkdir(exist_ok=True)

        # Initialize secret manager
        self.secret_manager = SecretManager()

        # Load configuration
        self.main_config = self._load_main_config()
        self.profiles: dict[str, ProjectProfile] = {}
        self.environments: dict[str, EnvironmentConfig] = {}

        self._load_profiles()
        self._load_environments()

        logger.info(f"Initialized WorkflowConfigManager at {self.config_dir}")

    def _load_main_config(self) -> dict[str, Any]:
        """Load main workflow configuration."""
        if self.main_config_file.exists():
            try:
                with open(self.main_config_file) as f:
                    config = yaml.safe_load(f) or {}
                logger.info("Loaded main configuration")
                return config
            except Exception as e:
                logger.error(f"Failed to load main config: {e}")
                return self._create_default_config()
        else:
            return self._create_default_config()

    def _create_default_config(self) -> dict[str, Any]:
        """Create and save default configuration."""
        default_config = {
            "version": "2.0.0",
            "default_profile": "standard",
            "default_environment": "development",
            "global_settings": {
                "max_retries": 3,
                "timeout": 300,
                "enable_git": True,
                "enable_notifications": False,
                "log_level": "INFO",
            },
            "agent_defaults": {
                "model": "claude-3-sonnet",
                "temperature": 0.7,
                "max_tokens": 4000,
                "timeout": 120,
            },
            "stage_defaults": {
                "timeout": 600,
                "max_retries": 2,
                "enable_pause_points": True,
            },
            "git_defaults": {
                "auto_commit": True,
                "auto_push": False,
                "branch_prefix": "workflow",
                "commit_message_template": "feat: {stage_name} - {description}",
            },
        }

        try:
            with open(self.main_config_file, "w") as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)
            logger.info(f"Created default configuration: {self.main_config_file}")
        except Exception as e:
            logger.error(f"Failed to save default config: {e}")

        return default_config

    def _load_profiles(self):
        """Load all project profiles."""
        for profile_file in self.profiles_dir.glob("*.yaml"):
            try:
                with open(profile_file) as f:
                    profile_data = yaml.safe_load(f)

                profile = ProjectProfile.from_dict(profile_data)
                self.profiles[profile.name] = profile
                logger.debug(f"Loaded profile: {profile.name}")

            except Exception as e:
                logger.error(f"Failed to load profile {profile_file}: {e}")

    def _load_environments(self):
        """Load all environment configurations."""
        for env_file in self.environments_dir.glob("*.yaml"):
            try:
                with open(env_file) as f:
                    env_data = yaml.safe_load(f)

                env = EnvironmentConfig.from_dict(env_data)
                self.environments[env.name] = env
                logger.debug(f"Loaded environment: {env.name}")

            except Exception as e:
                logger.error(f"Failed to load environment {env_file}: {e}")

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports dot notation, e.g., 'global_settings.max_retries')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        current = self.main_config

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default

        return current

    def set_config(self, key: str, value: Any):
        """
        Set a configuration value.

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        keys = key.split(".")
        current = self.main_config

        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Set the value
        current[keys[-1]] = value

        # Save configuration
        self._save_main_config()

    def _save_main_config(self):
        """Save main configuration to file."""
        try:
            with open(self.main_config_file, "w") as f:
                yaml.dump(self.main_config, f, default_flow_style=False, indent=2)
            logger.debug("Saved main configuration")
        except Exception as e:
            logger.error(f"Failed to save main config: {e}")

    def create_profile(
        self, name: str, description: str = "", template: Optional[str] = None, **kwargs
    ) -> ProjectProfile:
        """
        Create a new project profile.

        Args:
            name: Profile name
            description: Profile description
            template: Template name to base profile on
            **kwargs: Additional profile settings

        Returns:
            Created ProjectProfile
        """
        profile_data = {
            "name": name,
            "description": description,
            "template": template,
            **kwargs,
        }

        profile = ProjectProfile.from_dict(profile_data)
        self.profiles[name] = profile

        # Save to file
        profile_file = self.profiles_dir / f"{name}.yaml"
        try:
            with open(profile_file, "w") as f:
                yaml.dump(profile.to_dict(), f, default_flow_style=False, indent=2)
            logger.info(f"Created profile: {name}")
        except Exception as e:
            logger.error(f"Failed to save profile {name}: {e}")

        return profile

    def get_profile(self, name: str) -> Optional[ProjectProfile]:
        """Get a project profile by name."""
        return self.profiles.get(name)

    def list_profiles(self) -> list[str]:
        """List all available profile names."""
        return list(self.profiles.keys())

    def delete_profile(self, name: str) -> bool:
        """
        Delete a project profile.

        Args:
            name: Profile name to delete

        Returns:
            True if successful, False otherwise
        """
        if name not in self.profiles:
            logger.warning(f"Profile not found: {name}")
            return False

        try:
            # Remove from memory
            del self.profiles[name]

            # Remove file
            profile_file = self.profiles_dir / f"{name}.yaml"
            if profile_file.exists():
                profile_file.unlink()

            logger.info(f"Deleted profile: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete profile {name}: {e}")
            return False

    def create_environment(
        self, name: str, base_url: Optional[str] = None, **kwargs
    ) -> EnvironmentConfig:
        """
        Create a new environment configuration.

        Args:
            name: Environment name
            base_url: Base URL for the environment
            **kwargs: Additional environment settings

        Returns:
            Created EnvironmentConfig
        """
        env_data = {"name": name, "base_url": base_url, **kwargs}

        env = EnvironmentConfig.from_dict(env_data)
        self.environments[name] = env

        # Save to file
        env_file = self.environments_dir / f"{name}.yaml"
        try:
            with open(env_file, "w") as f:
                yaml.dump(env.to_dict(), f, default_flow_style=False, indent=2)
            logger.info(f"Created environment: {name}")
        except Exception as e:
            logger.error(f"Failed to save environment {name}: {e}")

        return env

    def get_environment(self, name: str) -> Optional[EnvironmentConfig]:
        """Get an environment configuration by name."""
        return self.environments.get(name)

    def list_environments(self) -> list[str]:
        """List all available environment names."""
        return list(self.environments.keys())

    def delete_environment(self, name: str) -> bool:
        """
        Delete an environment configuration.

        Args:
            name: Environment name to delete

        Returns:
            True if successful, False otherwise
        """
        if name not in self.environments:
            logger.warning(f"Environment not found: {name}")
            return False

        try:
            # Remove from memory
            del self.environments[name]

            # Remove file
            env_file = self.environments_dir / f"{name}.yaml"
            if env_file.exists():
                env_file.unlink()

            logger.info(f"Deleted environment: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete environment {name}: {e}")
            return False

    def resolve_config_for_workflow(
        self,
        profile_name: Optional[str] = None,
        environment_name: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Resolve complete configuration for a workflow run.

        Args:
            profile_name: Project profile to use
            environment_name: Environment to use
            overrides: Configuration overrides

        Returns:
            Resolved configuration dictionary
        """
        # Start with main config
        config = self.main_config.copy()

        # Apply environment settings
        env_name = environment_name or self.get_config(
            "default_environment", "development"
        )
        if env_name in self.environments:
            env = self.environments[env_name]
            config["environment"] = env.to_dict()

        # Apply profile settings
        prof_name = profile_name or self.get_config("default_profile", "standard")
        if prof_name in self.profiles:
            profile = self.profiles[prof_name]
            config["profile"] = profile.to_dict()

            # Merge profile-specific settings
            for key, value in profile.to_dict().items():
                if key not in ["name", "description"]:
                    config[key] = value

        # Apply overrides
        if overrides:
            self._deep_merge_config(config, overrides)

        # Resolve secrets
        config = self._resolve_secrets(config)

        return config

    def _deep_merge_config(self, base: dict[str, Any], override: dict[str, Any]):
        """Deep merge override configuration into base configuration."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge_config(base[key], value)
            else:
                base[key] = value

    def _resolve_secrets(self, config: dict[str, Any]) -> dict[str, Any]:
        """Resolve secret placeholders in configuration."""

        def resolve_value(value):
            if (
                isinstance(value, str)
                and value.startswith("${SECRET:")
                and value.endswith("}")
            ):
                # Extract secret key
                secret_key = value[9:-1]  # Remove ${SECRET: and }
                secret_value = self.secret_manager.retrieve_secret(secret_key)
                return secret_value if secret_value is not None else value
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            else:
                return value

        return resolve_value(config)

    # Secret management convenience methods
    def store_secret(self, key: str, secret: str) -> bool:
        """Store a secret."""
        return self.secret_manager.store_secret(key, secret)

    def retrieve_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret."""
        return self.secret_manager.retrieve_secret(key)

    def list_secrets(self) -> list[str]:
        """List all secret keys."""
        return self.secret_manager.list_secret_keys()

    def delete_secret(self, key: str) -> bool:
        """Delete a secret."""
        return self.secret_manager.delete_secret(key)


# Global configuration manager instance
config_manager = WorkflowConfigManager()
