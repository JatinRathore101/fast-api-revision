"""
Password hashing and verification utilities.

All password-related cryptographic operations are centralized here so that
the hashing algorithm can be swapped in one place if needed.

Library: bcrypt
  - bcrypt is a slow, salted hashing algorithm designed specifically for
    passwords. Its cost factor makes brute-force attacks computationally
    expensive even with modern hardware.
  - A random salt is generated per password so that two identical passwords
    produce different hashes (prevents rainbow table attacks).

Security note:
  - Raw passwords are NEVER logged. Only operation start/completion is logged.
  - Hashed values are also not logged (they are long and not useful in logs).
"""

import bcrypt

from app.utils.logger import logger


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt with an auto-generated salt.

    Steps:
      1. Generate a unique cryptographic salt via bcrypt.gensalt()
      2. Hash the UTF-8 encoded password + salt together
      3. Decode the resulting bytes to a UTF-8 string for DB storage

    Args:
        plain_password (str): The raw password provided by the user.
                              Must NOT be logged or stored as-is.

    Returns:
        str: The bcrypt hash string (safe to store in the database).

    Example:
        hashed = hash_password("mySecret123")
        # hashed → "$2b$12$..."  (60-char bcrypt string)
    """
    # Log that hashing has started — never log the actual password value
    logger.debug("Password hashing started")

    # Step 1: Generate a new random salt for this specific password
    salt = bcrypt.gensalt()

    # Step 2: Hash the UTF-8 encoded password bytes with the salt
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)

    # Step 3: Decode bytes → str for storage in the VARCHAR column
    result = hashed.decode("utf-8")

    logger.info("Password hashed successfully")
    return result


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify that a plain-text password matches a stored bcrypt hash.

    Uses bcrypt's constant-time comparison to prevent timing-based attacks.
    bcrypt.checkpw() internally extracts the salt from the stored hash, so
    there is no need to manage the salt separately.

    Args:
        plain_password   (str): The raw password submitted by the user at login.
        hashed_password  (str): The bcrypt hash string retrieved from the database.

    Returns:
        bool: True if the password matches the hash, False otherwise.

    Example:
        is_valid = verify_password("mySecret123", stored_hash)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    """
    logger.debug("Password verification started")

    # bcrypt.checkpw handles encoding and salt extraction internally
    result = bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )

    # Log result without revealing which password was tested
    if result:
        logger.info("Password verification succeeded")
    else:
        logger.warning("Password verification failed — passwords do not match")

    return result
