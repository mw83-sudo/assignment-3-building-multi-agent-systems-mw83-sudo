"""
Main Entry Point
Can be used to run the system or evaluation.

Usage:
  python main.py --mode cli           # Run CLI interface
  python main.py --mode web           # Run web interface
  python main.py --mode evaluate      # Run evaluation
"""

import argparse
import asyncio
import sys
from pathlib import Path
import logging


def run_cli(config_path: str = "config.yaml"):
    """Run CLI interface."""
    from src.ui.cli import CLI
    cli = CLI(config_path=config_path)
    asyncio.run(cli.run())


def run_web():
    """Run web interface."""
    import subprocess
    print("Starting Streamlit web interface...")
    subprocess.run(["streamlit", "run", "src/ui/streamlit_app.py"])


async def run_evaluation():
    """Run system evaluation."""
    import yaml
    from dotenv import load_dotenv
    from src.autogen_orchestrator import AutoGenOrchestrator
    from src.evaluation.evaluator import SystemEvaluator
    
    # Load environment variables
    load_dotenv()

    # Load config
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    logging.basicConfig(
        level=getattr(logging, config.get("logging", {}).get("level", "INFO")),
        format=config.get("logging", {}).get(
            "format",
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
        force=True,
    )

    # Initialize AutoGen orchestrator
    print("Initializing AutoGen orchestrator...")
    orchestrator = AutoGenOrchestrator(config)
    
    # Run full evaluation
    evaluator = SystemEvaluator(config, orchestrator=orchestrator)
    report = await evaluator.evaluate_system("data/example_queries.json")
    
    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total Queries: {report.get('summary', {}).get('total_queries', 0)}")
    print(f"Successful: {report.get('summary', {}).get('successful', 0)}")
    print(f"Failed: {report.get('summary', {}).get('failed', 0)}")
    print(f"Success Rate: {report.get('summary', {}).get('success_rate', 0.0):.2%}")
    print(f"Overall Average Score: {report.get('scores', {}).get('overall_average', 0.0):.3f}")
    print("\nScores by Criterion:")
    for criterion, score in report.get("scores", {}).get("by_criterion", {}).items():
        print(f"  - {criterion}: {score:.3f}")


def run_autogen(config_path: str = "config.yaml"):
    """Run AutoGen end-to-end demo query through the real orchestrator."""
    import yaml
    from dotenv import load_dotenv
    from src.autogen_orchestrator import AutoGenOrchestrator

    load_dotenv()

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    print("Initializing AutoGen orchestrator...")
    orchestrator = AutoGenOrchestrator(config)

    print("\n" + "=" * 70)
    print("RUNNING AUTOGEN DEMO QUERY")
    print("=" * 70)

    test_query = "What are the key principles of accessible user interface design?"
    print(f"\nQuery: {test_query}\n")

    result = orchestrator.process_query(test_query)

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\nResponse:\n{result.get('response', 'No response generated')}")

    print(f"\nMetadata:")
    print(f"  - Messages: {result.get('metadata', {}).get('num_messages', 0)}")
    print(f"  - Sources: {result.get('metadata', {}).get('num_sources', 0)}")

    citations = result.get("citations", [])
    if citations:
        print("\nSources:")
        for citation in citations:
            print(f"  [{citation['index']}] {citation.get('title', '')} — {citation.get('url', '')}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Research Assistant"
    )
    parser.add_argument(
        "--mode",
        choices=["cli", "web", "evaluate", "autogen"],
        default="autogen",
        help="Mode to run: cli, web, evaluate, or autogen (default)"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file"
    )
    args = parser.parse_args()

    if args.mode == "cli":
        run_cli(args.config)
    elif args.mode == "web":
        run_web()
    elif args.mode == "evaluate":
        asyncio.run(run_evaluation())
    elif args.mode == "autogen":
        run_autogen(args.config)


if __name__ == "__main__":
    main()
