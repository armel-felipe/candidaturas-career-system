from agent.turn_context import PreLlmHookBlocked
import gateway.run as gateway_run


def test_expected_pre_llm_hook_block_is_suppressed_at_gateway_boundary():
    assert gateway_run._should_suppress_gateway_error(
        PreLlmHookBlocked("supervisor dispatched the turn")
    ) is True


def test_unexpected_gateway_errors_are_not_suppressed():
    assert gateway_run._should_suppress_gateway_error(RuntimeError("provider down")) is False
