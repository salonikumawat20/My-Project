"""
watsonx_agent.py — IBM Watsonx.ai + IBM Granite Integration
Course Content Simplification Agent
=====================================================================
AGENT_INSTRUCTIONS
=====================================================================
Customize the agent's behaviour by editing the sections below.
Each section is clearly labelled. Changes take effect immediately
on the next request — no restart required for most settings.
=====================================================================
"""

import os
import json
import re
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# =====================================================================
#  AGENT_INSTRUCTIONS — Edit this block to customize the agent
# =====================================================================

AGENT_INSTRUCTIONS = {

    # ------------------------------------------------------------------
    #  IDENTITY & ROLE
    # ------------------------------------------------------------------
    "agent_name": "EduSimpli",
    "agent_role": (
        "You are EduSimpli, an expert AI tutor and educational content simplification agent "
        "powered by IBM Granite. Your mission is to make complex academic material accessible "
        "to every learner regardless of their background."
    ),

    # ------------------------------------------------------------------
    #  RESPONSE TONE
    #  Options: friendly | formal | socratic | encouraging | concise
    # ------------------------------------------------------------------
    "response_tone": "friendly",
    "tone_guidelines": {
        "friendly":     "Be warm, approachable, and conversational. Use 'you' and 'we'.",
        "formal":       "Be precise, professional, and avoid contractions.",
        "socratic":     "Guide with questions and let the learner discover answers.",
        "encouraging":  "Celebrate effort, highlight progress, and motivate.",
        "concise":      "Be ultra-brief. Bullet points over prose. No filler words.",
    },

    # ------------------------------------------------------------------
    #  EXPLANATION STYLE
    #  Options: analogy-first | example-first | definition-first |
    #           visual-description | step-by-step
    # ------------------------------------------------------------------
    "explanation_style": "analogy-first",

    # ------------------------------------------------------------------
    #  EDUCATIONAL DOMAIN
    #  The agent will tailor examples and vocabulary to this domain.
    #  Examples: General Education | Computer Science | Medicine |
    #            Engineering | Business | Law | Sciences | Mathematics
    # ------------------------------------------------------------------
    "educational_domain": os.getenv("AGENT_DOMAIN", "General Education"),

    # ------------------------------------------------------------------
    #  LEARNING LEVEL PROFILES
    #  Describes how the agent should adapt content per level
    # ------------------------------------------------------------------
    "level_profiles": {
        "Beginner": {
            "vocab":       "everyday language, avoid jargon",
            "depth":       "surface-level overview, key takeaways only",
            "analogies":   "use familiar real-world comparisons (e.g., cooking, sports)",
            "examples":    "concrete, tangible, single-step",
            "max_tokens":  600,
        },
        "Intermediate": {
            "vocab":       "introduce domain terms with inline definitions",
            "depth":       "moderate depth; include 'how' alongside 'what'",
            "analogies":   "domain-adjacent comparisons",
            "examples":    "multi-step, slightly abstract",
            "max_tokens":  800,
        },
        "Advanced": {
            "vocab":       "full technical vocabulary assumed",
            "depth":       "deep dive; include edge cases and nuances",
            "analogies":   "technical metaphors are acceptable",
            "examples":    "realistic, problem-solving oriented",
            "max_tokens":  1000,
        },
        "Expert": {
            "vocab":       "peer-level terminology; reference standards where relevant",
            "depth":       "research-grade depth; discuss trade-offs and limitations",
            "analogies":   "use sparingly; prioritize formal reasoning",
            "examples":    "case studies, research scenarios, open questions",
            "max_tokens":  1200,
        },
    },

    # ------------------------------------------------------------------
    #  OUTPUT FORMAT RULES
    # ------------------------------------------------------------------
    "output_format": {
        "use_markdown":    True,
        "use_emojis":      True,
        "max_bullet_depth": 2,
        "always_include_summary": True,
        "highlight_keywords": True,
    },

    # ------------------------------------------------------------------
    #  SAFETY & CONTENT RULES
    # ------------------------------------------------------------------
    "safety_rules": [
        "Never produce harmful, discriminatory, or offensive content.",
        "Do not answer questions unrelated to education or the uploaded content.",
        "If asked for personal opinions on controversial topics, stay neutral.",
        "Do not fabricate citations or references; say 'I don't know' if unsure.",
        "Respect academic integrity — guide understanding, do not write assignments for submission.",
        "If content is outside the uploaded document, say so explicitly.",
    ],

    # ------------------------------------------------------------------
    #  LEARNING PREFERENCES
    # ------------------------------------------------------------------
    "learning_preferences": {
        "default_level":          os.getenv("AGENT_DEFAULT_LEVEL", "Beginner"),
        "include_flashcards":     True,
        "include_quiz":           True,
        "include_glossary":       True,
        "include_key_concepts":   True,
        "include_real_examples":  True,
        "include_analogies":      True,
        "highlight_important":    True,
        "follow_up_suggestions":  True,
    },

    # ------------------------------------------------------------------
    #  IBM GRANITE MODEL SETTINGS
    #  Primary:  ibm/granite-8b-code-instruct  (Granite, available on Lite)
    #  Fallback: meta-llama/llama-3-3-70b-instruct (best general model on Lite)
    #  Override via env: MODEL_ID=ibm/granite-4-h-small
    # ------------------------------------------------------------------
    "model_id": os.getenv("MODEL_ID", "meta-llama/llama-3-3-70b-instruct"),
    "fallback_model_id": "ibm/granite-8b-code-instruct",
    "default_params": {
        "max_new_tokens": 800,
        "temperature":    0.4,
        "top_p":          0.9,
        "repetition_penalty": 1.1,
    },
}

# =====================================================================
#  WATSONX CLIENT
# =====================================================================

# Module-level client cache so we don't re-authenticate on every request
_client_cache: dict = {}

def _get_watsonx_client(model_id: str = None):
    """
    Lazy-initialize and cache the IBM Watsonx.ai ModelInference client.
    Tries the primary model first, falls back to fallback_model_id on
    WMLClientError (e.g. model not supported in the account's plan).
    """
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.wml_client_error import WMLClientError

    api_key    = os.getenv("IBM_API_KEY", "")
    project_id = os.getenv("IBM_PROJECT_ID", "")
    url        = os.getenv("IBM_WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

    if not api_key or api_key == "your_ibm_cloud_api_key_here":
        raise ValueError(
            "IBM_API_KEY is missing or still set to the placeholder. "
            "Copy .env.example to .env and add your real IBM Cloud API key."
        )
    if not project_id or project_id == "your_watsonx_project_id_here":
        raise ValueError(
            "IBM_PROJECT_ID is missing or still set to the placeholder. "
            "Find your project ID at https://dataplatform.cloud.ibm.com → your project → Manage."
        )

    use_model = model_id or AGENT_INSTRUCTIONS["model_id"]
    cache_key = f"{project_id}:{use_model}"

    if cache_key in _client_cache:
        return _client_cache[cache_key]

    credentials = Credentials(api_key=api_key, url=url)

    # Try primary model, auto-fallback on unsupported model error
    for attempt_model in [use_model, AGENT_INSTRUCTIONS["fallback_model_id"]]:
        try:
            client = ModelInference(
                model_id=attempt_model,
                credentials=credentials,
                project_id=project_id,
                params=AGENT_INSTRUCTIONS["default_params"],
            )
            if attempt_model != use_model:
                logger.warning(
                    "Primary model '%s' unavailable; using fallback '%s'.",
                    use_model, attempt_model
                )
            _client_cache[cache_key] = client
            return client
        except WMLClientError as exc:
            msg = str(exc)
            if "not supported" in msg or "Supported models" in msg:
                # Extract the list for a helpful log message
                import re
                supported = re.search(r"Supported models: (\[.*?\])", msg)
                hint = f" Available: {supported.group(1)}" if supported else ""
                logger.warning("Model '%s' not available in this account.%s", attempt_model, hint)
                if attempt_model == AGENT_INSTRUCTIONS["fallback_model_id"]:
                    raise ValueError(
                        f"Neither '{use_model}' nor the fallback model are available in your "
                        f"Watsonx.ai account/plan.{hint}\n"
                        "Set MODEL_ID in .env to one of the supported models above."
                    )
                continue  # try fallback
            # Re-raise other errors (bad project ID, auth, etc.)
            raise


# =====================================================================
#  PROMPT BUILDERS
# =====================================================================

def _build_system_prompt(level: str, task: str) -> str:
    """Construct the system portion of the prompt from AGENT_INSTRUCTIONS."""
    ins = AGENT_INSTRUCTIONS
    profile = ins["level_profiles"].get(level, ins["level_profiles"]["Beginner"])
    tone_guide = ins["tone_guidelines"].get(ins["response_tone"], "")
    safety = "\n".join(f"- {r}" for r in ins["safety_rules"])

    return f"""{ins['agent_role']}

## Current Task
{task}

## Learner Level: {level}
- Vocabulary: {profile['vocab']}
- Depth: {profile['depth']}
- Analogies: {profile['analogies']}
- Examples: {profile['examples']}

## Tone
{tone_guide}

## Explanation Style
{ins['explanation_style']}

## Domain
{ins['educational_domain']}

## Safety Rules
{safety}

## Output Format
- Use Markdown formatting.
- Emoji usage: {'Yes — use relevant emojis to highlight sections' if ins['output_format']['use_emojis'] else 'No emojis'}.
- Keep bullet nesting ≤ {ins['output_format']['max_bullet_depth']} levels.
- Always end with a short **Summary** section.
- Bold **key terms** on first use.
"""


def _build_simplify_prompt(text: str, level: str, topic: str = "") -> str:
    task = f"Simplify and explain the following educational content for a {level} learner."
    if topic:
        task += f" Focus on the topic: {topic}."
    system = _build_system_prompt(level, task)
    profile = AGENT_INSTRUCTIONS["level_profiles"].get(level, {})

    return f"""{system}

---
## Content to Simplify
{text[:4000]}
---

Please provide:
1. 📌 **Simple Explanation** — plain-language breakdown
2. 🔑 **Key Concepts** — bullet list of core ideas
3. 💡 **Real-World Example** — relatable scenario
4. 🔄 **Analogy** — compare to something familiar ({profile.get('analogies','')})
5. ⭐ **Important Points** — what the learner must remember
6. 📝 **Summary** — 2-3 sentence recap

Begin:
"""


def _build_chat_prompt(user_message: str, context: str, history: list, level: str) -> str:
    task = "Answer the learner's follow-up question about the uploaded educational content."
    system = _build_system_prompt(level, task)
    history_str = ""
    for msg in history[-6:]:   # last 6 turns for context window management
        role  = "Student" if msg["role"] == "user" else "EduSimpli"
        history_str += f"{role}: {msg['content']}\n"

    return f"""{system}

## Document Context (excerpt)
{context[:2000]}

## Conversation History
{history_str}

## Student's Question
{user_message}

EduSimpli:"""


def _build_quiz_prompt(text: str, level: str, num_questions: int = 5) -> str:
    task = f"Generate a {num_questions}-question quiz from the content for a {level} learner."
    system = _build_system_prompt(level, task)

    return f"""{system}

## Content
{text[:3000]}

Generate exactly {num_questions} multiple-choice questions. Return ONLY valid JSON in this format:
[
  {{
    "question": "Question text",
    "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
    "answer": "A",
    "explanation": "Why this answer is correct"
  }}
]

JSON output:"""


def _build_flashcard_prompt(text: str, level: str) -> str:
    task = "Generate flashcards (term → definition) from the content."
    system = _build_system_prompt(level, task)

    return f"""{system}

## Content
{text[:3000]}

Generate 8-10 flashcards. Return ONLY valid JSON:
[
  {{"term": "Technical Term", "definition": "Plain-language definition", "example": "Short example"}}
]

JSON output:"""


def _build_glossary_prompt(text: str, level: str) -> str:
    task = "Extract a glossary of technical terms from the content."
    system = _build_system_prompt(level, task)

    return f"""{system}

## Content
{text[:3000]}

Extract 10-15 key terms. Return ONLY valid JSON:
{{"term": "definition"}}

JSON output:"""


def _build_summary_prompt(text: str, level: str) -> str:
    task = "Create a structured topic-wise summary of the content."
    system = _build_system_prompt(level, task)

    return f"""{system}

## Content
{text[:4000]}

Provide:
- **Title** of the document/topic
- **Main Topics** (list with brief descriptions)
- **Key Takeaways** (3-5 bullets)
- **One-Line Summary**

Begin:"""


# =====================================================================
#  RESPONSE PARSER HELPERS
# =====================================================================

def _extract_json(text: str):
    """Best-effort JSON extraction from model output."""
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting first JSON array or object
    for pattern in (r'\[.*\]', r'\{.*\}'):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


def _call_model(prompt: str, max_tokens: int = 800) -> str:
    """Send prompt to Watsonx and return the generated text."""
    try:
        model = _get_watsonx_client()
        params = {**AGENT_INSTRUCTIONS["default_params"], "max_new_tokens": max_tokens}
        response = model.generate_text(prompt=prompt, params=params)
        return response.strip() if isinstance(response, str) else str(response)
    except Exception as exc:
        msg = str(exc)
        logger.error("Watsonx generation error: %s", msg)

        # Translate IBM error codes into plain English
        if "invalid_instance_status_error" in msg or "Inactive" in msg:
            raise RuntimeError(
                "Your Watson Machine Learning service instance is **Inactive**.\n\n"
                "**How to fix it:**\n"
                "1. Go to https://cloud.ibm.com/resources\n"
                "2. Find your **Watson Machine Learning** instance (status: Inactive)\n"
                "3. Click it → click **Activate** or upgrade to a Lite/Plus plan\n"
                "4. Return here and try again."
            ) from exc
        if "invalid_instance_status_error" in msg or "403" in msg:
            raise RuntimeError(
                "IBM Cloud returned 403 Forbidden. Your WML instance may be inactive or "
                "your API key may not have access to this project."
            ) from exc
        if "not_found" in msg or "404" in msg:
            raise RuntimeError(
                "IBM Project not found (404). Check that IBM_PROJECT_ID in your .env "
                "matches a project visible at https://dataplatform.cloud.ibm.com"
            ) from exc
        if "IBM_API_KEY" in msg or "IBM_PROJECT_ID" in msg:
            raise  # already a clear ValueError
        raise RuntimeError(f"AI service error: {msg}") from exc


# =====================================================================
#  PUBLIC API — called by app.py
# =====================================================================

def simplify_content(text: str, level: str, topic: str = "") -> str:
    profile = AGENT_INSTRUCTIONS["level_profiles"].get(level, {})
    max_tok = profile.get("max_tokens", 800)
    prompt  = _build_simplify_prompt(text, level, topic)
    return _call_model(prompt, max_tokens=max_tok)


def chat_with_agent(user_message: str, context: str, history: list, level: str) -> str:
    profile = AGENT_INSTRUCTIONS["level_profiles"].get(level, {})
    max_tok = profile.get("max_tokens", 800)
    prompt  = _build_chat_prompt(user_message, context, history, level)
    return _call_model(prompt, max_tokens=max_tok)


def generate_quiz(text: str, level: str, num_questions: int = 5) -> list:
    prompt   = _build_quiz_prompt(text, level, num_questions)
    raw      = _call_model(prompt, max_tokens=1200)
    parsed   = _extract_json(raw)
    if isinstance(parsed, list):
        return parsed
    # Fallback: return stub
    return [{"question": "Could not parse quiz.", "options": [], "answer": "", "explanation": raw[:200]}]


def generate_flashcards(text: str, level: str) -> list:
    prompt = _build_flashcard_prompt(text, level)
    raw    = _call_model(prompt, max_tokens=1000)
    parsed = _extract_json(raw)
    if isinstance(parsed, list):
        return parsed
    return []


def generate_glossary(text: str, level: str) -> dict:
    prompt = _build_glossary_prompt(text, level)
    raw    = _call_model(prompt, max_tokens=1000)
    parsed = _extract_json(raw)
    if isinstance(parsed, dict):
        return parsed
    return {}


def generate_summary(text: str, level: str) -> str:
    prompt = _build_summary_prompt(text, level)
    return _call_model(prompt, max_tokens=800)


def get_recommendations(user_level: str, recent_topics: list) -> str:
    topics_str = ", ".join(recent_topics[:5]) if recent_topics else "general topics"
    prompt = (
        f"As EduSimpli, give 3-4 personalized study recommendations for a {user_level} learner "
        f"who recently studied: {topics_str}. Format as a friendly Markdown list with brief rationale."
    )
    return _call_model(prompt, max_tokens=400)
