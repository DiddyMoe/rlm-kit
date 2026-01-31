"""Text analysis and reasoning helpers for AgentEnvironment."""

import json
import re
from collections.abc import Callable
from typing import Any, TypedDict


class ReasoningStep(TypedDict):
    """Type definition for reasoning step."""

    step: str
    reasoning: str


class ReasoningResult(TypedDict):
    """Type definition for reasoning result."""

    problem: str
    reasoning_steps: list[ReasoningStep]
    conclusion: str


class EvaluationResult(TypedDict):
    """Type definition for evaluation result."""

    options: list[str]
    criteria: list[str]
    evaluations: list[dict[str, Any]]
    recommendation: str


class TextAnalyzer:
    """Provides text analysis capabilities using LLM queries."""

    def __init__(self, llm_query_func: Callable[[str], str]) -> None:
        """Initialize text analyzer with LLM query function."""
        self.llm_query: Callable[[str], str] = llm_query_func

    def analyze_text(self, text: str, analysis_type: str = "sentiment") -> dict[str, Any]:
        """Analyze text using LLM capabilities."""
        analysis_prompts: dict[str, str] = {
            "sentiment": f"Analyze the sentiment of this text: {text}",
            "summary": f"Summarize this text in 2-3 sentences: {text}",
            "keywords": f"Extract the main keywords from this text: {text}",
            "entities": f"Extract named entities from this text: {text}",
            "topics": f"Identify the main topics discussed in this text: {text}",
        }
        if analysis_type not in analysis_prompts:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
        result: str = self.llm_query(analysis_prompts[analysis_type])
        return {"analysis_type": analysis_type, "result": result}

    def summarize_context(self, context_data: dict[str, Any]) -> str:
        """Summarize relevant context information."""
        if not context_data:
            return "No context available to summarize."
        context_text: str = json.dumps(context_data, indent=2)
        summary_prompt: str = (
            f"Summarize the following context information concisely:\n\n{context_text}"
        )
        return self.llm_query(summary_prompt)

    def extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extract entities from text."""
        entity_prompt: str = f"""Extract named entities from the following text. Return as JSON with categories: persons, organizations, locations, dates, other.

Text: {text}

Return only valid JSON:"""
        result: str = self.llm_query(entity_prompt)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "persons": re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text),
                "organizations": [],
                "locations": re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)*\b", text)[:5],
                "dates": re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", text),
                "other": [],
            }


class ReasoningHelper:
    """Provides reasoning support functions."""

    def __init__(self, llm_query_func: Callable[[str], str]) -> None:
        """Initialize reasoning helper with LLM query function."""
        self.llm_query: Callable[[str], str] = llm_query_func

    def reason_step_by_step(self, problem: str, steps: list[str] | None = None) -> ReasoningResult:
        """Guide step-by-step reasoning process."""
        reasoning_steps: list[ReasoningStep] = []
        if steps:
            for i, step in enumerate(steps, 1):
                step_prompt: str = (
                    f"Step {i}: {step}\n\nProblem: {problem}\n\nProvide reasoning for this step:"
                )
                reasoning: str = self.llm_query(step_prompt)
                reasoning_steps.append(ReasoningStep(step=step, reasoning=reasoning))
        else:
            planning_prompt: str = f"""Break down how to solve this problem step by step: {problem}

Return a numbered list of steps:"""
            step_list: str = self.llm_query(planning_prompt)
            lines: list[str] = step_list.strip().split("\n")
            for line in lines:
                if line.strip() and (line[0].isdigit() or line.startswith("-")):
                    step_text: str = re.sub(r"^\d+\.?\s*|\-\s*", "", line).strip()
                    if step_text:
                        step_reasoning: str = self.llm_query(
                            f"Problem: {problem}\nStep: {step_text}\n\nExplain how to execute this step:"
                        )
                        reasoning_steps.append(
                            ReasoningStep(step=step_text, reasoning=step_reasoning)
                        )
        return ReasoningResult(
            problem=problem,
            reasoning_steps=reasoning_steps,
            conclusion=self.llm_query(
                f"Based on the reasoning steps above, provide a final conclusion for: {problem}"
            ),
        )

    def evaluate_options(
        self, options: list[str], criteria: list[str] | None = None
    ) -> EvaluationResult:
        """Evaluate multiple options against criteria."""
        if not criteria:
            criteria = ["feasibility", "effectiveness", "cost", "risk"]
        evaluations: list[dict[str, Any]] = []
        for option in options:
            option_eval: dict[str, str] = {}
            for criterion in criteria:
                eval_prompt: str = f"Evaluate '{option}' on the criterion of {criterion}. Rate from 1-10 and explain:"
                result: str = self.llm_query(eval_prompt)
                option_eval[criterion] = result
            evaluations.append({"option": option, "evaluations": option_eval})
        comparison_prompt: str = f"""Compare these options and recommend the best one:

Options: {json.dumps(options, indent=2)}

Evaluations: {json.dumps(evaluations, indent=2)}

Provide a clear recommendation with reasoning:"""
        recommendation: str = self.llm_query(comparison_prompt)
        return EvaluationResult(
            options=options,
            criteria=criteria,
            evaluations=evaluations,
            recommendation=recommendation,
        )

    def make_decision(self, decision_problem: str, options: list[str]) -> dict[str, Any]:
        """Make a decision from multiple options."""
        decision_prompt: str = f"""Make a decision for this problem: {decision_problem}

Available options: {", ".join(options)}

Consider:
1. Pros and cons of each option
2. Potential outcomes
3. Risks and benefits
4. Alignment with goals

Provide:
- Analysis of each option
- Clear recommendation
- Reasoning for the choice"""
        decision: str = self.llm_query(decision_prompt)
        return {"problem": decision_problem, "options": options, "decision": decision}
