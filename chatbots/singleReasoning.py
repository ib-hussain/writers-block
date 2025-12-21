from typing import Dict, List, Tuple

# Agents Available: intro, final_cta, FAQs, business_description, short_cta, writing
DEFAULT_AGENT = "writing"

AGENT_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "intro": {
        "phrases": [
            "write an introduction", "write an intro", "opening paragraph",
            "hook and intro", "introduce this", "intro for", "opening statement"
        ],
        "words": [
            "introduction", "intro", "hook", "opening", "overview", "context",
            "background", "set the scene", "kickoff"
        ],
    },
    "FAQs": {
        "phrases": [
            "frequently asked questions", "common questions", "faq section",
            "questions and answers", "q and a", "q&a"
        ],
        "words": [
            "faq", "faqs", "questions", "answers", "q&a", "qna",
            "help centre", "help center", "support questions"
        ],
    },
    "business_description": {
        "phrases": [
            "business description", "company description", "about the business",
            "about us", "who we are", "what we do", "our mission", "our vision",
            "value proposition", "elevator pitch"
        ],
        "words": [
            "business", "company", "brand", "mission", "vision", "services",
            "solutions", "offerings", "value", "positioning", "overview"
        ],
    },
    "short_cta": {
        "phrases": [
            "short cta", "cta line", "call to action", "one line cta",
            "button text", "cta button", "add a cta", "end with cta"
        ],
        "words": [
            "cta", "button", "subscribe", "sign up", "signup", "join",
            "download", "buy", "order", "book", "reserve", "get started",
            "learn more"
        ],
    },
    "final_cta": {
        "phrases": [
            "final cta", "closing cta", "closing statement", "end with a cta",
            "wrap up", "conclusion cta", "closing paragraph"
        ],
        "words": [
            "closing", "conclusion", "wrap-up", "wrap up", "final",
            "summary", "next steps"
        ],
    },
    "writing": {
        "phrases": [
            "write a blog", "write an article", "rewrite this", "refine this",
            "improve this", "edit this", "make it better", "write content",
            "draft copy", "create copy", "write a section"
        ],
        "words": [
            "write", "rewrite", "refine", "edit", "improve", "draft", "copy",
            "content", "paragraph", "section", "blog", "article"
        ],
    },
}
# If there is a tie, this decides which agent wins.
# Put the most "specific" intents earlier.
TIE_BREAK_PRIORITY: List[str] = [
    "FAQs",
    "business_description",
    "intro",
    "final_cta",
    "short_cta",
    "writing",
]
def _score_prompt(prompt_lower: str, phrases: List[str], words: List[str]) -> int:
    """
    Simple scoring:
    - Phrase match: +3 each (more intent-specific)
    - Word match: +1 each
    """
    score = 0
    # Phrase matches
    for p in phrases:
        if p in prompt_lower:
            score += 3
    # Word matches (guard a bit against empty / very short words)
    for w in words:
        if w and w in prompt_lower:
            score += 1
    return score
def SingleClassifier(user_prompt: str) -> str:
    """
    Keyword-based fallback classifier for new agent types:
    intro, final_cta, FAQs, business_description, short_cta, writing (default).
    """
    if not user_prompt or not user_prompt.strip():
        return DEFAULT_AGENT

    prompt_lower = user_prompt.lower()

    # Score each agent
    scores: Dict[str, int] = {}
    for agent, kw in AGENT_KEYWORDS.items():
        scores[agent] = _score_prompt(
            prompt_lower,
            kw.get("phrases", []),
            kw.get("words", []),
        )

    # If all zero, return default
    max_score = max(scores.values()) if scores else 0
    if max_score == 0:
        return DEFAULT_AGENT

    # Collect tied winners
    winners = [a for a, s in scores.items() if s == max_score]

    # Tie-break using priority list
    for agent in TIE_BREAK_PRIORITY:
        if agent in winners:
            return agent

    # Fallback (shouldn't happen)
    return DEFAULT_AGENT
