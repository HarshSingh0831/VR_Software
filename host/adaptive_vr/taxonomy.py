from enum import StrEnum


class Engagement(StrEnum):
    ENGAGED = "engaged"
    NOT_ENGAGED = "not_engaged"


class StudentState(StrEnum):
    FOCUSED = "focused"
    THINKING = "thinking"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    HAPPY = "happy"
    ANSWERING = "answering"
    BORED = "bored"
    DROWSY = "drowsy"
    LOOKING_AWAY = "looking_away"
    DISTRACTED = "distracted"
    IDLE = "idle"
    HEADSET_REMOVED = "headset_removed"


STATE_ENGAGEMENT = {
    StudentState.FOCUSED: Engagement.ENGAGED,
    StudentState.THINKING: Engagement.ENGAGED,
    StudentState.CONFUSED: Engagement.ENGAGED,
    StudentState.FRUSTRATED: Engagement.ENGAGED,
    StudentState.HAPPY: Engagement.ENGAGED,
    StudentState.ANSWERING: Engagement.ENGAGED,
    StudentState.BORED: Engagement.NOT_ENGAGED,
    StudentState.DROWSY: Engagement.NOT_ENGAGED,
    StudentState.LOOKING_AWAY: Engagement.NOT_ENGAGED,
    StudentState.DISTRACTED: Engagement.NOT_ENGAGED,
    StudentState.IDLE: Engagement.NOT_ENGAGED,
    StudentState.HEADSET_REMOVED: Engagement.NOT_ENGAGED,
}

