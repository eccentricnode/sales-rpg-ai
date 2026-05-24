#!/usr/bin/env python3
"""
Test script to validate LLM provider configuration.

Usage:
    python test_providers.py
    python test_providers.py --provider github
    python test_providers.py --provider openrouter
    python test_providers.py --provider azure
"""

import os
import sys
import argparse
from pathlib import Path
from openai import OpenAI

# Load environment variables
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()


def get_provider_config(provider_name):
    """Get configuration for a specific provider."""
    provider = provider_name.lower()

    if provider == "github":
        token = os.getenv("GITHUB_TOKEN", "")
        model = os.getenv("GITHUB_MODEL", "gpt-4o-mini")
        base_url = "https://models.github.ai/inference"
        if not token:
            raise ValueError("GITHUB_TOKEN not set. Get one at: https://github.com/settings/tokens")
        return token, base_url, model

    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        base_url = "https://openrouter.ai/api/v1"
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set. Get one at: https://openrouter.ai/keys")
        return api_key, base_url, model

    elif provider == "azure":
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        if not api_key or not endpoint:
            raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT required")
        base_url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        return api_key, base_url, deployment

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        base_url = "https://api.openai.com/v1"
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return api_key, base_url, model

    elif provider == "local":
        api_key = "local"
        base_url = os.getenv("LOCAL_AI_BASE_URL", "http://localhost:8080/v1")
        model = os.getenv("LOCAL_AI_MODEL", "phi-3.5-mini")
        return api_key, base_url, model

    else:
        raise ValueError(f"Unknown provider: {provider}. Options: github, openrouter, azure, openai, local")


def test_provider(provider_name):
    """Test a specific LLM provider."""
    print(f"\n{'='*60}")
    print(f"Testing {provider_name.upper()} Provider")
    print(f"{'='*60}\n")

    try:
        # Get configuration
        api_key, base_url, model = get_provider_config(provider_name)

        print(f"📝 Configuration:")
        print(f"   Provider: {provider_name}")
        print(f"   Base URL: {base_url}")
        print(f"   Model: {model}")
        print(f"   API Key: {api_key[:20]}..." if len(api_key) > 20 else f"   API Key: {api_key}")
        print()

        # Initialize client
        print("🔌 Connecting to provider...")
        client = OpenAI(base_url=base_url, api_key=api_key)

        # Test prompt
        test_prompt = """Analyze this sales objection:

"That sounds expensive for what you're offering."

Is this a PRICE objection? (Yes/No)
Provide one brief response suggestion."""

        print("📤 Sending test request...")
        print(f"   Prompt: {test_prompt[:50]}...")
        print()

        # Make API call
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": test_prompt}
            ],
            max_tokens=200,
            temperature=0.7,
        )

        # Display result
        answer = response.choices[0].message.content
        print("✅ SUCCESS! Provider is working correctly.")
        print()
        print(f"📥 Response:")
        print("-" * 60)
        print(answer)
        print("-" * 60)
        print()
        print(f"⚡ Metadata:")
        print(f"   Model: {response.model}")
        print(f"   Usage: {response.usage.total_tokens} tokens")
        print()

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print()
        print("📋 Troubleshooting:")

        if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
            print("   • Check your API key/token is correct")
            print("   • Verify the token hasn't expired")
            if provider_name == "github":
                print("   • Ensure 'models:read' scope is enabled")
                print("   • Create new token at: https://github.com/settings/tokens")

        elif "not found" in str(e).lower() or "does not exist" in str(e).lower():
            print("   • Check the model name is correct")
            print(f"   • Current model: {model}")

        elif "rate limit" in str(e).lower():
            print("   • You've hit the rate limit")
            print("   • Wait a few minutes and try again")
            print("   • Consider upgrading to a paid tier")

        elif "connection" in str(e).lower():
            print("   • Check your internet connection")
            if provider_name == "local":
                print("   • Ensure LocalAI is running: docker ps")

        else:
            print("   • Check the full error message above")
            print(f"   • Verify .env configuration for {provider_name.upper()}")

        print()
        return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Test LLM provider configuration")
    parser.add_argument("--provider", help="Provider to test (github, openrouter, azure, openai, local)")
    args = parser.parse_args()

    print(f"\n{'#'*60}")
    print("LLM PROVIDER TEST SUITE")
    print(f"{'#'*60}")

    if args.provider:
        # Test specific provider
        success = test_provider(args.provider)
        sys.exit(0 if success else 1)

    else:
        # Test configured provider from .env
        provider = os.getenv("LLM_PROVIDER", "local").lower()
        print(f"\nTesting configured provider: {provider.upper()}")
        print("(Set LLM_PROVIDER in .env to change, or use --provider flag)")

        success = test_provider(provider)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
