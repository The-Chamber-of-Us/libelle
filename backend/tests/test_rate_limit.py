from services.rate_limit import InMemoryIntakeRateLimiter


def test_per_ip_limit_blocks_after_configured_count():
    limiter = InMemoryIntakeRateLimiter(
        enabled=True,
        per_ip_limit=2,
        per_email_limit=10,
        global_limit=10,
        clock=lambda: 100.0,
    )

    assert limiter.check(ip_address="203.0.113.10", email="first@example.com").allowed
    assert limiter.check(ip_address="203.0.113.10", email="second@example.com").allowed

    decision = limiter.check(ip_address="203.0.113.10", email="third@example.com")

    assert not decision.allowed
    assert decision.scope == "ip"
    assert decision.retry_after_seconds == 60


def test_per_email_limit_blocks_across_ips():
    limiter = InMemoryIntakeRateLimiter(
        enabled=True,
        per_ip_limit=10,
        per_email_limit=1,
        global_limit=10,
        clock=lambda: 100.0,
    )

    assert limiter.check(ip_address="203.0.113.10", email="Person@Example.com").allowed

    decision = limiter.check(ip_address="203.0.113.11", email="person@example.com")

    assert not decision.allowed
    assert decision.scope == "email"


def test_global_limit_blocks_across_ips_and_emails():
    limiter = InMemoryIntakeRateLimiter(
        enabled=True,
        per_ip_limit=10,
        per_email_limit=10,
        global_limit=2,
        clock=lambda: 100.0,
    )

    assert limiter.check(ip_address="203.0.113.10", email="first@example.com").allowed
    assert limiter.check(ip_address="203.0.113.11", email="second@example.com").allowed

    decision = limiter.check(ip_address="203.0.113.12", email="third@example.com")

    assert not decision.allowed
    assert decision.scope == "global"


def test_disabled_limiter_allows_repeated_submissions():
    limiter = InMemoryIntakeRateLimiter(
        enabled=False,
        per_ip_limit=1,
        per_email_limit=1,
        global_limit=1,
        clock=lambda: 100.0,
    )

    assert limiter.check(ip_address="203.0.113.10", email="person@example.com").allowed
    assert limiter.check(ip_address="203.0.113.10", email="person@example.com").allowed
