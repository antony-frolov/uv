from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).parent.parent
TREE_DIR = PROJECT_DIR / "tests" / "tree"

# Snapshot filters
TIME = (r"(\d+.)?\d+(ms|s)", "[TIME]")
SHUTDOWN = (
    textwrap.dedent(
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        SHUTDOWN
        """
    ).lstrip(),
    "",
)
STDOUT = ("STDOUT .*", "STDOUT [PATH]")
STDERR = ("STDERR .*", "STDERR [PATH]")

TREE = (re.escape(str(TREE_DIR)), "[TREE]")
CWD = (re.escape(os.getcwd()), "[CWD]")
TRACEBACK = ("TRACEBACK .*", "TRACEBACK [TRACEBACK]")
DEFAULT_FILTERS = [TIME, STDOUT, STDERR, TRACEBACK, TREE, CWD]


def new(
    extra_backend_paths: list[str] | None = None,
    tree_path: Path | None = TREE_DIR,
) -> subprocess.Popen:
    extra_backend_paths = extra_backend_paths or []

    env = os.environ.copy()
    # Add the test backends to the Python path
    env["PYTHONPATH"] = ":".join(
        [str(path) for path in [PROJECT_DIR / "backends"] + extra_backend_paths]
    )

    return subprocess.Popen(
        [sys.executable, str(PROJECT_DIR / "hookd.py")]
        + ([str(tree_path)] if tree_path is not None else []),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def send(process, lines):
    process.stdin.write("\n".join(lines) + "\n")


def assert_snapshot(value, expected, filters=None):
    filters = filters or []
    for pattern, replace in filters:
        value = re.sub(pattern, replace, value)
    print(value)
    assert value == textwrap.dedent(expected).lstrip()


def test_shutdown():
    daemon = new()
    daemon.communicate(input="shutdown\n")
    assert daemon.returncode == 0


def test_sigkill():
    daemon = new()
    daemon.kill()
    daemon.wait()
    assert daemon.returncode == -9


def test_sigterm():
    daemon = new()
    daemon.terminate()
    daemon.wait()
    assert daemon.returncode == -15


def test_run_invalid_backend():
    daemon = new()
    send(
        daemon,
        [
            "run",
            "backend_does_not_exist",
            "",
            "build_wheel",
            "",
            "",
            "",
        ],
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling backend_does_not_exist.build_wheel(wheel_directory='[TREE]', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR MissingBackendModule Failed to import the backend 'backend_does_not_exist'
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_invalid_hook():
    daemon = new()
    send(daemon, ["run", "ok_backend", "", "hook_does_not_exist"])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        ERROR InvalidHookName The name 'hook_does_not_exist' is not valid hook. Expected one of: 'build_wheel', 'prepare_metadata_for_build_wheel', 'get_requires_for_build_wheel', 'build_editable', 'prepare_metadata_for_build_editable', 'get_requires_for_build_editable', 'build_sdist', 'get_requires_for_build_sdist'
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_build_wheel_ok():
    """
    Uses a mock backend to test the `build_wheel` hook.
    """
    daemon = new()
    send(daemon, ["run", "ok_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling ok_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_build_sdist_ok():
    """
    Uses a mock backend to test the `build_sdist` hook.
    """
    daemon = new()
    send(daemon, ["run", "ok_backend", "", "build_sdist", "foo", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT sdist_directory
        EXPECT config_settings
        DEBUG Calling ok_backend.build_sdist(sdist_directory='[TREE]/foo', config_settings=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_sdist_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_build_editable_ok():
    """
    Uses a mock backend to test the `build_editable` hook.
    """
    daemon = new()
    send(daemon, ["run", "ok_backend", "", "build_editable", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling ok_backend.build_editable(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_editable_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_get_requires_for_build_wheel_ok():
    """
    Uses a mock backend to test the `get_requires_for_build_wheel` hook.
    """
    daemon = new()
    send(daemon, ["run", "ok_backend", "", "get_requires_for_build_wheel", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT config_settings
        DEBUG Calling ok_backend.get_requires_for_build_wheel(config_settings=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK ['fake', 'build', 'wheel', 'requires']
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_prepare_metadata_for_build_wheel_ok():
    """
    Uses a mock backend to test the `prepare_metadata_for_build_wheel` hook.
    """
    daemon = new()
    send(
        daemon, ["run", "ok_backend", "", "prepare_metadata_for_build_wheel", "foo", ""]
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT metadata_directory
        EXPECT config_settings
        DEBUG Calling ok_backend.prepare_metadata_for_build_wheel(metadata_directory='[TREE]/foo', config_settings=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK prepare_metadata_fake_dist_info_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_get_requires_for_build_editable_ok():
    """
    Uses a mock backend to test the `get_requires_for_build_editable` hook.
    """
    daemon = new()
    send(daemon, ["run", "ok_backend", "", "get_requires_for_build_editable", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT config_settings
        DEBUG Calling ok_backend.get_requires_for_build_editable(config_settings=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK ['fake', 'build', 'editable', 'requires']
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_prepare_metadata_for_build_editable_ok():
    """
    Uses a mock backend to test the `prepare_metadata_for_build_editable` hook.
    """
    daemon = new()
    send(
        daemon,
        ["run", "ok_backend", "", "prepare_metadata_for_build_editable", "foo", ""],
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT metadata_directory
        EXPECT config_settings
        DEBUG Calling ok_backend.prepare_metadata_for_build_editable(metadata_directory='[TREE]/foo', config_settings=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK prepare_metadata_fake_dist_info_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_get_requires_for_build_sdist_ok():
    """
    Uses a mock backend to test the `get_requires_for_build_sdist` hook.
    """
    daemon = new()
    send(daemon, ["run", "ok_backend", "", "get_requires_for_build_sdist", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT config_settings
        DEBUG Calling ok_backend.get_requires_for_build_sdist(config_settings=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK ['fake', 'build', 'sdist', 'requires']
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_invalid_config_settings():
    """
    Sends invalid JSON for the `config_settings` argument which should result in a non_fatal error.
    """
    daemon = new()
    send(
        daemon,
        ["run", "ok_backend", "", "get_requires_for_build_wheel", "not_valid_json"],
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT config_settings
        ERROR MalformedHookArgument Malformed content for argument 'config_settings': 'not_valid_json'
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_build_wheel_multiple_times():
    """
    Uses a mock backend to test running a hook repeatedly.
    """
    daemon = new()
    for _ in range(5):
        send(daemon, ["run", "ok_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        """.rstrip()
        + """
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling ok_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]"""
        * 5
        + """
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_build_wheel_error():
    """
    Uses a mock backend that throws an error to test error reporting.
    """
    daemon = new()
    send(daemon, ["run", "err_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling err_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR HookRuntimeError Oh no
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_error_not_fatal():
    """
    Uses a mock backend that throws an error to ensure errors are not fatal and another hook can be run.
    """
    daemon = new()
    send(daemon, ["run", "err_backend", "", "build_wheel", "foo", "", ""])
    send(daemon, ["run", "err_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling err_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR HookRuntimeError Oh no
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling err_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR HookRuntimeError Oh no
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_base_exception_error_not_fatal(tmp_path: Path):
    """
    Uses a mock backend that throws an error to ensure errors are not fatal and another hook can be run.
    """
    (tmp_path / "base_exc_backend.py").write_text(
        textwrap.dedent(
            """
            def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
                raise BaseException("Oh no")
            """
        )
    )

    daemon = new(extra_backend_paths=[tmp_path])
    send(daemon, ["run", "base_exc_backend", "", "build_wheel", "foo", "", ""])
    send(daemon, ["run", "base_exc_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling base_exc_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR HookRuntimeError Oh no
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling base_exc_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR HookRuntimeError Oh no
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_error_in_backend_module(tmp_path: Path):
    """
    Tests a backend that raises an error on import.
    """
    (tmp_path / "import_err_backend.py").write_text("raise RuntimeError('oh no')")
    daemon = new(extra_backend_paths=[tmp_path])
    send(daemon, ["run", "import_err_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling import_err_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR BackendImportError Backend threw an exception during import: oh no
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_unsupported_hook_empty(tmp_path: Path):
    """
    Tests a backend without any hooks.
    """
    (tmp_path / "empty_backend.py").write_text("")
    daemon = new(extra_backend_paths=[tmp_path])
    send(daemon, ["run", "empty_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling empty_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR UnsupportedHook The hook 'build_wheel' is not supported by the backend. The backend does not support any known hooks.
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_unsupported_hook_partial(tmp_path: Path):
    """
    Tests a backend without the requested hook.
    """
    (tmp_path / "partial_backend.py").write_text(
        textwrap.dedent(
            """
            def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
                raise BaseException("Oh no")

            def some_other_utility():
                pass
            """
        )
    )

    daemon = new(extra_backend_paths=[tmp_path])
    send(daemon, ["run", "partial_backend", "", "build_sdist", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT sdist_directory
        EXPECT config_settings
        DEBUG Calling partial_backend.build_sdist(sdist_directory='[TREE]/foo', config_settings=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR UnsupportedHook The hook 'build_sdist' is not supported by the backend. The backend supports: 'build_wheel'
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


@pytest.mark.parametrize("separator", [":", "."])
def test_run_cls_backend(separator):
    """
    Tests a backend namespaced to a class.
    """
    daemon = new()
    send(
        daemon,
        ["run", f"cls_backend{separator}Class", "", "build_wheel", "foo", "", ""],
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        f"""
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling cls_backend{separator}Class.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


@pytest.mark.parametrize("separator", [":", "."])
def test_run_obj_backend(separator):
    """
    Tests a backend namespaced to an object.
    """
    daemon = new()
    send(
        daemon, ["run", f"obj_backend{separator}obj", "", "build_wheel", "foo", "", ""]
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        f"""
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling obj_backend{separator}obj.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_in_tree_backend():
    """
    Tests a backend in the source tree
    """
    daemon = new()
    send(
        daemon,
        [
            "run",
            "in_tree",
            "directory_does_not_exist",
            "in_tree_backend",
            "",
            "build_wheel",
            "foo",
            "",
            "",
        ],
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling in_tree.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_submodule_backend():
    """
    Tests a backend namespaced to an submodule.
    """
    daemon = new()
    send(
        daemon, ["run", "submodule_backend.submodule", "", "build_wheel", "foo", "", ""]
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling submodule_backend.submodule.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_submodule_backend_invalid_import():
    """
    Tests a backend namespaced to an submodule but imported as an attribute
    """
    daemon = new()
    send(
        daemon,
        [
            "run",
            "submodule_backend:submodule",
            "",
            "build_wheel",
            "",
            "",
            "",
        ],
    )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling submodule_backend:submodule.build_wheel(wheel_directory='[TREE]', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR MissingBackendAttribute Failed to find attribute 'submodule_backend:submodule' in the backend module 'submodule_backend'
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    assert stderr == ""
    assert daemon.returncode == 0


def test_run_stdout_capture():
    """
    Tests capture of stdout from a backend.
    """
    daemon = new()
    send(daemon, ["run", "stdout_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling stdout_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    stdout_parts = stderr_parts = None
    for line in stdout.splitlines():
        parts = line.split()
        if parts[0] == "STDOUT":
            stdout_parts = parts
        elif parts[0] == "STDERR":
            stderr_parts = parts

    assert len(stdout_parts) == 2
    assert len(stderr_parts) == 2

    assert_snapshot(
        Path(stdout_parts[1]).read_text(),
        """
        hello
        world
        """,
    )
    assert Path(stderr_parts[1]).read_text() == ""

    assert stderr == ""
    assert daemon.returncode == 0


def test_run_stderr_capture():
    """
    Tests capture of stderr from a backend.
    """
    daemon = new()
    send(daemon, ["run", "stderr_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling stderr_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    stdout_parts = stderr_parts = None
    for line in stdout.splitlines():
        parts = line.split()
        if parts[0] == "STDOUT":
            stdout_parts = parts
        elif parts[0] == "STDERR":
            stderr_parts = parts

    assert len(stdout_parts) == 2
    assert len(stderr_parts) == 2
    assert Path(stdout_parts[1]).read_text() == ""
    assert_snapshot(
        Path(stderr_parts[1]).read_text(),
        """
        hello
        world
        """,
    )

    assert stderr == ""
    assert daemon.returncode == 0


def test_run_stdout_capture_multiple_hook_runs():
    """
    Tests capture of stdout from a backend, each hook run should get a unique file
    """
    COUNT = 2
    daemon = new()
    for i in range(COUNT):
        send(
            daemon,
            ["run", "stdout_backend", "", "build_wheel", "foo", f'{{"run": {i}}}', ""],
        )
    stdout, stderr = daemon.communicate(input="shutdown\n")
    print(stdout)

    all_stdout_parts = []
    all_stderr_parts = []
    for line in stdout.splitlines():
        parts = line.split()
        if parts[0] == "STDOUT":
            all_stdout_parts.append(parts)
        elif parts[0] == "STDERR":
            all_stderr_parts.append(parts)

    # We should have a result for each hook run
    assert len(all_stdout_parts) == COUNT
    assert len(all_stderr_parts) == COUNT

    # Each run should write unique output to their file
    for i, stdout_parts in enumerate(all_stdout_parts):
        assert_snapshot(
            Path(stdout_parts[1]).read_text(),
            f"""
            writing config_settings
            run = {i}
            """,
        )
    for i, stderr_parts in enumerate(all_stderr_parts):
        assert Path(stderr_parts[1]).read_text() == ""

    assert stderr == ""
    assert daemon.returncode == 0


def test_run_stdout_capture_subprocess():
    """
    Tests capture of stdout from a backend that writes to stdout from a subprocess.
    """
    daemon = new()
    send(daemon, ["run", "stdout_subprocess_backend", "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        """
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling stdout_subprocess_backend.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        OK build_wheel_fake_path
        DEBUG Ran hook in [TIME]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=DEFAULT_FILTERS,
    )
    stdout_parts = stderr_parts = None
    for line in stdout.splitlines():
        parts = line.split()
        if parts[0] == "STDOUT":
            stdout_parts = parts
        elif parts[0] == "STDERR":
            stderr_parts = parts

    assert len(stdout_parts) == 2
    assert len(stderr_parts) == 2

    assert_snapshot(
        Path(stdout_parts[1]).read_text(),
        """
        hello world
        """,
    )
    assert Path(stderr_parts[1]).read_text() == ""

    assert stderr == ""
    assert daemon.returncode == 0


@pytest.mark.parametrize("backend", ["hatchling.build", "poetry.core.masonry.api"])
def test_run_real_backend_build_wheel_error(backend: str):
    """
    Sends an path that does not exist to a real "build_wheel" hook.
    """
    try:
        importlib.import_module(backend)
    except ImportError:
        pytest.skip(f"build backend {backend!r} is not installed")

    daemon = new()
    send(daemon, ["run", backend, "", "build_wheel", "foo", "", ""])
    stdout, stderr = daemon.communicate(input="shutdown\n")
    assert_snapshot(
        stdout,
        f"""
        DEBUG Changed working directory to [TREE]
        READY
        EXPECT action
        EXPECT build-backend
        EXPECT backend-path
        EXPECT hook-name
        EXPECT wheel_directory
        EXPECT config_settings
        EXPECT metadata_directory
        DEBUG Calling {backend}.build_wheel(wheel_directory='[TREE]/foo', config_settings=None, metadata_directory=None)
        DEBUG Parsed hook inputs in [TIME]
        STDOUT [PATH]
        STDERR [PATH]
        ERROR HookRuntimeError [MESSAGE]
        TRACEBACK [TRACEBACK]
        READY
        EXPECT action
        SHUTDOWN
        """,
        filters=(
            DEFAULT_FILTERS + [("HookRuntimeError .*", "HookRuntimeError [MESSAGE]")]
        ),
    )
    assert stderr == ""
    assert daemon.returncode == 0
