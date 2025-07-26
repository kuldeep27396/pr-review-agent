#!/usr/bin/env python3



import os
import sys
from openai import OpenAI

def test_openrouter():
    try:
        print("🔗 Connecting to OpenRouter API...")
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv('OPENROUTER_API_KEY', 'your-api-key-here'),
        )

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/kuldeep27396/pr-review-agent",
                "X-Title": "PR Review Agent Test",
            },
            model="qwen/qwen3-coder:free",
            messages=[
                {
                    "role": "user",
                    "content": "Write a simple 'Hello World' program in Python"
                }
            ]
        )
        
        print("✅ OpenRouter API test successful!")
        print("\n📝 Response:")
        print("-" * 50)
        print(completion.choices[0].message.content)
        print("-" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing OpenRouter API: {e}")
        return False

if __name__ == "__main__":
    success = test_openrouter()
    sys.exit(0 if success else 1)
