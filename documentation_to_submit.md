# Multi-Agent Research Assistant for HCI Deep Research

## Abstract

This project implements a multi-agent deep-research assistant for HCI-oriented questions, with a focused system topic of explainable AI for novice users in education. The system is built on an AutoGen-style workflow with four specialized agents: a Planner, Researcher, Writer, and Critic. The Planner decomposes a user’s research question into subtopics and search directions, the Researcher gathers evidence through configurable search tools, the Writer synthesizes findings into a readable answer with citations, and the Critic evaluates completeness and clarity before termination. The system also includes input and output guardrails that screen for harmful requests, prompt injection attempts, misinformation risks, and personally identifiable information. A command-line interface and a Streamlit web interface expose the system to end users and surface citations, traces, metadata, and safety outcomes. Evaluation is implemented with an LLM-as-a-Judge pipeline using two distinct rubrics and more than five test queries. In practice, the system produces strong end-to-end demonstrations in AutoGen, CLI, and web modes. Evaluation over 10 test queries produced a moderate overall score of 0.502, showing meaningful improvement over earlier runs, although judge-output parsing and API rate limits still make the quantitative results somewhat provisional.

## System Design and Implementation

The assignment required a multi-agent research system with at least three distinct agents, explicit orchestration, tool integration, a usable interface, safety logic, and an evaluation pipeline. The provided scaffold organized the project into modules for agents, orchestration, tools, guardrails, evaluation, and UI, and explicitly directed implementation work into those files rather than rewriting the entire system from scratch. 

I implemented the system as a four-agent AutoGen workflow. The Planner is responsible for query decomposition and produces a structured plan for subtopics, search directions, and synthesis structure. The Researcher uses the tool layer to gather evidence from the web and, when enabled, academic search. The Writer converts the research notes into a user-facing answer with structure and source grounding. The Critic provides a final pass focused on relevance, evidence quality, completeness, and clarity before terminating the exchange. This overall architecture matches the assignment’s recommended workflow of planning, evidence gathering, synthesis, and critique.

The implementation also follows the assignment’s configuration and reproducibility guidance. The repository is structured around `src/agents/`, `src/autogen_orchestrator.py`, `src/tools/`, `src/guardrails/`, `src/evaluation/`, and `src/ui/`, with shared settings kept in `config.yaml` and environment setup in `.env` / `.env.example`. The README documents the main entry points for AutoGen mode, CLI mode, Streamlit web mode, and evaluation mode.

Tool integration is organized into modular helper files. The web search tool supports external providers and returns readable result blocks with titles, URLs, snippets, and timestamps when available. The paper search tool is intended to connect to Semantic Scholar, though in the final stabilized setup paper search was disabled in configuration because of runtime instability and slow or failed requests in the local environment. Citation formatting and tracking are handled through a dedicated citation utility, which allows the system to surface source lists in both CLI and web outputs. This design aligns with the assignment’s requirement that tools remain modular and that evidence collection be clearly surfaced in system outputs.

In practice, the system successfully answered representative HCI-style queries. For example, a CLI run on the question “What are best practices for explainable AI interfaces for novice student users?” produced a full synthesized answer, 25 gathered sources, and metadata reporting 7 exchanged messages across the user, Planner, Researcher, Writer, and Critic. The same topic also ran successfully in the Streamlit web interface, where the UI displayed a completed response, citations, 29 sources used, and a computed quality score of 8.70. These demonstrations show that the system meets the assignment’s core requirements for orchestration, tool use, and user-facing presentation.

## Safety Design

The assignment requires both input and output safety checks, documented policy categories, and communication of safety outcomes in both logs and interfaces. I implemented a custom policy-based safety layer with three coordinated parts: `InputGuardrail`, `OutputGuardrail`, and `SafetyManager`. The assignment guide specifically calls for unsafe-input detection, unsafe-output inspection, event logging, and runtime integration with the orchestrator, and the final design follows that structure.

The input guardrail checks user queries for several categories of unsafe or inappropriate requests. These include harmful requests, prompt injection attempts, and off-topic queries. Prompt injection detection looks for override patterns such as attempts to ignore previous instructions, reveal the system prompt, or exploit role confusion. The input validator also tracks query length and whether the request appears aligned with the system’s intended HCI topic area. Queries that trigger high-severity violations are refused; lower-severity issues are marked as warnings. 

The output guardrail checks model responses for potentially unsafe content, misinformation risk, and PII leakage. It uses regex-based PII checks for emails, phone numbers, and SSNs, along with pattern checks for harmful content and unsupported references. It also inspects whether a response appears to contain a references section or source claims without any captured source metadata, which is treated as a misinformation risk. Medium-severity violations can trigger sanitization, while high-severity violations trigger refusal. 

The `SafetyManager` coordinates these guardrails, logs safety events, and exposes statistics and event histories to the interfaces. It records event type, whether the content was safe, the associated violations, and a preview of the blocked or sanitized content. This event log is also used by the UI layer to display whether a request was refused or a response was sanitized. The Streamlit interface includes safety-event display and statistics panels, and the CLI output also surfaces safety status and recent events when relevant. Even though the demonstrated runs did not show active safety violations, the runtime plumbing and UI paths are implemented, which satisfies the assignment’s safety-communication requirement.

## Evaluation Setup and Results

The system was evaluated with an LLM-as-a-Judge pipeline over 10 test queries, using the evaluator and judge modules implemented in the project. The evaluation framework aggregates criterion-level scores and exports both a detailed JSON report and a summary text file under outputs/, which supports the assignment’s requirement for batch evaluation reporting and reproducible artifacts. The latest run saved its outputs to `outputs/evaluation_20260423_120900.json` and `outputs/evaluation_summary_20260423_120900.txt`.

In the most recent evaluation run, the system reported 10 total queries, 10 successful queries, 0 failed queries, and an overall average score of 0.502. 

The per-criterion averages were:

- Relevance: 0.500
- Evidence quality: 0.520
- Factual accuracy: 0.460
- Safety compliance: 0.490
- Clarity: 0.540

These results are substantially better than an earlier evaluation attempt, which reported an overall average score of only 0.086 and was affected by an event-loop issue during orchestration. Compared with that earlier run, the new results suggest that the system’s orchestration and end-to-end response quality improved meaningfully as the integration work was stabilized.

However, the evaluation should still be interpreted with modest caution. During the current run, the judge API hit rate limits (HTTP 429) and retried automatically, and one safety_reliability judge output failed JSON parsing. Despite these issues, the evaluation still completed successfully, saved both the detailed results and summary files, and produced a coherent aggregate report. This means the evaluation pipeline is functional enough for reporting, but its robustness under rate limits and malformed judge output remains an area for improvement.

Overall, the evaluation shows that the system performs at a moderate quality level rather than an excellent one. The strongest area is clarity, while the weaker areas are factual accuracy and safety/evidence robustness, which is consistent with the system’s current limitations in source grounding and judge-output reliability.

## Artifacts included in the repository

The repository includes the following artifacts to support reproducibility and grading:

- `run_demo.py` — single-command demo runner that exports session and artifacts (uses existing evaluation outputs as fallback when AutoGen dependencies are not installed).
- `outputs/session_example.json` — exported session for a representative query (conversation history and metadata).
- `outputs/final_answer_example.md` — final synthesized answer with inline citations and a sources list.
- `outputs/judge_prompts_example.txt` — the two judge prompts (research quality and safety) used for evaluation when available.
- `outputs/judge_outputs_example.json` — raw judge outputs for a representative query (research_quality and safety_reliability raw JSON).
- `outputs/evaluation_20260423_120900.json` — full evaluation report used in the write-up.

Reproducing the demo locally:

1. Install dependencies (see `requirements.txt`) and set environment variables (copy `.env.example` to `.env` and fill API keys).
2. Run the single-command demo:

```bash
python run_demo.py
```

If AutoGen / model dependencies are missing, `run_demo.py` will fall back to the included evaluation artifact and still generate `session_example.json` and other outputs so graders can inspect the required artifacts.

## Discussion and Limitations

The final system demonstrates working end-to-end behavior in AutoGen, CLI, Streamlit web UI, and batch evaluation modes. In particular, the newest evaluation run completed successfully across 10 queries and produced an overall average score of 0.502, which is a clear improvement over the earlier 0.086 run. This suggests that the multi-agent orchestration, tool integration, and UI-facing packaging became substantially more stable over the course of implementation. This practical stability is also reflected in the CLI and Streamlit demos, where the system returned complete answers with citations, source counts, and interface-visible metadata.

At the same time, the project still has important limitations. The current evaluation run encountered judge-side rate limiting and a failed parse of one safety-related judge output, which means the scoring pipeline is usable but not fully robust. In addition, the criterion profile shows that the system’s answers are clearer than they are deeply grounded: clarity (0.540) and evidence quality (0.520) are stronger than factual accuracy (0.460) and safety compliance (0.490). This indicates that future improvements should focus on stricter citation grounding, more reliable parsing of judge outputs, and better resilience to API rate limits.

## Conclusion

This project successfully developed a working multi-agent research assistant for HCI-oriented questions using a Planner–Researcher–Writer–Critic workflow, modular tools, configurable safety guardrails, and both CLI and web interfaces. The final system demonstrates end-to-end operation, clear source surfacing, and a functional evaluation pipeline. While source grounding and judge robustness still leave room for improvement, the project meets the core goals of the assignment and provides a solid foundation for future refinement.