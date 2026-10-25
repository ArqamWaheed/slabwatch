from slabwatch import config


def test_secret_file_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SECRETS_DIR", tmp_path)
    monkeypatch.delenv("SLAB_TEST_KEY", raising=False)
    assert config.env("SLAB_TEST_KEY", "dflt") == "dflt"
    (tmp_path / "SLAB_TEST_KEY").write_text("abc123\n")
    assert config.env("SLAB_TEST_KEY") == "abc123"
    (tmp_path / "SLAB_TEST_KEY").write_text('SLAB_TEST_KEY="xyz"\n')
    assert config.env("SLAB_TEST_KEY") == "xyz"
    monkeypatch.setenv("SLAB_TEST_KEY", "from-env")  # a real env var wins
    assert config.env("SLAB_TEST_KEY") == "from-env"
