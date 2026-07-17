from __future__ import annotations

from dataclasses import dataclass

from .taxonomy import StudentState


@dataclass(frozen=True, slots=True)
class AdaptiveAction:
    action: str
    message: str
    cooldown_seconds: int


ACTIONS = {
    StudentState.FOCUSED: AdaptiveAction("continue", "Continue the lesson normally.", 30),
    StudentState.THINKING: AdaptiveAction("wait", "Allow additional response time.", 10),
    StudentState.CONFUSED: AdaptiveAction("simplify", "Offer a simpler explanation or example.", 20),
    StudentState.FRUSTRATED: AdaptiveAction("support", "Reduce difficulty and provide supportive feedback.", 30),
    StudentState.HAPPY: AdaptiveAction("reinforce", "Reinforce progress and continue.", 30),
    StudentState.ANSWERING: AdaptiveAction("listen", "Do not interrupt while the student answers.", 5),
    StudentState.BORED: AdaptiveAction("increase_interactivity", "Introduce a short interactive activity.", 30),
    StudentState.DROWSY: AdaptiveAction("suggest_break", "Pause and suggest a short break.", 60),
    StudentState.LOOKING_AWAY: AdaptiveAction("attention_prompt", "Give a gentle attention reminder.", 20),
    StudentState.DISTRACTED: AdaptiveAction("refocus", "Restore the primary learning task.", 20),
    StudentState.IDLE: AdaptiveAction("offer_help", "Ask whether the student needs help.", 30),
    StudentState.HEADSET_REMOVED: AdaptiveAction("pause", "Pause content and sensing.", 5),
}


def action_for(state: StudentState) -> AdaptiveAction:
    return ACTIONS[state]

