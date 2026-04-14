"""
Shared validation constants and patterns.

Centralizing regex patterns here ensures that the same validation logic
is applied consistently across every route handler that needs it. If the
email format requirement ever changes, this is the single place to update.

Usage in handlers:
    from app.utils.validators import EMAIL_REGEX

    if not EMAIL_REGEX.match(email):
        errors.append("email is not a valid email address")
"""

import re

# ─── Email Validation Pattern ────────────────────────────────────────────────────
# Matches standard email addresses of the form local@domain.tld
#
# Pattern breakdown:
#   ^                   → start of string
#   [a-z0-9._%+\-]+     → local part: lowercase letters, digits, dots, underscores,
#                          percent signs, plus signs, or hyphens (one or more)
#   @                   → literal '@' separator
#   [a-z0-9.\-]+        → domain name: letters, digits, dots, hyphens (one or more)
#   \.                  → literal dot before the TLD
#   [a-z]{2,}           → TLD: at least two lowercase letters (e.g., com, io, dev)
#   $                   → end of string
#
# Note: email addresses are lowercased before matching in the handlers,
# so uppercase input like "User@Example.COM" is handled correctly.
EMAIL_REGEX = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
