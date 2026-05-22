"""Run a single end-to-end demo and export artifacts.

This script runs a single query through AutoGenOrchestrator and saves:
- outputs/session_example.json
- outputs/final_answer_example.md
- outputs/judge_prompts_example.txt

Use: python run_demo.py
"""
import json
from pathlib import Path
import yaml
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        return None

def main():
    load_dotenv()

    repo_root = Path(__file__).parent
    outputs_dir = repo_root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Load config
    config_path = repo_root / "config.yaml"
    if not config_path.exists():
        print("config.yaml not found in repo root. Please provide a config file.")
        return

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    # Try to initialize orchestrator; if dependencies missing, fall back to sample outputs
    try:
        # Import orchestrator lazily so missing AutoGen deps don't break the script
        try:
            from src.autogen_orchestrator import AutoGenOrchestrator
        except Exception:
            AutoGenOrchestrator = None

        if AutoGenOrchestrator:
            orchestrator = AutoGenOrchestrator(config)

            # Representative demo query (can be customized)
            demo_query = config.get("demo", {}).get("query", "What are the key principles of explainable AI for novice users?")
            print(f"Running demo query: {demo_query}")

            result = orchestrator.process_query(demo_query)
        else:
            raise ImportError("AutoGenOrchestrator or its dependencies are not available")
    except Exception as e:
        print(f"Failed to initialize orchestrator or run demo: {e}")
        print("Falling back to existing evaluation output to generate demo artifacts.")
        # Load a recent evaluation file if available
        fallback = None
        candidate = Path("outputs") / "evaluation_20260423_120900.json"
        if candidate.exists():
            with open(candidate, 'r') as f:
                fallback = json.load(f)
        else:
            # Try to locate any evaluation file
            import glob
            files = sorted(glob.glob("outputs/evaluation_*.json"), reverse=True)
            if files:
                with open(files[0], 'r') as f:
                    fallback = json.load(f)

        if fallback and fallback.get('detailed_results'):
            # Use the first detailed result as demo
            demo_item = fallback['detailed_results'][0]
            demo_query = demo_item.get('query', '')
            result = {
                'query': demo_query,
                'response': demo_item.get('response', ''),
                'conversation_history': demo_item.get('conversation_history', []),
                'sources': demo_item.get('sources', []),
                'citations': [],
                'metadata': demo_item.get('metadata', {}),
            }
        else:
            print("No fallback evaluation artifacts found. Exiting.")
            return

    # Save session JSON
    session_path = outputs_dir / "session_example.json"
    with open(session_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Saved session to: {session_path}")

    # Save final answer as Markdown with citations
    final_md_path = outputs_dir / "final_answer_example.md"
    with open(final_md_path, 'w') as f:
        f.write(f"# Answer: {demo_query}\n\n")
        f.write(result.get('response', '') + "\n\n")

        citations = result.get('citations', []) or result.get('metadata', {}).get('sources', [])
        if citations:
            f.write("## Sources\n\n")
            # If citations are in object form, format them
            if isinstance(citations, list) and citations and isinstance(citations[0], dict):
                for c in citations:
                    title = c.get('title') or c.get('formatted') or c.get('url')
                    url = c.get('url', '')
                    f.write(f"- {title} — {url}\n")
            else:
                for c in citations:
                    f.write(f"- {c}\n")
    print(f"Saved final answer markdown to: {final_md_path}")

    # Save judge prompts if available
    judge_prompts_path = outputs_dir / "judge_prompts_example.txt"
    judge_prompts = []
    # Try to reconstruct judge prompts from orchestrator/evaluation modules if present
    try:
        from src.evaluation.judge import LLMJudge
        judge = LLMJudge(config)
        p1 = judge._create_research_quality_prompt(
            query=demo_query,
            response=result.get('response',''),
            sources=result.get('sources',[]),
            ground_truth=None
        )
        p2 = judge._create_safety_reliability_prompt(
            query=demo_query,
            response=result.get('response',''),
            sources=result.get('sources',[]),
            ground_truth=None
        )
        judge_prompts = [p1, p2]
    except Exception:
        # Best-effort only; judge module may require API keys
        judge_prompts = ["<judge prompts unavailable - check GROQ_API_KEY or judge module>\n"]

    with open(judge_prompts_path, 'w') as f:
        for i, p in enumerate(judge_prompts, 1):
            f.write(f"--- Prompt {i} ---\n")
            f.write(p + "\n\n")
    print(f"Saved judge prompts to: {judge_prompts_path}")


if __name__ == '__main__':
    main()
