# app/managers/api_manager.py
"""
API Manager for the Autonomous Income Generator.

This module handles interactions with various LLM APIs (Claude, DeepSeek, Gemma).
"""
import logging
import time
import json
import random
import requests
from typing import Dict, Any, Optional, List, Union
import os
import asyncio
import httpx


class APIManager:
    """
    Manages interactions with various LLM APIs.
    """

    def __init__(self, config):
        """
        Initialize the API manager.

        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Load API keys
        self.claude_api_key = config.get("LLM_API", "CLAUDE_API_KEY", "")
        self.deepseek_api_key = config.get("LLM_API", "DEEPSEEK_API_KEY", "")
        self.gemma_api_key = config.get("LLM_API", "GEMMA_API_KEY", "")

        # API specific settings
        self.use_local_gemma = config.get("LLM_API", "USE_LOCAL_GEMMA", "true").lower() == "true"

        # Default model settings
        self.default_model = config.get("LLM_API", "DEFAULT_MODEL", "claude")
        self.temperature = float(config.get("LLM_API", "TEMPERATURE", "0.7"))

        # API endpoints
        self.claude_endpoint = "https://api.anthropic.com/v1/messages"
        self.deepseek_endpoint = "https://api.deepseek.com/v1/chat/completions"

        # Local Gemma endpoint if using local inference
        self.local_gemma_endpoint = config.get("LLM_API", "LOCAL_GEMMA_ENDPOINT", "http://127.0.0.1:8000/generate")

        # Rate limiting settings
        self.rate_limit_delay = float(config.get("LLM_API", "RATE_LIMIT_DELAY", "1.0"))
        self.last_request_time = 0

        # Initialize API availability based on keys
        self.apis_available = {
            "claude": bool(self.claude_api_key),
            "deepseek": bool(self.deepseek_api_key),
            "gemma": bool(self.gemma_api_key) or self.use_local_gemma
        }

        # Log available APIs
        available_apis = [api for api, available in self.apis_available.items() if available]
        self.logger.info(f"Initialized API manager with available APIs: {', '.join(available_apis)}")

        if not available_apis:
            self.logger.warning("No API keys provided, LLM functionality will not work")

    def _respect_rate_limit(self) -> None:
        """
        Respect rate limits by adding delay between API calls.
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.rate_limit_delay:
            delay = self.rate_limit_delay - elapsed
            time.sleep(delay)

        self.last_request_time = time.time()

    def generate_text(self, prompt: str, model: Optional[str] = None,
                      max_tokens: int = 1000, temperature: Optional[float] = None,
                      system_prompt: Optional[str] = None) -> str:
        """
        Generate text using an LLM API.

        Args:
            prompt: User prompt or input text
            model: Model to use (claude, deepseek, gemma, or None for default)
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation (0.0 to 1.0)
            system_prompt: Optional system prompt for models that support it

        Returns:
            Generated text response
        """
        # Use default model if none specified
        model = model or self.default_model

        # Use default temperature if none specified
        temperature = temperature if temperature is not None else self.temperature

        # Check if the requested API is available
        if model not in self.apis_available or not self.apis_available[model]:
            # Fall back to the first available API
            available_apis = [api for api, available in self.apis_available.items() if available]

            if not available_apis:
                self.logger.error("No LLM APIs available")
                return "I apologize, but I'm unable to generate content at the moment due to API unavailability."

            model = available_apis[0]
            self.logger.info(f"Falling back to {model} API")

        # Respect rate limits
        self._respect_rate_limit()

        # Generate text with the appropriate API
        try:
            if model == "claude":
                return self._generate_with_claude(prompt, max_tokens, temperature, system_prompt)
            elif model == "deepseek":
                return self._generate_with_deepseek(prompt, max_tokens, temperature, system_prompt)
            elif model == "gemma":
                if self.use_local_gemma:
                    return self._generate_with_local_gemma(prompt, max_tokens, temperature, system_prompt)
                else:
                    return self._generate_with_gemma_api(prompt, max_tokens, temperature, system_prompt)
            else:
                self.logger.error(f"Unknown model: {model}")
                return "I apologize, but I'm unable to generate content due to an unknown model configuration."

        except Exception as e:
            self.logger.error(f"Error generating text with {model}: {str(e)}")
            return f"I apologize, but I encountered an error while generating content: {str(e)}"

    def _generate_with_claude(self, prompt: str, max_tokens: int, temperature: float,
                              system_prompt: Optional[str] = None) -> str:
        """
        Generate text using the Claude API.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            system_prompt: System prompt for Claude

        Returns:
            Generated text
        """
        # Use a default system prompt if none provided
        if not system_prompt:
            system_prompt = "You are a helpful, harmless, and honest AI assistant."

        headers = {
            "x-api-key": self.claude_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        data = {
            "model": "claude-3-opus-20240229",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            response = requests.post(
                self.claude_endpoint,
                headers=headers,
                json=data,
                timeout=60
            )

            if response.status_code != 200:
                self.logger.error(f"Claude API error: {response.status_code} - {response.text}")
                return f"Error: Claude API returned status code {response.status_code}"

            response_data = response.json()
            return response_data["content"][0]["text"]

        except Exception as e:
            self.logger.error(f"Error calling Claude API: {str(e)}")
            raise

    def _generate_with_deepseek(self, prompt: str, max_tokens: int, temperature: float,
                                system_prompt: Optional[str] = None) -> str:
        """
        Generate text using the DeepSeek API.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            system_prompt: System prompt for DeepSeek

        Returns:
            Generated text
        """
        # Use a default system prompt if none provided
        if not system_prompt:
            system_prompt = "You are a helpful, harmless, and honest AI assistant."

        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }

        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        try:
            response = requests.post(
                self.deepseek_endpoint,
                headers=headers,
                json=data,
                timeout=60
            )

            if response.status_code != 200:
                self.logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                return f"Error: DeepSeek API returned status code {response.status_code}"

            response_data = response.json()
            return response_data["choices"][0]["message"]["content"]

        except Exception as e:
            self.logger.error(f"Error calling DeepSeek API: {str(e)}")
            raise

    def _generate_with_gemma_api(self, prompt: str, max_tokens: int, temperature: float,
                                 system_prompt: Optional[str] = None) -> str:
        """
        Generate text using the Gemma 3 API.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            system_prompt: System prompt for Gemma

        Returns:
            Generated text
        """
        # Note: This is a placeholder implementation as the Gemma 3 API details might differ
        # The actual implementation would need to be adjusted based on the final API specs

        # Use a default system prompt if none provided
        if not system_prompt:
            system_prompt = "You are a helpful, harmless, and honest AI assistant."

        headers = {
            "Authorization": f"Bearer {self.gemma_api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": "gemma-3",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        try:
            # This endpoint is a placeholder and would need to be updated
            response = requests.post(
                "https://api.gemma.example.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )

            if response.status_code != 200:
                self.logger.error(f"Gemma API error: {response.status_code} - {response.text}")
                return f"Error: Gemma API returned status code {response.status_code}"

            response_data = response.json()
            return response_data["choices"][0]["message"]["content"]

        except Exception as e:
            self.logger.error(f"Error calling Gemma API: {str(e)}")
            raise

    def _generate_with_local_gemma(self, prompt: str, max_tokens: int, temperature: float,
                                   system_prompt: Optional[str] = None) -> str:
        """
        Generate text using a locally running Gemma model.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            system_prompt: System prompt for Gemma

        Returns:
            Generated text
        """
        # Format the prompt with system prompt if provided
        if system_prompt:
            full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        else:
            full_prompt = f"User: {prompt}\n\nAssistant:"

        data = {
            "prompt": full_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        try:
            response = requests.post(
                self.local_gemma_endpoint,
                json=data,
                timeout=120  # Longer timeout for local inference
            )

            if response.status_code != 200:
                self.logger.error(f"Local Gemma error: {response.status_code} - {response.text}")
                return f"Error: Local Gemma returned status code {response.status_code}"

            response_data = response.json()
            return response_data.get("response", "")

        except Exception as e:
            self.logger.error(f"Error calling local Gemma: {str(e)}")
            raise

    async def generate_text_async(self, prompt: str, model: Optional[str] = None,
                                  max_tokens: int = 1000, temperature: Optional[float] = None,
                                  system_prompt: Optional[str] = None) -> str:
        """
        Generate text asynchronously using an LLM API.

        Args:
            prompt: User prompt or input text
            model: Model to use (claude, deepseek, gemma, or None for default)
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation (0.0 to 1.0)
            system_prompt: Optional system prompt for models that support it

        Returns:
            Generated text response
        """
        # Use default model if none specified
        model = model or self.default_model

        # Use default temperature if none specified
        temperature = temperature if temperature is not None else self.temperature

        # Check if the requested API is available
        if model not in self.apis_available or not self.apis_available[model]:
            # Fall back to the first available API
            available_apis = [api for api, available in self.apis_available.items() if available]

            if not available_apis:
                self.logger.error("No LLM APIs available")
                return "I apologize, but I'm unable to generate content at the moment due to API unavailability."

            model = available_apis[0]
            self.logger.info(f"Falling back to {model} API")

        # Generate text with the appropriate API
        try:
            if model == "claude":
                return await self._generate_with_claude_async(prompt, max_tokens, temperature, system_prompt)
            elif model == "deepseek":
                return await self._generate_with_deepseek_async(prompt, max_tokens, temperature, system_prompt)
            elif model == "gemma":
                if self.use_local_gemma:
                    return await self._generate_with_local_gemma_async(prompt, max_tokens, temperature, system_prompt)
                else:
                    return await self._generate_with_gemma_api_async(prompt, max_tokens, temperature, system_prompt)
            else:
                self.logger.error(f"Unknown model: {model}")
                return "I apologize, but I'm unable to generate content due to an unknown model configuration."

        except Exception as e:
            self.logger.error(f"Error generating text with {model}: {str(e)}")
            return f"I apologize, but I encountered an error while generating content: {str(e)}"

    async def _generate_with_claude_async(self, prompt: str, max_tokens: int, temperature: float,
                                          system_prompt: Optional[str] = None) -> str:
        """
        Generate text asynchronously using the Claude API.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            system_prompt: System prompt for Claude

        Returns:
            Generated text
        """
        # Use a default system prompt if none provided
        if not system_prompt:
            system_prompt = "You are a helpful, harmless, and honest AI assistant."

        headers = {
            "x-api-key": self.claude_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        data = {
            "model": "claude-3-opus-20240229",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.claude_endpoint,
                    headers=headers,
                    json=data,
                    timeout=60
                )

            if response.status_code != 200:
                self.logger.error(f"Claude API error: {response.status_code} - {response.text}")
                return f"Error: Claude API returned status code {response.status_code}"

            response_data = response.json()
            return response_data["content"][0]["text"]

        except Exception as e:
            self.logger.error(f"Error calling Claude API: {str(e)}")
            raise
