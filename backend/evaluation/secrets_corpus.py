"""
Labelled samples for measuring secret detection (precision / recall).

Each case: (case_id, file name, True if the file contains a real-looking
secret, content). All "secrets" here are random strings made up for this
corpus; none is a real credential.

Values in a vendor's key format (AWS, GitHub, Stripe, Slack, Google, private
keys, URLs with a password) are assembled from pieces at import time, so this
file never contains a complete secret-shaped string. Otherwise secret
scanners (GitHub push protection included) would block it as a leaked key.
"""


def _fake(*parts: str) -> str:
    """Join pieces of a made-up secret (see module docstring)."""
    return "".join(parts)


CASES = [
    # ── contains a secret ───────────────────────────────────────────
    ("aws-key", "config.py", True, f'AWS_ACCESS_KEY_ID = "{_fake("AKIA", "ZQ3HXKW7PLM2V9QD")}"\n'),
    ("github-token", "deploy.py", True, f'GH = "{_fake("ghp", "_8fK2mQ7xL0vR4tYw9Nb3Hj6Fd1Sa5Ge0Zc7P")}"\n'),
    ("stripe-live", "billing.py", True, f'STRIPE_KEY = "{_fake("sk", "_live_", "4eC39HqLyjWDarjtT1zdp7dc")}"\n'),
    ("slack-token", "notify.py", True,
     f'SLACK = "{_fake("xox", "b-", "1234567890123-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx")}"\n'),
    ("private-key", "key.pem", True,
     _fake("-----BEGIN RSA ", "PRIVATE KEY-----\nMIIEowIBAAKCAQEA7bq\n-----END RSA ", "PRIVATE KEY-----\n")),
    ("db-url", "settings.py", True, f'MONGO_URI = "{_fake("mongo", "db://admin:Rk82mQz7Lp@db.internal:27017/app")}"\n'),
    ("hex-token-keyword", "client.py", True, 'INTERNAL_TOKEN = "f3a9c0d17b2e4e8a9c6d5b4a3f2e1d0c9b8a7f6e"\n'),
    ("base64-token-kwarg", "client.py", True, 'client = Client(token="Zx8Kq2LmP9vR4tYw7Nb3Hj6Fd1Sa5Ge0")\n'),
    ("password-literal", "db.py", True, 'DB_PASSWORD = "Wint3r-Is-Coming-42"\n'),
    ("dict-secret", "app.py", True, 'config = {"client_secret": "q8XmL2pV7rT4wY9nB3hJ6fD1sA5gE0zC"}\n'),
    ("entropy-weak-hint", "app.py", True, 'cookie_key = "Qm9vX2Fq7Lz3Rt8Yp1Wc5Nv6Hb4Kd2Gs"\n'),
    ("env-file", ".env", True, "SECRET_KEY=9f2c7a1e5b8d4f6a0c3e9b7d1a5f8c2e\nDEBUG=False\n"),
    ("yaml-password", "values.yaml", True, "database:\n  password: Sup3rS3cret-Prod!\n"),
    ("js-api-key", "api.js", True, f'const apiKey = "{_fake("AIza", "SyD4kL9mQ2xR7tV3wY8nB1hJ5fC6sA0gE2z")}";\n'),
    # ── no secret (look-alikes) ─────────────────────────────────────
    ("placeholder-change-me", "config.py", False, 'SECRET_KEY = "CHANGE_ME_TO_A_RANDOM_32_BYTE_HEX_STRING"\n'),
    ("placeholder-your-key", "config.py", False, 'API_KEY = "your-api-key-here"\n'),
    ("env-example", ".env.example", False, "SECRET_KEY=CHANGE_ME\nGITHUB_TOKEN=\nDB_PASSWORD=<password>\n"),
    ("env-reference", "config.py", False, 'password = os.environ["DB_PASSWORD"]\ntoken = settings.GITHUB_TOKEN\n'),
    ("template-reference", "workflow.yml", False, "env:\n  TOKEN: ${{ secrets.TOKEN }}\n"),
    ("sentence", "messages.py", False, 'PASSWORD_HINT = "Password must contain at least 12 characters"\n'),
    ("bcrypt-hash", "fixtures.py", False, 'password_hash = "$2b$12$KIXQ8yW2vH6jV1nE4rT7Ue9oZ3cL5aB0dF8gH2iJ4kL6mN8pQ0rS"\n'),
    ("commit-sha", "release.py", False, 'commit_sha = "418137c38154ab1e7d428bc86eb6fe2608cf644b"\n'),
    ("uuid", "models.py", False, 'DEFAULT_ID = "550e8400-e29b-41d4-a716-446655440000"\n'),
    ("integrity-hash", "lock.py", False, 'integrity = "sha512-Qm9vX2Fq7Lz3Rt8Yp1Wc5Nv6Hb4Kd2GsZx8Kq2LmP9vR4tYw7Nb3Hj6Fd1Sa5Ge0"\n'),
    ("function-call", "auth.py", False, "token = create_access_token(user)\npassword = get_password()\n"),
    ("sort-key", "query.py", False, 'sort_key = "created_at"\nprimary_key = "employee_id"\n'),
    ("url-no-credentials", "config.py", False, 'MONGO_URI = "mongodb://localhost:27017"\n'),
]
