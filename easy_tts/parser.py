"""텍스트 파싱 모듈 (정지 지시어 등)"""

import re
from typing import List, Dict


class TextParser:
    """텍스트에서 정지 등 특수 지시어를 파싱"""

    PAUSE_PATTERN = re.compile(
        r'\[(\d+(?:\.\d+)?)\s*(?:초|sec|s)?\s*(?:정지|pause|silence|쉼)?\]',
        re.IGNORECASE
    )

    @classmethod
    def parse(cls, text: str) -> List[Dict]:
        """
        텍스트를 파싱하여 세그먼트 리스트 반환

        Returns:
            [{"type": "text", "content": "..."}, {"type": "pause", "duration": 5.0}, ...]
        """
        segments = []
        last_end = 0

        for match in cls.PAUSE_PATTERN.finditer(text):
            if match.start() > last_end:
                text_before = text[last_end:match.start()].strip()
                if text_before:
                    segments.append({"type": "text", "content": text_before})

            duration = float(match.group(1))
            segments.append({"type": "pause", "duration": duration})
            last_end = match.end()

        if last_end < len(text):
            text_after = text[last_end:].strip()
            if text_after:
                segments.append({"type": "text", "content": text_after})

        if not segments and text.strip():
            segments.append({"type": "text", "content": text.strip()})

        return segments

    @classmethod
    def has_pause(cls, text: str) -> bool:
        """정지 지시어 존재 여부"""
        return bool(cls.PAUSE_PATTERN.search(text))

    @classmethod
    def clean(cls, text: str) -> str:
        """정지 지시어 제거"""
        return cls.PAUSE_PATTERN.sub('', text).strip()
