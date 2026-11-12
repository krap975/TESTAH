"""Compare old HTTP baselines while checking explicitly additive migration defaults."""


def assert_saved_record(actual: dict, expected: dict, additive_defaults: dict) -> None:
    current = dict(actual)
    for key, default in additive_defaults.items():
        if key not in expected:
            assert current.pop(key) == default, key
    assert current == expected
