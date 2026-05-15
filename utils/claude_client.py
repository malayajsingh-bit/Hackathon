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
        content = response.choices[0].message.content
        if content is None:
            raise ValueError(
                f"LLM returned empty response (model={self.model}). "
                "Check your API key, model name, and gateway URL."
            )
        return content

    def _clean_json_text(self, text: str) -> str:
        """Multi-pass cleanup for LLM-generated JSON."""
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
            text = re.sub(r'```\s*$', '', text)
            text = text.strip()
        # Extract JSON block if wrapped in other text
        if not text.startswith(("{", "[")):
            json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
            if json_match:
                text = json_match.group(1)
        # Fix Python/JS literals
        text = re.sub(r'\bTrue\b', 'true', text)
        text = re.sub(r'\bFalse\b', 'false', text)
        text = re.sub(r'\bNone\b', 'null', text)
        # Remove single-line comments not inside strings (// ...)
        text = re.sub(r'(?<!:)//[^\n"]*', '', text)
        # Remove block comments /* ... */
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        # Remove trailing commas before ] or }
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        return text.strip()

    def generate_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> dict:
        full_system = system_prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanation, no code fences. No trailing commas."
        text = self.generate(full_system, user_prompt, max_tokens)
        text = self._clean_json_text(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: json-repair handles most remaining LLM JSON quirks
            try:
                from json_repair import repair_json
                return json.loads(repair_json(text))
            except Exception:
                raise json.JSONDecodeError(
                    f"Could not parse LLM response as JSON after all cleanup attempts.\n"
                    f"First 500 chars: {text[:500]}",
                    text, 0
                )
