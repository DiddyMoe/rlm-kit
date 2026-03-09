"""Tests verifying bare except: was replaced with except Exception: (RF-087)."""

import re


class TestNoBareExcepts:
    """Verify that environment templates use except Exception: not bare except:."""

    def _check_no_bare_except(self, source: str, label: str) -> None:
        """Assert there are no bare `except:` (without an exception type) in source."""
        # Match 'except:' but not 'except SomeType:' or 'except (A, B):'
        bare_except_pattern = re.compile(r"\bexcept\s*:")
        matches = bare_except_pattern.findall(source)
        assert len(matches) == 0, f"Found {len(matches)} bare except: in {label}"

    def test_modal_exec_script_no_bare_except(self) -> None:
        from rlm.environments.exec_script_templates import MODAL_EXEC_SCRIPT_TEMPLATE

        self._check_no_bare_except(MODAL_EXEC_SCRIPT_TEMPLATE, "MODAL_EXEC_SCRIPT_TEMPLATE")

    def test_docker_exec_script_no_bare_except(self) -> None:
        from rlm.environments.exec_script_templates import DOCKER_EXEC_SCRIPT_TEMPLATE

        self._check_no_bare_except(DOCKER_EXEC_SCRIPT_TEMPLATE, "DOCKER_EXEC_SCRIPT_TEMPLATE")

    def test_prime_repl_templates_no_bare_except(self) -> None:
        import inspect

        from rlm.environments import prime_repl

        source = inspect.getsource(prime_repl)
        self._check_no_bare_except(source, "prime_repl.py")

    def test_daytona_repl_templates_no_bare_except(self) -> None:
        import inspect

        from rlm.environments import daytona_repl

        source = inspect.getsource(daytona_repl)
        self._check_no_bare_except(source, "daytona_repl.py")

    def test_e2b_repl_templates_no_bare_except(self) -> None:
        import inspect

        from rlm.environments import e2b_repl

        source = inspect.getsource(e2b_repl)
        self._check_no_bare_except(source, "e2b_repl.py")
