"""
AI Engine Component - Milestone 3
Multi-provider AI engine: Gemini → HuggingFace Router → Cohere fallback chain.
All providers are initialized; generation falls through on failure.
Features:
  - Exponential backoff: 2s, 4s, 8s for 500 INTERNAL errors
  - HF 503 warm-up: waits 15s for model spin-up (up to 3 attempts)
  - Structured failure object returned when all providers exhausted
"""

import time
import json
import google.generativeai as genai
import cohere
from openai import OpenAI
from src.config import (
    OPENAI_API_KEY, GPT_MODEL, HF_BASE_URL,
    GEMINI_API_KEY, GEMINI_MODEL,
    COHERE_API_KEY
)
from src.utils import setup_logger

logger = setup_logger(__name__)

class AIEngine:
    """Multi-provider AI engine with automatic fallback: Gemini → Cohere → OpenAI."""

    def __init__(self):
        self.gemini_ready = False
        self.cohere_client = None
        self.openai_client = None
        self.provider = "None"
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize ALL available providers (all are tried independently)."""

        # 1. Google Gemini
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.gemini_ready = True
                logger.info(f"[OK] Gemini initialized ({GEMINI_MODEL})")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")

        # 2. OpenAI / HuggingFace
        if OPENAI_API_KEY:
            try:
                base_url = None
                model = GPT_MODEL
                
                # Check for HuggingFace key
                if OPENAI_API_KEY.startswith("hf_"):
                    base_url = HF_BASE_URL
                    logger.info(f"[OK] HuggingFace initialized ({model})")
                else:
                    logger.info(f"[OK] OpenAI initialized ({model})")

                self.openai_client = OpenAI(
                    api_key=OPENAI_API_KEY,
                    base_url=base_url,
                    timeout=60.0  # Increased timeout for HF warm-up
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI/HF: {e}")

        # 3. Cohere
        if COHERE_API_KEY:
            try:
                self.cohere_client = cohere.Client(COHERE_API_KEY)
                logger.info("[OK] Cohere initialized (command-r-08-2024)")
            except Exception as e:
                logger.error(f"Failed to initialize Cohere: {e}")

        # Set primary provider label
        if self.gemini_ready:
            self.provider = "Google Gemini"
        elif self.cohere_client:
            self.provider = "Cohere"
        elif self.openai_client:
            self.provider = "OpenAI/HF"
        else:
            logger.warning("[WARN] No AI providers available. Using template fallback.")

    def is_ready(self) -> bool:
        """Check if any AI provider is available."""
        return self.gemini_ready or self.cohere_client is not None or self.openai_client is not None

    def _exponential_backoff(self, attempt: int, base: float = 2.0):
        """Sleep with exponential backoff: 2s, 4s, 8s for attempts 0, 1, 2."""
        delay = base ** (attempt + 1)  # 2, 4, 8 seconds
        logger.warning(f"Exponential backoff: retrying in {delay:.0f}s (attempt {attempt + 1})...")
        time.sleep(delay)

    def generate(self, prompt: str, system_prompt: str = "", max_tokens: int = 1000) -> dict:
        """
        Attempt generation with fallback chain: Gemini → HuggingFace Router → Cohere.
        Returns detailed object: {"text": str, "status": "success"|"failed", "provider": str, "error": str|None}
        
        Error handling:
          - 500 INTERNAL errors: exponential backoff (2s, 4s, 8s)
          - HF 503 warm-up: waits 15s per attempt (up to 3 attempts)
        """

        # 1. Try Gemini (with exponential backoff for 500 errors)
        if self.gemini_ready:
            for attempt in range(3):
                try:
                    model = genai.GenerativeModel(GEMINI_MODEL)
                    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                    response = model.generate_content(full_prompt)
                    if response.text:
                        self.provider = "Google Gemini"
                        return {"text": response.text, "status": "success", "provider": "Google Gemini", "error": None}
                except Exception as e:
                    err_str = str(e)
                    if "500" in err_str or "INTERNAL" in err_str.upper():
                        logger.warning(f"Gemini 500 INTERNAL error (attempt {attempt+1}/3): {e}")
                        if attempt < 2:
                            self._exponential_backoff(attempt)
                    else:
                        logger.warning(f"Gemini generation failed: {e}")
                        break  # Non-retryable error, move to next provider

        # 2. Try HuggingFace Router (with 503 warm-up + exponential backoff for 500)
        if self.openai_client:
            for attempt in range(3):
                try:
                    resp = self.openai_client.chat.completions.create(
                        model=GPT_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=max_tokens
                    )
                    self.provider = "OpenAI/HF"
                    return {"text": resp.choices[0].message.content, "status": "success", "provider": "OpenAI/HF", "error": None}
                except Exception as e:
                    err_str = str(e)
                    if "503" in err_str:
                        # HF model warming up — wait 15s before retry
                        logger.warning(f"HF 503 Service Unavailable (Attempt {attempt+1}/3). Model warming up, waiting 15s...")
                        time.sleep(15)
                    elif "500" in err_str or "INTERNAL" in err_str.upper():
                        logger.warning(f"HF 500 INTERNAL error (attempt {attempt+1}/3): {e}")
                        if attempt < 2:
                            self._exponential_backoff(attempt)
                    else:
                        logger.warning(f"HF generation failed: {e}")
                        break  # Non-retryable error, move to next provider

        # 3. Try Cohere (with exponential backoff for 500 errors)
        if self.cohere_client:
            for attempt in range(3):
                try:
                    # Combine system prompt with user prompt (Cohere doesn't use preamble param)
                    full_message = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                    response = self.cohere_client.chat(
                        message=full_message,
                        model="command-r-08-2024"
                    )
                    self.provider = "Cohere"
                    return {"text": response.text, "status": "success", "provider": "Cohere", "error": None}
                except Exception as e:
                    err_str = str(e)
                    if "500" in err_str or "INTERNAL" in err_str.upper():
                        logger.warning(f"Cohere 500 INTERNAL error (attempt {attempt+1}/3): {e}")
                        if attempt < 2:
                            self._exponential_backoff(attempt)
                    else:
                        logger.warning(f"Cohere generation failed: {e}")
                        break  # Non-retryable error

        # All providers exhausted
        error_msg = "All providers exhausted (Gemini → HuggingFace → Cohere)"
        logger.error(f"[ERROR] {error_msg}")
        return {"text": "", "status": "failed", "provider": "None", "error": error_msg}

    def safe_generate(self, prompt: str, system_prompt: str = "", max_tokens: int = 1000) -> dict:
        """Safe wrapper that guarantees a return object."""
        try:
            return self.generate(prompt, system_prompt, max_tokens)
        except Exception as e:
            logger.critical(f"Critical Engine Failure: {e}")
            return {"text": "", "status": "failed", "provider": "None", "error": str(e)}
