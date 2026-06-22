"""Tests for advanced features: vision, tool calling, embeddings"""
import pytest
import json


# === Vision Tests ===

def test_create_image_message_url():
    from core.advanced_features import VisionSupport
    msg = VisionSupport.create_image_message(
        "What's in this image?",
        ["https://example.com/image.jpg"]
    )
    assert msg["role"] == "user"
    assert isinstance(msg["content"], list)
    assert len(msg["content"]) == 2  # text + image


def test_create_image_message_base64():
    from core.advanced_features import VisionSupport, ImageContent
    # Test with explicit ImageContent object
    img = ImageContent(base64_data="abc123", media_type="image/png")
    msg = VisionSupport.create_image_message("Describe this", [img])
    assert isinstance(msg["content"], list)
    assert len(msg["content"]) == 2  # text + image


def test_is_vision_message():
    from core.advanced_features import VisionSupport
    msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Hello"},
            {"type": "image_url", "image_url": {"url": "https://example.com/img.jpg"}}
        ]
    }
    assert VisionSupport.is_vision_message(msg) is True

    regular_msg = {"role": "user", "content": "Hello"}
    assert VisionSupport.is_vision_message(regular_msg) is False


# === Tool Calling Tests ===

def test_register_tool():
    from core.advanced_features import ToolCallingSupport, ToolDefinition
    tc = ToolCallingSupport()

    tool = ToolDefinition(
        name="get_weather",
        description="Get weather for a location",
        parameters={
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"}
            },
            "required": ["location"]
        }
    )

    tc.register_tool(tool, lambda location: {"temp": 72})
    assert tc.has_tool("get_weather") is True
    assert tc.has_tool("other_tool") is False


def test_get_tools_for_request():
    from core.advanced_features import ToolCallingSupport, ToolDefinition
    tc = ToolCallingSupport()

    tool = ToolDefinition("test_tool", "Test", {"type": "object", "properties": {}})
    tc.register_tool(tool)

    tools = tc.get_tools_for_request()
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "test_tool"


def test_execute_tool():
    from core.advanced_features import ToolCallingSupport, ToolDefinition, ToolCall
    tc = ToolCallingSupport()

    def weather_handler(location, unit="celsius"):
        return {"location": location, "temp": 25, "unit": unit}

    tool = ToolDefinition("get_weather", "Get weather", {
        "type": "object",
        "properties": {"location": {"type": "string"}, "unit": {"type": "string"}}
    })
    tc.register_tool(tool, weather_handler)

    result = tc.execute_tool(ToolCall(id="tc_1", name="get_weather", arguments={"location": "NYC"}))
    assert result["location"] == "NYC"


def test_execute_tool_no_handler():
    from core.advanced_features import ToolCallingSupport, ToolDefinition, ToolCall
    tc = ToolCallingSupport()
    tc.register_tool(ToolDefinition("no_handler", "No handler", {}))

    with pytest.raises(ValueError):
        tc.execute_tool(ToolCall(id="tc_1", name="no_handler", arguments={}))


def test_parse_tool_calls():
    from core.advanced_features import ToolCallingSupport
    response = {
        "choices": [{
            "message": {
                "tool_calls": [{
                    "id": "tc_1",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "NYC"}'
                    }
                }]
            }
        }]
    }

    tool_calls = ToolCallingSupport.parse_tool_calls(response)
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "get_weather"
    assert tool_calls[0].arguments == {"location": "NYC"}


def test_create_tool_response():
    from core.advanced_features import ToolCallingSupport
    response = ToolCallingSupport.create_tool_response("tc_1", {"temp": 25})
    assert response["role"] == "tool"
    assert response["tool_call_id"] == "tc_1"
    assert json.loads(response["content"]) == {"temp": 25}


# === Embedding Tests ===

def test_calculate_similarity():
    from core.advanced_features import EmbeddingSupport
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    assert EmbeddingSupport.calculate_similarity(vec1, vec2) == 1.0

    vec3 = [0.0, 1.0, 0.0]
    assert EmbeddingSupport.calculate_similarity(vec1, vec3) == 0.0


def test_calculate_similarity_different_length():
    from core.advanced_features import EmbeddingSupport
    with pytest.raises(ValueError):
        EmbeddingSupport.calculate_similarity([1.0], [1.0, 0.0])


def test_find_most_similar():
    from core.advanced_features import EmbeddingSupport
    query = [1.0, 0.0, 0.0]
    embeddings = [
        {"id": 1, "embedding": [0.9, 0.1, 0.0], "text": "similar"},
        {"id": 2, "embedding": [0.0, 0.0, 1.0], "text": "different"},
        {"id": 3, "embedding": [0.8, 0.2, 0.0], "text": "also similar"}
    ]

    results = EmbeddingSupport.find_most_similar(query, embeddings, top_k=2)
    assert len(results) == 2
    assert results[0]["id"] == 1  # Most similar first


def test_prepare_embedding_request():
    from core.advanced_features import EmbeddingSupport
    request = EmbeddingSupport.prepare_embedding_request(["hello", "world"])
    assert request["input"] == ["hello", "world"]
    assert "model" in request
