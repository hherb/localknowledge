#!/usr/bin/env python3
"""
Ollama Model Capabilities Detection
Programmatically determine model capabilities using the Ollama Python library
"""

import ollama
from typing import Dict, List, Optional, Union
import json

class OllamaModelCapabilities:
    """
    A class to detect and analyze Ollama model capabilities including:
    - Vision/multimodal support
    - Tool/function calling
    - Reasoning/thinking capabilities
    """
    
    def __init__(self, host: str = 'http://localhost:11434'):
        """Initialize with Ollama client"""
        self.client = ollama.Client(host=host)
    
    def get_model_info(self, model_name: str) -> Dict:
        """
        Get detailed model information using the show API
        
        Returns:
            Dict containing model details, capabilities, families, etc.
        """
        try:
            response = self.client.show(model_name)
            return response
        except Exception as e:
            print(f"Error getting model info for {model_name}: {e}")
            return {}
    
    def has_vision_capability(self, model_name: str) -> bool:
        """
        Check if model supports vision/multimodal input
        
        Recent Ollama versions include a 'capabilities' field that explicitly lists 'vision'
        Also checks model families and names for vision models
        """
        model_info = self.get_model_info(model_name)
        
        # Check the new capabilities field (added in recent Ollama versions)
        capabilities = model_info.get('capabilities', [])
        if 'vision' in capabilities:
            return True
        
        # Fallback: Check model families and names for known vision models
        details = model_info.get('details', {})
        families = details.get('families', [])
        
        # Known vision model families and patterns
        vision_families = ['llava', 'qwen2-vl', 'pixtral', 'phi3-vision']
        vision_patterns = ['vision', 'llava', 'qwen2-vl', 'pixtral', 'phi3-vision']
        
        # Check families
        for family in families:
            if family.lower() in vision_families:
                return True
        
        # Check model name patterns
        model_lower = model_name.lower()
        for pattern in vision_patterns:
            if pattern in model_lower:
                return True
        
        return False
    
    def has_tool_calling_capability(self, model_name: str) -> bool:
        """
        Check if model supports tool/function calling
        
        Tests actual capability by attempting a simple tool call
        """
        # Test with a simple function to see if model supports tools
        test_tools = [{
            'type': 'function',
            'function': {
                'name': 'test_function',
                'description': 'A test function to check tool calling support',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'message': {
                            'type': 'string',
                            'description': 'A test message',
                        },
                    },
                    'required': ['message'],
                },
            },
        }]
        
        try:
            response = self.client.chat(
                model=model_name,
                messages=[{
                    'role': 'user', 
                    'content': 'Please call the test_function with message "hello"'
                }],
                tools=test_tools
            )
            
            # Check if response contains tool_calls
            tool_calls = response.get('message', {}).get('tool_calls')
            return tool_calls is not None and len(tool_calls) > 0
            
        except Exception as e:
            # If tools parameter is not supported, the model doesn't support tool calling
            if "tools" in str(e).lower() or "function" in str(e).lower():
                return False
            return False
    
    def has_reasoning_capability(self, model_name: str) -> bool:
        """
        Check if model supports reasoning/thinking (like DeepSeek-R1, QwQ, etc.)
        
        Reasoning models often have specific patterns in their names and can generate
        explicit thinking processes
        """
        model_info = self.get_model_info(model_name)
        
        # Check for reasoning model patterns in name
        reasoning_patterns = [
            'deepseek-r1', 'qwq', 'r1', 'reasoning', 'think', 'cot', 'chain-of-thought'
        ]
        
        model_lower = model_name.lower()
        for pattern in reasoning_patterns:
            if pattern in model_lower:
                return True
        
        # Check model families for reasoning models
        details = model_info.get('details', {})
        families = details.get('families', [])
        reasoning_families = ['qwen2', 'deepseek']  # Families that often include reasoning models
        
        # Test if model can produce thinking output
        try:
            response = self.client.chat(
                model=model_name,
                messages=[{
                    'role': 'user',
                    'content': 'Think step by step about how many Rs are in "strawberry". Show your thinking process.'
                }]
            )
            
            # Check if response has thinking field (new in Ollama for reasoning models)
            if 'thinking' in response:
                return True
                
            # Check response content for thinking patterns
            content = response.get('message', {}).get('content', '').lower()
            thinking_indicators = ['step 1', 'first', 'let me think', 'thinking', 'reasoning']
            
            return any(indicator in content for indicator in thinking_indicators)
            
        except Exception:
            return False
    
    def get_all_capabilities(self, model_name: str) -> Dict[str, Union[bool, Dict]]:
        """
        Get comprehensive capability analysis for a model
        """
        model_info = self.get_model_info(model_name)
        
        capabilities = {
            'model_name': model_name,
            'vision': self.has_vision_capability(model_name),
            'tool_calling': self.has_tool_calling_capability(model_name),
            'reasoning': self.has_reasoning_capability(model_name),
            'model_details': {
                'family': model_info.get('details', {}).get('family'),
                'families': model_info.get('details', {}).get('families', []),
                'parameter_size': model_info.get('details', {}).get('parameter_size'),
                'quantization_level': model_info.get('details', {}).get('quantization_level'),
                'format': model_info.get('details', {}).get('format'),
            },
            'explicit_capabilities': model_info.get('capabilities', []),
        }
        
        return capabilities
    
    def list_all_models_with_capabilities(self) -> List[Dict]:
        """
        List all available models and their capabilities
        """
        try:
            models_response = self.client.list()
            models = models_response.get('models', [])
            
            results = []
            for model in models:
                model_name = model.get('name', '')
                if model_name:
                    capabilities = self.get_all_capabilities(model_name)
                    results.append(capabilities)
            
            return results
            
        except Exception as e:
            print(f"Error listing models: {e}")
            return []

# Example usage and testing
def main():
    """
    Example usage of the OllamaModelCapabilities class
    """
    detector = OllamaModelCapabilities()
    
    # Test specific models
    test_models = [
        'qwen3:14b',  # Should have vision
        'llama3.3:latest ',         # Should have tool calling
        'deepseek-r1:14b-qwen-distill-q8_0',      # Should have reasoning
        'gemma3:12b',          
    ]
    
    print("=== Model Capability Analysis ===\n")
    
    for model in test_models:
        print(f"Analyzing {model}...")
        try:
            capabilities = detector.get_all_capabilities(model)
            
            print(f"  Vision: {capabilities['vision']}")
            print(f"  Tool Calling: {capabilities['tool_calling']}")
            print(f"  Reasoning: {capabilities['reasoning']}")
            print(f"  Family: {capabilities['model_details']['family']}")
            print(f"  Explicit Capabilities: {capabilities['explicit_capabilities']}")
            print()
            
        except Exception as e:
            print(f"  Error analyzing {model}: {e}\n")
    
    # List all available models and their capabilities
    print("=== All Available Models ===\n")
    all_models = detector.list_all_models_with_capabilities()
    
    for model_info in all_models:
        name = model_info['model_name']
        vision = "✓" if model_info['vision'] else "✗"
        tools = "✓" if model_info['tool_calling'] else "✗"
        reasoning = "✓" if model_info['reasoning'] else "✗"
        
        print(f"{name:25} | Vision: {vision} | Tools: {tools} | Reasoning: {reasoning}")

if __name__ == "__main__":
    main()
