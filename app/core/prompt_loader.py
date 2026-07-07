from __future__ import annotations

from pathlib import Path


class PromptLoader:

    def __init__(self, prompt_root: str | Path | None = None):

        self.prompt_root = Path(prompt_root) if prompt_root else Path(__file__).resolve().parents[2] / "prompts"

    def load(self, filename: str) -> str:

        prompt_path = self.prompt_root / filename

        if not prompt_path.exists():

            raise FileNotFoundError(f"Prompt 파일을 찾을 수 없습니다: {prompt_path}")

        return prompt_path.read_text(encoding="utf-8")