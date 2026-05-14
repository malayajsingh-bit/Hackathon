import json
import re
from openai import OpenAI


class ClaudeClient:
    def __init__(self, api_key: str, base_url: str, model: str = "claude-opus-4-6"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    def generate_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> dict:
        full_system = system_prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanation, no code fences."
        text = self.generate(full_system, user_prompt, max_tokens)
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        # Try to extract JSON if wrapped in other text
        if not text.startswith(("{", "[")):
            json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
            if json_match:
                text = json_match.group(1)
        return json.loads(text)
