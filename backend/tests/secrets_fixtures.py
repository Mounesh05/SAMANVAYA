"""Generate deterministic, never-issued credentials for scanner tests.

Provider-shaped values exist only while the tests run. No stored API token is
needed to verify matching, severity classification, or complete redaction.
"""

import random
import string


def synthetic_token(provider: str, variant: int = 0, fixture: bool = False) -> str:
    rng = random.Random(f"samanvaya-scanner-fixture:{provider}:{variant}")

    def body(length: int) -> str:
        marker = "fake" if fixture else ""
        return marker + "".join(rng.choice(string.ascii_letters + string.digits)
                                for _ in range(length - len(marker)))

    if provider == "aws-secret":
        value = body(40)
        return value[:20] + "/" + value[21:]
    if provider == "slack":
        return "xoxb-" + "".join(rng.choice(string.digits) for _ in range(12)) + "-" + \
            "".join(rng.choice(string.digits) for _ in range(12)) + "-" + body(24)
    if provider == "sendgrid":
        return "SG." + body(22) + "." + body(43)
    prefix, length = {
        "github": ("ghp_", 36),
        "gitlab": ("glpat-", 20),
        "stripe": ("sk_live_", 24),
        "stripe-restricted": ("rk_live_", 24),
    }[provider]
    return prefix + body(length)
