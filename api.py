from dotenv import load_dotenv
load_dotenv(override=True)
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import Optional, List, Union, Dict, Any
import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, GenerationConfig
from qwen_vl_utils import process_vision_info
import uvicorn
import json
from datetime import datetime
import logging
import time
import psutil
import GPUtil
import base64
from PIL import Image
import io
import argparse
import shutil
import os
import asyncio
import unicodedata
from threading import Thread
from queue import Queue
from threading import Event
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables
model = None
current_loaded_model = None
processor = None
device = "cuda" if torch.cuda.is_available() else "cpu"

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=9192, help="Which port to listen on for HTTP API requests")
parser.add_argument('--size', type=str, choices=['7B', '32B'], default='7B', help="Which Qwen 2.5 VL AWQ model size to load (7B or 32B)")
parser.add_argument(
    '--resume',
    action='store_true',
    help="Attempt to resume partial downloads if possible"
)
parser.add_argument('--log', action='store_true', help="Enable logging of request, response, and tool/function definitions")
parser.add_argument('--api_key', action='store_true', help="Enforce API key from .env API_KEY variable on all requests")
args = parser.parse_args()

# Load .env if --api_key is set
if args.api_key:
    load_dotenv()
    API_KEY = os.getenv('API_KEY')
    if not API_KEY:
        raise RuntimeError("API_KEY must be set in .env when using --api_key flag.")

# Model selection logic for AWQ only
AWQ_MODEL_NAMES = {
    '7B': 'Qwen/Qwen2.5-VL-7B-Instruct-AWQ',
    '32B': 'Qwen/Qwen2.5-VL-32B-Instruct-AWQ',
}

MODEL_NAME = AWQ_MODEL_NAMES[args.size]

class ImageURL(BaseModel):
    url: str

class MessageContent(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[Dict[str, str]] = None

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ['text', 'image_url']:
            raise ValueError(f"Invalid content type: {v}")
        return v

class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[MessageContent]]

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ['system', 'user', 'assistant']:
            raise ValueError(f"Invalid role: {v}")
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: Union[str, List[Any]]) -> Union[str, List[MessageContent]]:
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return [MessageContent(**item) if isinstance(item, dict) else item for item in v]
        raise ValueError("Content must be either a string or a list of content items")

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    response_format: Optional[Dict[str, str]] = None
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, Any]]] = None

class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]

class ModelCard(BaseModel):
    id: str
    created: int
    owned_by: str
    permission: List[Dict[str, Any]] = []
    root: Optional[str] = None
    parent: Optional[str] = None
    capabilities: Optional[Dict[str, bool]] = None
    context_window: Optional[int] = None
    max_tokens: Optional[int] = None

class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelCard]

def process_base64_image(base64_string: str) -> Image.Image:
    """Process base64 image data and return PIL Image"""
    try:
        # Remove data URL prefix if present
        if 'base64,' in base64_string:
            base64_string = base64_string.split('base64,')[1]

        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        return image
    except Exception as e:
        logger.error(f"Error processing base64 image: {str(e)}")
        raise ValueError(f"Invalid base64 image data: {str(e)}")

def log_system_info():
    """Log system resource information"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        gpu_info = []
        if torch.cuda.is_available():
            for gpu in GPUtil.getGPUs():
                gpu_info.append({
                    'id': gpu.id,
                    'name': gpu.name,
                    'load': f"{gpu.load*100}%",
                    'memory_used': f"{gpu.memoryUsed}MB/{gpu.memoryTotal}MB",
                    'temperature': f"{gpu.temperature}°C"
                })
        logger.info(f"System Info - CPU: {cpu_percent}%, RAM: {memory.percent}%, "
                   f"Available RAM: {memory.available/1024/1024/1024:.1f}GB")
        if gpu_info:
            logger.info(f"GPU Info: {gpu_info}")
    except Exception as e:
        logger.warning(f"Failed to log system info: {str(e)}")

def clean_generated_text(text):
    """Clean generated text by removing special characters and control tokens, but preserve newlines."""
    # Remove common special tokens that might appear in generation
    text = re.sub(r'\u003c\|.*?\|\u003e', '', text)
    
    # Remove diamond characters and other common artifacts
    text = re.sub(r'[◆◇■□▲△▼▽★☆♦♢]', '', text)
    
    # Remove other control characters, but preserve newlines (\n, \r)
    text = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1F\x7F-\x9F]', '', text)
    
    return text

def initialize_model(model_name: str):
    """Initialize the model and processor"""
    global model, processor, current_loaded_model
    logger.info(f"Loading AWQ model: {model_name}")
    processor = AutoProcessor.from_pretrained(model_name, use_fast=True)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        attn_implementation="flash_attention_2",
        device_map="auto",
    )
    current_loaded_model = model_name
    logger.info(f"Model {model_name} loaded successfully.")

initialize_model(MODEL_NAME)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application initialization...")
    try:
        yield
    finally:
        logger.info("Shutting down application...")
        global model, processor
        if model is not None:
            try:
                del model
                torch.cuda.empty_cache()
                logger.info("Model unloaded and CUDA cache cleared")
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")
        model = None
        processor = None
        logger.info("Shutdown complete")

app = FastAPI(
    title="Qwen2.5-VL API",
    description="OpenAI-compatible API for Qwen2.5-VL vision-language model",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_valid_unicode(s):
    try:
        s.encode('utf-8').decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False

class StreamingLogitsProcessor:
    def __init__(self, tokenizer, queue, input_length):
        self.tokenizer = tokenizer
        self.queue = queue
        self.generated_tokens = []
        self.last_length = 0
        # Track the length of the input to skip prompt tokens
        self.input_length = input_length
        
    def __call__(self, input_ids, scores):
        # Get the latest token that was just generated
        if len(input_ids[0]) > self.last_length:
            new_token = input_ids[0][self.last_length:].cpu()
            self.generated_tokens.extend(new_token.tolist())
            
            # Decode only the newly generated tokens (excluding the prompt)
            text = self.tokenizer.decode(self.generated_tokens, skip_special_tokens=True)
            
            # Clean the text to remove special characters and control tokens
            if len(self.generated_tokens) > self.input_length:
                text = self.tokenizer.decode(self.generated_tokens[self.input_length:], skip_special_tokens=True)
                text = clean_generated_text(text)
            else:
                text = ""
            
            # Remove trailing replacement character if present
            text = text.rstrip('�')
            
            # Put the new token in the queue
            self.queue.put(text)
            
            # Update last length
            self.last_length = len(input_ids[0])
        
        return scores

from fastapi import Depends

# Dependency to enforce API key if required
def enforce_api_key(request: Request):
    if args.api_key:
        key = request.headers.get("Authorization")
        if not key or not key.startswith("Bearer ") or key.split(" ", 1)[1] != API_KEY:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key.")

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest, _: None = Depends(enforce_api_key)):
    """Handle chat completion requests with vision support"""

    if request.model != current_loaded_model:
        raise HTTPException(
            status_code=400,
            detail=f"Requested model '{request.model}' not loaded. Current model is {current_loaded_model}"
        )

    try:
        request_start_time = time.time()
        logger.info(f"Received chat completion request for model: {request.model}")
        if args.log:
            logger.info(f"Request content: {request.model_dump_json()}")

        messages = []
        for msg in request.messages:
            if isinstance(msg.content, str):
                messages.append({"role": msg.role, "content": msg.content})
            else:
                processed_content = []
                for content_item in msg.content:
                    if content_item.type == "text":
                        processed_content.append({
                            "type": "text",
                            "text": content_item.text
                        })
                    elif content_item.type == "image_url":
                        if "url" in content_item.image_url:
                            if content_item.image_url["url"].startswith("data:image"):
                                processed_content.append({
                                    "type": "image",
                                    "image": process_base64_image(content_item.image_url["url"])
                                })
                messages.append({"role": msg.role, "content": processed_content})

        text = processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        image_inputs, video_inputs = process_vision_info(messages)

        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt"
        ).to(device)

        # Prepare bad_words_ids to block <unk> tokens (replacement char)
        unk_token_id = processor.tokenizer.unk_token_id
        bad_words_ids = [[unk_token_id]] if unk_token_id is not None else None

        if request.stream:
            # For true streaming, we'll use a custom logits processor
            token_queue = Queue()
            
            # Get the input length to track where assistant response starts
            input_length = len(inputs.input_ids[0])
            
            # Create a logits processor to stream tokens as they're generated
            streaming_processor = StreamingLogitsProcessor(
                processor.tokenizer, 
                token_queue,
                input_length
            )
            
            # Stream the tokens as they're generated
            async def event_generator():
                message_id = f"chatcmpl-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Start generation in a separate thread
                def generate_tokens():
                    try:
                        model.generate(
                            **inputs,
                            max_new_tokens=request.max_tokens,
                            temperature=request.temperature,
                            top_p=request.top_p,
                            do_sample=True,
                            logits_processor=[streaming_processor],
                            bad_words_ids=bad_words_ids
                        )
                    except Exception as e:
                        logger.error(f"Generation error: {str(e)}")
                        # Put None in the queue to signal an error
                        token_queue.put(None)
                
                thread = Thread(target=generate_tokens)
                thread.start()
                
                # Stream tokens as they become available
                last_text = ""
                try:
                    while thread.is_alive() or not token_queue.empty():
                        try:
                            # Try to get the next chunk of text with a timeout
                            current_text = await asyncio.to_thread(
                                lambda: token_queue.get(block=True, timeout=0.1)
                            )
                            
                            # Check for error signal
                            if current_text is None:
                                break
                                
                            # Get the new part (delta)
                            if len(current_text) > len(last_text):
                                delta = current_text[len(last_text):]
                                last_text = current_text
                                
                                # Clean the delta text
                                delta = clean_generated_text(delta)
                                
                                # Only send valid, non-empty deltas
                                if delta and is_valid_unicode(delta):
                                    data = {
                                        "id": message_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(datetime.now().timestamp()),
                                        "model": request.model,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {"content": delta},
                                                "finish_reason": None
                                            }
                                        ]
                                    }
                                    yield f"data: {json.dumps(data)}\n\n"
                        except Exception as e:
                            # If queue.get times out, just continue
                            if not thread.is_alive():
                                break
                            await asyncio.sleep(0.01)
                finally:
                    # Make sure thread is joined
                    if thread.is_alive():
                        thread.join()
                    
                    # Send completion message
                    done_data = {
                        "id": message_id,
                        "object": "chat.completion.chunk",
                        "created": int(datetime.now().timestamp()),
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    yield f"data: {json.dumps(done_data)}\n\n"
                    yield "data: [DONE]\n\n"
            
            return StreamingResponse(event_generator(), media_type="text/event-stream")

        if not request.stream and request.functions:
            if args.log:
                logger.info(f"Received functions/tool definitions: {json.dumps(request.functions)}")

        generated_ids = model.generate(
            **inputs,
            max_new_tokens=request.max_tokens,
            do_sample=True,
            temperature=request.temperature,
            top_p=request.top_p,
            bad_words_ids=bad_words_ids
        )

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        response = processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )[0]

        # Remove trailing replacement character if present
        response = response.rstrip('�')

        if request.response_format and request.response_format.get("type") == "json_object":
            try:
                if response.startswith('```'):
                    response = '\n'.join(response.split('\n')[1:-1])
                if response.startswith('json'):
                    response = response[4:].lstrip()
                content = json.loads(response)
                response = json.dumps(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Invalid JSON response: {str(e)}")

        response = clean_generated_text(response)

        total_time = time.time() - request_start_time
        logger.info(f"Request completed in {total_time:.2f} seconds")
        if args.log:
            logger.info(f"Response content: {response}")

        return ChatCompletionResponse(
            id=f"chatcmpl-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            object="chat.completion",
            created=int(datetime.now().timestamp()),
            model=request.model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": len(inputs.input_ids[0]),
                "completion_tokens": len(generated_ids_trimmed[0]),
                "total_tokens": len(inputs.input_ids[0]) + len(generated_ids_trimmed[0])
            }
        )
    except Exception as e:
        logger.error(f"Request error: {str(e)}", exc_info=True)
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/models", response_model=ModelList)
async def list_models(_: None = Depends(enforce_api_key)):
    """List available models"""
    return ModelList(
        data=[
            ModelCard(
                id=current_loaded_model,
                created=1709251200,
                owned_by="Qwen",
                permission=[{
                    "id": current_loaded_model,
                    "created": 1709251200,
                    "allow_create_engine": False,
                    "allow_sampling": True,
                    "allow_logprobs": True,
                    "allow_search_indices": False,
                    "allow_view": True,
                    "allow_fine_tuning": False,
                    "organization": "*",
                    "group": None,
                    "is_blocking": False
                }],
                capabilities={
                    "vision": True,
                    "chat": True,
                    "embeddings": False,
                    "text_completion": True
                },
                context_window=131072,
                max_tokens=8192
            )
        ]
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    log_system_info()
    return {
        "status": "healthy",
        "model_loaded": model is not None and processor is not None,
        "device": str(device),
        "cuda_available": torch.cuda.is_available(),
        "model_name": MODEL_NAME,
        "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=args.port)