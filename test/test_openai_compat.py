import os
import base64
import openai
import pytest

# Set up the OpenAI client to point to the local server (OpenAI v1+ interface)
client = openai.OpenAI(base_url=os.environ.get("OPENAI_BASE_URL", "http://localhost:9192/v1"), api_key="sk-local-test")

AWQ_MODEL_NAMES = [
    "Qwen/Qwen2.5-VL-7B-Instruct-AWQ",
    "Qwen/Qwen2.5-VL-32B-Instruct-AWQ"
]


def test_list_models():
    response = client.models.list()
    assert response.object == "list"
    # At least one of the supported models (7B or 32B) should be present
    assert any(model.id in AWQ_MODEL_NAMES for model in response.data)


def test_chat_completions_with_image():
    # Load image and encode as base64
    image_path = os.path.join("data", "demo.jpeg")
    with open(image_path, "rb") as img_file:
        b64_image = base64.b64encode(img_file.read()).decode("utf-8")
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                {"type": "text", "text": "Describe this image."}
            ]
        }
    ]
    # Use the currently loaded model (from the API)
    current_model = client.models.list().data[0].id
    response = client.chat.completions.create(
        model=current_model,
        messages=messages,
        stream=False
    )
    assert response.choices and response.choices[0].message.content


def test_function_call_response():
    messages = [
        {"role": "user", "content": "What is the weather like in Paris?"}
    ]
    functions = [
        {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "The city to get the weather for"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "Temperature unit"}
                },
                "required": ["city"]
            }
        }
    ]
    current_model = client.models.list().data[0].id
    response = client.chat.completions.create(
        model=current_model,
        messages=messages,
        functions=functions,
        function_call="auto",
        stream=False
    )
    # The model may return a tool/function call or just text; check for a valid response
    msg = response.choices[0].message
    assert msg.content or getattr(msg, "function_call", None)
