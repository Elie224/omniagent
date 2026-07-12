"""Tests de la couche resilience (errors + saga)."""
import pytest


def test_classify_transient():
    from omniagent.core.resilience.errors import classify_error, ErrorCategory
    assert classify_error("Connection timeout") == ErrorCategory.TRANSIENT
    assert classify_error("Service 503 unavailable") == ErrorCategory.TRANSIENT


def test_classify_rate_limit():
    from omniagent.core.resilience.errors import classify_error, ErrorCategory
    assert classify_error("429 Too Many Requests") == ErrorCategory.RATE_LIMIT
    assert classify_error("Rate limit exceeded") == ErrorCategory.RATE_LIMIT


def test_classify_fatal():
    from omniagent.core.resilience.errors import classify_error, ErrorCategory
    assert classify_error("401 Unauthorized") == ErrorCategory.FATAL
    assert classify_error("403 Forbidden") == ErrorCategory.FATAL


def test_classify_user_error():
    from omniagent.core.resilience.errors import classify_error, ErrorCategory
    assert classify_error("400 Bad Request: invalid email") == ErrorCategory.USER_ERROR


def test_wrap_exception_preserves_category():
    from omniagent.core.resilience.errors import wrap_exception, ErrorCategory
    e = wrap_exception(RuntimeError("connection refused"))
    assert e.category == ErrorCategory.TRANSIENT
    assert e.is_retryable
    e2 = wrap_exception(RuntimeError("401 Unauthorized"))
    assert e2.category == ErrorCategory.FATAL
    assert not e2.is_retryable


@pytest.mark.asyncio
async def test_saga_success():
    from omniagent.core.resilience.saga import SagaBuilder
    saga = (SagaBuilder(user_id="u1")
            .step("a", lambda s: _async_return({"a": 1}))
            .step("b", lambda s: _async_return({"b": 2})))
    result = await saga.execute()
    assert result["status"] == "completed"
    assert saga.status == "completed"


@pytest.mark.asyncio
async def test_saga_compensation_on_failure():
    from omniagent.core.resilience.saga import SagaBuilder
    compensations: list[str] = []

    async def step_a(s):
        return {"a": 1}

    async def step_b(s):
        raise RuntimeError("step_b failed")

    async def step_c(s):
        return {"c": 3}

    async def comp_a(s):
        compensations.append("a")

    async def comp_b(s):
        compensations.append("b")

    saga = (SagaBuilder(user_id="u1")
            .step("a", step_a, comp_a)
            .step("b", step_b, comp_b)
            .step("c", step_c))
    result = await saga.execute()
    assert result["status"] == "rolled_back"
    # Seules les etapes executees (a, b) sont compensees
    assert "a" in compensations
    assert "b" not in compensations  # comp_b levee elle-meme
    assert "c" not in compensations  # pas executee


@pytest.mark.asyncio
async def test_saga_state_propagation():
    from omniagent.core.resilience.saga import SagaBuilder
    saga = (SagaBuilder(user_id="u1")
            .step("a", lambda s: _async_return({"x": 10}))
            .step("b", lambda s: _async_return({"y": s["a"]["x"] * 2})))
    result = await saga.execute()
    assert result["status"] == "completed"
    assert saga.state["a"]["x"] == 10
    assert saga.state["b"]["y"] == 20


async def _async_return(value):
    return value