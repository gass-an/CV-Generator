from cv_generator_shared.security import SecureKeyGenerator, extract_prefix, hash_key


def test_generated_keys_have_expected_format_and_are_random() -> None:
    generator = SecureKeyGenerator()
    first = generator.generate()
    second = generator.generate()

    assert first.value.startswith(f"cvg_{first.prefix}_")
    assert len(first.prefix) >= 10
    assert len(first.value.split("_", 2)[2]) >= 43
    assert extract_prefix(first.value) == first.prefix
    assert first.key_hash == hash_key(first.value)
    assert first.value != second.value
    assert first.prefix != second.prefix
    assert first.value not in repr(first)
    assert first.key_hash not in repr(first)


def test_extract_prefix_rejects_absent_and_malformed_values() -> None:
    assert extract_prefix(None) is None
    assert extract_prefix("") is None
    assert extract_prefix("not-a-key") is None
    assert extract_prefix("cvg_short_secret") is None
    assert extract_prefix("cvg_abcdefghij_secret with spaces" + "x" * 43) is None
