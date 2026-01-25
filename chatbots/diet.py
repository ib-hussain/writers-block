from typing import Dict, Tuple
    # ---------- Agent calls (PURE, NO DB) ----------

def Intro_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
        return prompt, llm.generate(prompt, temperature)
def Final_CTA_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
        return prompt, llm.generate(prompt, temperature)
def FAQs_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
        return prompt, llm.generate(prompt, temperature)
def Business_Description_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
        return prompt, llm.generate(prompt, temperature)
def References_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
        return prompt, llm.generate(prompt, temperature)
def Short_CTA_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
        return prompt, llm.generate(prompt, temperature)
def Full_Blog_Writer(prompt: str, temperature: float) -> Tuple[str, str]:
        return prompt, llm.generate(prompt, temperature)