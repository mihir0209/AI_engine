"""
Advanced AI features module
Vision models, tool/function calling, and embeddings support
"""
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
import json
import base64
import os


@dataclass
class ToolDefinition:
    """Definition of a tool/function for AI calling"""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format
    
    def to_dict(self) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


@dataclass
class ToolCall:
    """Result of a tool call from AI"""
    id: str
    name: str
    arguments: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments)
            }
        }


@dataclass
class ImageContent:
    """Image content for vision models"""
    url: Optional[str] = None
    base64_data: Optional[str] = None
    media_type: str = "image/jpeg"
    
    def to_dict(self) -> Dict:
        if self.url:
            return {"type": "image_url", "image_url": {"url": self.url}}
        elif self.base64_data:
            return {"type": "image_url", "image_url": {"url": f"data:{self.media_type};base64,{self.base64_data}"}}
        return {}


class VisionSupport:
    """Vision model support"""
    
    @staticmethod
    def create_image_message(
        prompt: str,
        images: List[Union[str, ImageContent]],
        role: str = "user"
    ) -> Dict:
        """Create a message with images for vision models"""
        content = [{"type": "text", "text": prompt}]
        
        for image in images:
            if isinstance(image, str):
                # Assume it's a URL or file path
                if image.startswith("http"):
                    img = ImageContent(url=image)
                else:
                    # Read file and convert to base64
                    with open(image, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode()
                    ext = os.path.splitext(image)[1].lower()
                    media_type = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".gif": "image/gif",
                        ".webp": "image/webp"
                    }.get(ext, "image/jpeg")
                    img = ImageContent(base64_data=img_data, media_type=media_type)
            else:
                img = image
            
            content.append(img.to_dict())
        
        return {"role": role, "content": content}
    
    @staticmethod
    def is_vision_message(message: Dict) -> bool:
        """Check if message contains vision content"""
        content = message.get("content", [])
        if isinstance(content, list):
            return any(item.get("type") == "image_url" for item in content)
        return False


class ToolCallingSupport:
    """Function/tool calling support"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.tool_handlers: Dict[str, callable] = {}
    
    def register_tool(self, tool: ToolDefinition, handler: callable = None):
        """Register a tool with optional handler"""
        self.tools[tool.name] = tool
        if handler:
            self.tool_handlers[tool.name] = handler
    
    def get_tools_for_request(self) -> List[Dict]:
        """Get all tools in API format"""
        return [tool.to_dict() for tool in self.tools.values()]
    
    def has_tool(self, name: str) -> bool:
        """Check if tool is registered"""
        return name in self.tools
    
    def execute_tool(self, tool_call: ToolCall) -> Any:
        """Execute a tool call"""
        if tool_call.name not in self.tool_handlers:
            raise ValueError(f"No handler registered for tool: {tool_call.name}")
        
        handler = self.tool_handlers[tool_call.name]
        return handler(**tool_call.arguments)
    
    @staticmethod
    def parse_tool_calls(response: Dict) -> List[ToolCall]:
        """Parse tool calls from AI response"""
        tool_calls = []
        
        # OpenAI format
        choices = response.get("choices", [])
        for choice in choices:
            message = choice.get("message", {})
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    func = tc.get("function", {})
                    args = func.get("arguments", "{}")
                    if isinstance(args, str):
                        args = json.loads(args)
                    tool_calls.append(ToolCall(
                        id=tc.get("id", ""),
                        name=func.get("name", ""),
                        arguments=args
                    ))
        
        return tool_calls
    
    @staticmethod
    def create_tool_response(tool_call_id: str, content: Any) -> Dict:
        """Create a tool response message"""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(content) if not isinstance(content, str) else content
        }


class EmbeddingSupport:
    """Embedding model support"""
    
    @staticmethod
    def prepare_embedding_request(
        texts: List[str],
        model: str = "text-embedding-ada-002"
    ) -> Dict:
        """Prepare embedding request"""
        return {
            "model": model,
            "input": texts
        }
    
    @staticmethod
    def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a ** 2 for a in vec1) ** 0.5
        norm2 = sum(b ** 2 for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    @staticmethod
    def find_most_similar(
        query_embedding: List[float],
        embeddings: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict]:
        """Find most similar embeddings"""
        scored = []
        for item in embeddings:
            embedding = item.get("embedding", [])
            similarity = EmbeddingSupport.calculate_similarity(query_embedding, embedding)
            scored.append({**item, "similarity": similarity})
        
        return sorted(scored, key=lambda x: x["similarity"], reverse=True)[:top_k]


# Global tool calling instance
tool_calling = ToolCallingSupport()
