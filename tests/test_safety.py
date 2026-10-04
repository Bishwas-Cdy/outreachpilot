import pytest

from app.schemas import Signal
from app.services.research import fallback_hypotheses
from app.services.url_safety import UnsafeURLError, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://127.0.0.1",
        "http://10.0.0.5",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "http://[::1]",
    ],
)
def test_ssrf_private_url_blocking(url: str) -> None:
    with pytest.raises(UnsafeURLError):
        validate_public_url(url)


def test_no_fabricated_evidence_in_deterministic_fallback() -> None:
    signal = Signal(
        name="demo-led sales motion",
        evidence="Request a demo for our enterprise platform",
        source_url="https://example.com",
        confidence=0.9,
    )
    results = fallback_hypotheses([signal])
    assert len(results) == 1
    assert signal.evidence in results[0].evidence
    assert signal.source_url in results[0].evidence
    assert results[0].hypothesis.startswith("Hypothesis:")
    assert fallback_hypotheses([]) == []
