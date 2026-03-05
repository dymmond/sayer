from pathlib import Path


def test_taskfile_uses_sayer_settings_variable() -> None:
    taskfile = Path(__file__).resolve().parents[1] / "Taskfile.yaml"
    content = taskfile.read_text(encoding="utf-8")

    assert "LILYA_SETTINGS_MODULE" not in content
    assert "SAYER_SETTINGS_MODULE: tests.settings.TestSettings" in content
