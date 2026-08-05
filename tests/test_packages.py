from gh_pages_pypi_demo_lib import greeting
from gh_pages_pypi_demo_app import main


def test_greeting():
    assert greeting("PyPI") == "Hello, PyPI! (served from GitHub Pages)"


def test_app_main_with_name(capsys):
    main(["Pages"])
    assert capsys.readouterr().out.strip() == "Hello, Pages! (served from GitHub Pages)"


def test_app_main_default(capsys):
    main([])
    assert capsys.readouterr().out.strip() == "Hello, world! (served from GitHub Pages)"
