from rlm.environments.exec_script_templates import (
    DOCKER_EXEC_SCRIPT_TEMPLATE,
    MODAL_EXEC_SCRIPT_TEMPLATE,
    render_exec_script,
)


class TestExecScriptTemplates:
    def test_modal_template_contains_required_helpers(self) -> None:
        assert "def llm_query(" in MODAL_EXEC_SCRIPT_TEMPLATE
        assert "def llm_query_batched(" in MODAL_EXEC_SCRIPT_TEMPLATE
        assert "def FINAL_VAR(" in MODAL_EXEC_SCRIPT_TEMPLATE
        assert "def SHOW_VARS(" in MODAL_EXEC_SCRIPT_TEMPLATE

    def test_docker_template_contains_required_helpers(self) -> None:
        assert "def llm_query(" in DOCKER_EXEC_SCRIPT_TEMPLATE
        assert "def llm_query_batched(" in DOCKER_EXEC_SCRIPT_TEMPLATE
        assert "def FINAL_VAR(" in DOCKER_EXEC_SCRIPT_TEMPLATE
        assert "def SHOW_VARS(" in DOCKER_EXEC_SCRIPT_TEMPLATE

    def test_render_exec_script_applies_replacements(self) -> None:
        template = "hello __X__ and __Y__"
        rendered = render_exec_script(template, {"__X__": "A", "__Y__": "B"})
        assert rendered == "hello A and B"
