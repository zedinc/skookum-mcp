import pytest

from src.config import Config, ConfigError, config_path, load_config


def write_config(tmp_path, monkeypatch, text):
    path = tmp_path / "config.toml"
    path.write_text(text)
    monkeypatch.setenv("SKOOKUM_CONFIG", str(path))
    return path


def test_load_config_reads_profile_and_defaults(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch, 'profile = "us"\n[defaults]\npt = "typographic_point"\n')
    assert load_config() == Config(profile="us", defaults={"pt": "typographic_point"})


@pytest.mark.parametrize("text, fragment", [
    ('profile = "martian"', "profile must be one of"),
    ("[defaults]\nzzz = 'x'", "not an ambiguous unit symbol"),
    ("[defaults]\nton = 'heavy_ton'", "not a candidate"),
    ("defaults = 3", "[defaults] must be a table"),
    ("profile = ", "Invalid TOML"),
])
def test_load_config_validates(tmp_path, monkeypatch, text, fragment):
    write_config(tmp_path, monkeypatch, text)
    with pytest.raises(ConfigError) as exc:
        load_config()
    assert fragment in str(exc.value)


def test_missing_env_config_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("SKOOKUM_CONFIG", str(tmp_path / "nope.toml"))
    with pytest.raises(ConfigError, match="does not exist"):
        config_path()


def test_xdg_config_is_used_when_no_env(tmp_path, monkeypatch):
    monkeypatch.delenv("SKOOKUM_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert load_config() == Config()
    (tmp_path / "skookum").mkdir()
    (tmp_path / "skookum" / "config.toml").write_text('profile = "imperial"\n')
    assert load_config().profile == "imperial"
