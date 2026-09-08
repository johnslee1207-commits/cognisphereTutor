"""Built-in capability class paths."""

BUILTIN_CAPABILITY_CLASSES: dict[str, str] = {
    "chat": "cognispheretutor.agents.chat.capability:ChatCapability",
    "deep_solve": "cognispheretutor.capabilities.solve.capability:DeepSolveCapability",
    "deep_question": "cognispheretutor.agents.question.capability:DeepQuestionCapability",
    "deep_research": "cognispheretutor.agents.research.capability:DeepResearchCapability",
    "math_animator": "cognispheretutor.agents.math_animator.capability:MathAnimatorCapability",
    "visualize": "cognispheretutor.agents.visualize.capability:VisualizeCapability",
    "mastery_path": "cognispheretutor.capabilities.mastery.capability:MasteryPathCapability",
}
