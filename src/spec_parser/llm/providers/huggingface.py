"""
HuggingFace local model provider for LLM extraction.

Direct inference without server - loads models from HuggingFace Hub or local cache.
Ideal for systems where Ollama cannot be installed.

Supported Models:
- Qwen/Qwen2.5-Coder-7B-Instruct
- Qwen/Qwen2.5-Coder-3B-Instruct
- Qwen/Qwen2.5-Coder-1.5B-Instruct
- microsoft/Phi-3.5-mini-instruct
- Any HuggingFace chat model with AutoModelForCausalLM

Environment Variables:
- HF_HOME: Cache directory for downloaded models (default: ~/.cache/huggingface)
- HF_TOKEN: HuggingFace access token (optional, for gated models)
"""

from pathlib import Path
from typing import Optional

from loguru import logger

from spec_parser.llm.providers import BaseLLMProvider


class HuggingFaceProvider(BaseLLMProvider):
    """
    HuggingFace local model provider.
    
    Loads models directly using transformers library - no server needed.
    Models are downloaded once and cached for reuse.
    
    Example:
        >>> provider = HuggingFaceProvider(
        ...     model="Qwen/Qwen2.5-Coder-7B-Instruct",
        ...     device="auto"
        ... )
        >>> response = provider.generate(
        ...     prompt="Extract message types from POCT1-A spec",
        ...     temperature=0.0
        ... )
    """
    
    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
        device: str = "auto",
        load_in_8bit: bool = False,
        load_in_4bit: bool = False,
        max_memory: Optional[dict] = None,
        **kwargs
    ):
        """
        Initialize HuggingFace provider.
        
        Args:
            model: HuggingFace model ID (e.g., "Qwen/Qwen2.5-Coder-7B-Instruct")
            device: Device placement ("auto", "cuda", "cpu", "mps")
            load_in_8bit: Enable 8-bit quantization (requires bitsandbytes)
            load_in_4bit: Enable 4-bit quantization (requires bitsandbytes)
            max_memory: Max memory per device (e.g., {0: "10GB", "cpu": "30GB"})
            **kwargs: Additional arguments passed to model.generate()
        """
        super().__init__(**kwargs)
        self.model_id = model
        self.device = device
        self.load_in_8bit = load_in_8bit
        self.load_in_4bit = load_in_4bit
        self.max_memory = max_memory
        self.generation_kwargs = kwargs
        
        # Lazy initialization - load on first use
        self._model = None
        self._tokenizer = None
    
    def _ensure_dependencies(self):
        """Check transformers and torch are installed."""
        try:
            import torch
            import transformers
        except ImportError as e:
            raise ImportError(
                "HuggingFace provider requires 'transformers' and 'torch'. "
                "Install with: pip install transformers torch"
            ) from e
        
        # Check for quantization dependencies
        if self.load_in_8bit or self.load_in_4bit:
            try:
                import bitsandbytes
            except ImportError:
                logger.warning(
                    "Quantization requested but 'bitsandbytes' not installed. "
                    "Install with: pip install bitsandbytes"
                )
                self.load_in_8bit = False
                self.load_in_4bit = False
    
    def _load_model(self):
        """Load model and tokenizer from HuggingFace."""
        if self._model is not None:
            return  # Already loaded
        
        self._ensure_dependencies()
        
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        logger.info(f"Loading HuggingFace model: {self.model_id}")
        logger.info(f"Device: {self.device}, 8-bit: {self.load_in_8bit}, 4-bit: {self.load_in_4bit}")
        
        # Load tokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            trust_remote_code=True
        )
        
        # Prepare model loading kwargs
        model_kwargs = {
            "trust_remote_code": True,
            "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
        }
        
        # Device placement
        if self.device != "auto":
            model_kwargs["device_map"] = self.device
        else:
            model_kwargs["device_map"] = "auto"
        
        # Quantization
        if self.load_in_8bit:
            model_kwargs["load_in_8bit"] = True
        elif self.load_in_4bit:
            model_kwargs["load_in_4bit"] = True
        
        # Memory constraints
        if self.max_memory:
            model_kwargs["max_memory"] = self.max_memory
        
        # Load model
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            **model_kwargs
        )
        
        logger.info(f"Model loaded successfully: {self.model_id}")
    
    def is_available(self) -> bool:
        """
        Check if HuggingFace provider is available.
        
        Returns:
            True if transformers and torch are installed, False otherwise.
        """
        try:
            import torch
            import transformers
            return True
        except ImportError:
            return False
    
    def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """
        Generate text using HuggingFace model.
        
        Args:
            prompt: Input prompt text
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters
        
        Returns:
            Generated text response
        
        Raises:
            ImportError: If transformers/torch not installed
            RuntimeError: If model loading fails
        """
        # Load model on first use
        self._load_model()
        
        import torch
        
        # Format prompt for chat models
        messages = [{"role": "user", "content": prompt}]
        
        # Apply chat template if available
        if hasattr(self._tokenizer, "apply_chat_template"):
            formatted_prompt = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            formatted_prompt = prompt
        
        # Tokenize
        inputs = self._tokenizer(
            formatted_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=4096
        )
        
        # Move to model device
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
        
        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "temperature": temperature if temperature > 0 else 1e-7,  # Avoid zero
            "do_sample": temperature > 0,
            "top_p": 0.95,
            "repetition_penalty": 1.1,
            "pad_token_id": self._tokenizer.eos_token_id,
            **self.generation_kwargs,
            **kwargs
        }
        
        logger.debug(f"Generating with: {gen_kwargs}")
        
        # Generate
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                **gen_kwargs
            )
        
        # Decode response (skip input tokens)
        response = self._tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )
        
        return response.strip()
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"HuggingFaceProvider(model={self.model_id}, "
            f"device={self.device}, "
            f"8bit={self.load_in_8bit}, "
            f"4bit={self.load_in_4bit})"
        )
