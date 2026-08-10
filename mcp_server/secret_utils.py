"""
Robust secret loading utilities for Databricks Apps.

Tries multiple methods to load secrets:
1. Direct from environment variable (if secret is injected via app.yaml env)
2. Via dbutils.secrets (if available in Databricks runtime)
3. Via WorkspaceClient.secrets.get_secret (SDK method)
4. Alternative environment variable names
"""

import os
import base64
import logging

logger = logging.getLogger(__name__)


def get_secret(
    env_var_name: str,
    secret_scope: str,
    secret_key: str,
    base64_encoded: bool = False
) -> str:
    """
    Try to get secret from multiple sources in order of preference.
    
    Args:
        env_var_name: Name of environment variable to check first
        secret_scope: Databricks secret scope name
        secret_key: Secret key name within the scope
        base64_encoded: If True, base64-decode the secret value
        
    Returns:
        The secret value, or empty string if not found
    """
    
    # 1. Try dbutils.secrets FIRST (most reliable, same as working test notebook)
    try:
        from databricks.sdk.runtime import dbutils
        value = dbutils.secrets.get(scope=secret_scope, key=secret_key)
        if value:
            logger.info(f"{env_var_name} loaded from dbutils.secrets ({secret_scope}/{secret_key})")
            return _decode_if_needed(value, base64_encoded)
    except Exception as e:
        logger.debug(f"dbutils.secrets not available: {e}")
    
    # 2. Try direct environment variable (from app.yaml env section with resources)
    value = os.getenv(env_var_name)
    if value and not value.startswith("${"):  # Skip if template var wasn't substituted
        logger.info(f"{env_var_name} loaded from environment variable")
        return _decode_if_needed(value, base64_encoded)
    
    # 3. Try WorkspaceClient.secrets.get_secret (SDK method)
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        secret_response = w.secrets.get_secret(scope=secret_scope, key=secret_key)
        if secret_response and secret_response.value:
            logger.info(f"{env_var_name} loaded from WorkspaceClient.secrets")
            return _decode_if_needed(secret_response.value, base64_encoded)
    except Exception as e:
        logger.debug(f"WorkspaceClient.secrets not available: {e}")
    
    # 4. Try alternative env var names (secret_key with different formats)
    for alt_name in [
        secret_key,
        secret_key.replace("-", "_"),
        secret_key.upper(),
        secret_key.replace("-", "_").upper()
    ]:
        value = os.getenv(alt_name)
        if value:
            logger.info(f"{env_var_name} loaded from env var '{alt_name}'")
            return _decode_if_needed(value, base64_encoded)
    
    logger.warning(f"{env_var_name} not found in any source")
    return ""


def _decode_if_needed(value: str, base64_encoded: bool) -> str:
    """Decode base64 if needed."""
    if not base64_encoded or not value:
        return value
    try:
        return base64.b64decode(value).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to base64-decode secret: {e}")
        return value
