"""Bot configuration module for MTEC schedule bot.

This module contains essential configuration parameters for bot operation,
including authentication tokens, secret keys, and administrator settings.
All sensitive data should be properly secured in production environments.
"""

from typing import Final

# Bot authentication token (should be kept secret in production)
TOKEN: Final[str] = "токен"  # TESTBOT

# Secret key for encryption operations
SECRET_KEY: Final[str] = "ключ"

# Administrator user ID for privileged operations
ADMIN: Final[int] = 000000000


