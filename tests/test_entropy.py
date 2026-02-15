"""Tests for entropy-based secret detection."""

from __future__ import annotations

from composearr.analyzers.entropy import calculate_shannon_entropy, is_likely_secret, rate_secret_strength


class TestShannonEntropy:
    def test_empty_string(self):
        assert calculate_shannon_entropy("") == 0.0

    def test_single_char(self):
        assert calculate_shannon_entropy("a") == 0.0

    def test_all_same(self):
        assert calculate_shannon_entropy("aaaaaaaaaa") == 0.0

    def test_high_entropy(self):
        # Random-looking string should have high entropy
        entropy = calculate_shannon_entropy("aB3$xZ9!kL7@mN2#")
        assert entropy > 0.7

    def test_low_entropy_repeated(self):
        entropy = calculate_shannon_entropy("aaaaabbbbb")
        assert entropy < 0.5

    def test_returns_normalized_0_to_1(self):
        for s in ["test", "abcdefghijklmnop", "aB3$xZ9!kL7@mN2#pQ5&"]:
            e = calculate_shannon_entropy(s)
            assert 0.0 <= e <= 1.0


class TestIsLikelySecret:
    def test_short_value_not_secret(self):
        is_secret, _ = is_likely_secret("abc123")
        assert not is_secret

    def test_random_api_key(self):
        is_secret, score = is_likely_secret("xK9mN2pQ5rT8vW3yB6cF1hJ4lA7sD0g")
        assert is_secret
        assert score >= 0.75

    def test_base64_token(self):
        is_secret, _ = is_likely_secret("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert is_secret

    def test_url_not_secret(self):
        is_secret, _ = is_likely_secret("https://api.example.com/v1/webhook")
        assert not is_secret

    def test_file_path_not_secret(self):
        is_secret, _ = is_likely_secret("/opt/application/config/settings.yaml")
        assert not is_secret

    def test_domain_not_secret(self):
        is_secret, _ = is_likely_secret("com.example.application")
        assert not is_secret

    def test_normal_config_value(self):
        is_secret, _ = is_likely_secret("unless-stopped")
        assert not is_secret

    def test_timezone_not_secret(self):
        is_secret, _ = is_likely_secret("Australia/Sydney")
        assert not is_secret

    def test_custom_threshold(self):
        value = "xK9mN2pQ5rT8vW3yB6cF1hJ4lA7sD0g"
        is_secret_strict, _ = is_likely_secret(value, threshold=0.95)
        is_secret_loose, _ = is_likely_secret(value, threshold=0.5)
        # Loose threshold should still catch it
        assert is_secret_loose


class TestRateSecretStrength:
    def test_empty_value(self):
        rating, entropy = rate_secret_strength("")
        assert rating == "weak"
        assert entropy == 0.0

    def test_short_password(self):
        rating, _ = rate_secret_strength("pass1234")
        assert rating == "weak"

    def test_medium_password(self):
        rating, _ = rate_secret_strength("MyP@ssw0rd123456")
        assert rating == "medium"

    def test_strong_secret(self):
        rating, _ = rate_secret_strength("xK9mN2pQ5rT8vW3yB6cF1hJ4lA7sD0g")
        assert rating == "strong"

    def test_low_entropy_long_string(self):
        # Long but repetitive — should be weak
        rating, _ = rate_secret_strength("aaaaaaaabbbbbbbb")
        assert rating == "weak"

    def test_returns_entropy(self):
        _, entropy = rate_secret_strength("xK9mN2pQ5rT8vW3y")
        assert 0.0 < entropy <= 1.0
