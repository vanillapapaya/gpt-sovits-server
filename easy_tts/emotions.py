"""감정 분석 모듈"""

from typing import Dict


class EmotionAnalyzer:
    """텍스트에서 감정을 추론"""

    PATTERNS = {
        "happy": {
            "keywords": ["안녕", "좋아", "기뻐", "행복", "신나", "웃", "ㅋㅋ", "ㅎㅎ", "와!", "대박", "최고", "사랑", "고마워"],
            "punctuation": ["!", "~"],
            "weight": 1.0
        },
        "sad": {
            "keywords": ["슬퍼", "우울", "힘들", "아프", "눈물", "그립", "외로", "미안", "죄송", "ㅠㅠ", "ㅜㅜ"],
            "punctuation": ["...", "ㅠ"],
            "weight": 1.0
        },
        "angry": {
            "keywords": ["화나", "짜증", "싫어", "미워", "열받", "빡", "뭐야", "어이없", "답답"],
            "punctuation": ["!", "?!"],
            "weight": 1.0
        },
        "calm": {
            "keywords": ["평화", "편안", "차분", "조용", "잘자", "굿나잇", "괜찮", "천천히"],
            "punctuation": ["."],
            "weight": 0.8
        },
        "playful": {
            "keywords": ["헤헤", "히히", "장난", "농담", "재미", "ㅋㅋㅋ", "뿅", "짜잔"],
            "punctuation": ["~", "ㅋ"],
            "weight": 1.0
        }
    }

    def analyze(self, text: str) -> Dict[str, float]:
        """텍스트의 감정 점수를 분석"""
        scores = {emotion: 0.0 for emotion in self.PATTERNS}
        text_lower = text.lower()

        for emotion, patterns in self.PATTERNS.items():
            for keyword in patterns["keywords"]:
                if keyword in text_lower:
                    scores[emotion] += patterns["weight"]
            for punct in patterns["punctuation"]:
                scores[emotion] += text.count(punct) * 0.3 * patterns["weight"]

        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}
        else:
            scores["calm"] = 1.0

        return scores

    def get_primary(self, text: str) -> str:
        """가장 강한 감정 반환"""
        scores = self.analyze(text)
        return max(scores, key=scores.get)

    def get_summary(self, text: str) -> str:
        """감정 분석 요약"""
        scores = self.analyze(text)
        sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = [f"{e}: {s:.0%}" for e, s in sorted_emotions[:3] if s > 0]
        return " / ".join(result) if result else "neutral"
