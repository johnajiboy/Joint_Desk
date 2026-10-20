from types import SimpleNamespace as NS

import pytest
from pydantic import BaseModel, Field

from kneedss import llm


class Facts(BaseModel):
    oks: int | None = Field(default=None, ge=0, le=48)
    quote: str


def response(*blocks, stop="end_turn"):
    return NS(stop_reason=stop, content=list(blocks), _request_id="req_test")


def tool_use(data):
    return NS(type="tool_use", name=llm.TOOL_NAME, input=data)


def text(t):
    return NS(type="text", text=t)


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = NS(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def no_env_model(monkeypatch):
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)


@pytest.fixture
def fake(monkeypatch):
    def install(*responses):
        client = FakeClient(*responses)
        monkeypatch.setattr(llm, "_client", lambda: client)
        return client
    return install


def test_returns_tool_input_and_sends_strict_tool(fake):
    client = fake(response(tool_use({"oks": 14, "quote": "OKS 14/48"}), stop="tool_use"))
    out = llm.complete_json("Read the letter.", "Letter text", Facts.model_json_schema())

    assert out == {"oks": 14, "quote": "OKS 14/48"}
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert "fallbacks" not in call and "betas" not in call
    assert call["tool_choice"] == {"type": "auto"}
    tool = call["tools"][0]
    assert tool["strict"] is True
    assert tool["input_schema"]["additionalProperties"] is False
    assert "maximum" not in tool["input_schema"]["properties"]["oks"]["anyOf"][0]


def test_retries_once_when_no_tool_call(fake):
    client = fake(response(text("Here are the facts...")), response(tool_use({"quote": "x"}), stop="tool_use"))
    assert llm.complete_json("s", "p", Facts.model_json_schema()) == {"quote": "x"}
    assert len(client.calls) == 2
    assert client.calls[1]["messages"][-1]["role"] == "user"


def test_gives_up_after_attempts(fake):
    fake(response(text("no")), response(text("still no")))
    with pytest.raises(llm.LLMError, match="No record_facts call"):
        llm.complete_json("s", "p", Facts.model_json_schema())


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_raises_on_refusal_or_truncation(fake, stop):
    fake(response(tool_use({"quote": "x"}), stop=stop))
    with pytest.raises(llm.LLMError):
        llm.complete_json("s", "p", Facts.model_json_schema())


def test_model_from_env(fake, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
    client = fake(response(tool_use({"quote": "x"}), stop="tool_use"))
    llm.complete_json("s", "p", Facts.model_json_schema())
    assert llm.model_name() == "claude-opus-5-5"
    assert client.calls[0]["model"] == "claude-opus-5-5"


def test_blank_env_uses_default(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "  ")
    assert llm.model_name() == "claude-sonnet-5-5"
