"""
AutoGen-Based Orchestrator

This orchestrator uses AutoGen's RoundRobinGroupChat to coordinate multiple agents
in a research workflow.

Workflow:
1. Planner: Breaks down the query into research steps
2. Researcher: Gathers evidence using web and paper search tools
3. Writer: Synthesizes findings into a coherent response
4. Critic: Evaluates quality and provides feedback
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional

from src.agents.autogen_agents import create_research_team
import re
from src.guardrails.safety_manager import SafetyManager
from src.tools.citation_tool import CitationTool


class AutoGenOrchestrator:
    """
    Orchestrates multi-agent research using AutoGen's RoundRobinGroupChat.
    
    This orchestrator manages a team of specialized agents that work together
    to answer research queries. It uses AutoGen's built-in conversation
    management and tool execution capabilities.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the AutoGen orchestrator.

        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.logger = logging.getLogger("autogen_orchestrator")
        
        # Create the research team
        self.logger.info("Creating research team...")
        self.team = create_research_team(config)
        
        self.logger.info("Research team created successfully")
        
        # Initialize safety manager
        self.safety_manager = SafetyManager(config)
        
        # Workflow trace for debugging and UI display
        self.workflow_trace: List[Dict[str, Any]] = []

    def process_query(self, query: str, max_rounds: int = 20) -> Dict[str, Any]:
        """
        Process a research query through the multi-agent system.
        """
        self.logger.info(f"Processing query: {query}")
        
        try:
            try:
                asyncio.get_running_loop()
                in_running_loop = True
            except RuntimeError:
                in_running_loop = False

            if not in_running_loop:
                result = asyncio.run(self._process_query_async(query, max_rounds))
            else:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run,
                        self._process_query_async(query, max_rounds)
                    ).result()
            
            self.logger.info("Query processing complete")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                "query": query,
                "error": str(e),
                "response": f"An error occurred while processing your query: {str(e)}",
                "conversation_history": [],
                "sources": [],
                "citations": [],
                "metadata": {
                    "error": True,
                    "num_messages": 0,
                    "num_sources": 0,
                    "agents_involved": [],
                    "safety_events": self.safety_manager.get_safety_events(),
                    "safety_status": {},
                }
            }
    
    async def _process_query_async(self, query: str, max_rounds: int = 20) -> Dict[str, Any]:
        """
        Async implementation of query processing.
        """
        # Input safety check
        input_status = self.safety_manager.check_input_safety(query)
        if input_status.get("action") == "refuse":
            refusal_message = self.config.get("safety", {}).get("on_violation", {}).get(
                "message",
                "I cannot process this request due to safety policies."
            )
            return {
                "query": query,
                "response": refusal_message,
                "conversation_history": [],
                "sources": [],
                "citations": [],
                "metadata": {
                    "num_messages": 0,
                    "num_sources": 0,
                    "plan": "",
                    "research_findings": [],
                    "critique": "",
                    "agents_involved": [],
                    "sources": [],
                    "safety_status": {
                        "input": input_status,
                        "output": {"safe": True, "action": "allow", "violations": []},
                    },
                    "safety_events": self.safety_manager.get_safety_events(),
                }
            }

        # Create task message
        task_message = f"""Research Query: {input_status.get('query', query)}

    Please work together to answer this query comprehensively:
    1. Planner: Create a research plan
    2. Researcher: Gather evidence from web and academic sources
    3. Writer: Synthesize findings into a well-cited response
    4. Critic: Evaluate the quality and provide feedback"""
        
        timeout_seconds = self.config.get("system", {}).get("timeout_seconds", 90)
        self.logger.info(f"Running team with timeout={timeout_seconds}s")
        result = await asyncio.wait_for(self.team.run(task=task_message), timeout=timeout_seconds)
        self.logger.info("Team run completed")

        # Extract conversation history
        messages = []
        for message in result.messages:
            raw_content = getattr(message, "content", str(message))
            msg_dict = {
                "source": getattr(message, "source", "unknown"),
                "content": self._normalize_content(raw_content),
            }
            messages.append(msg_dict)
        
        # Prefer Writer output as final response, then Critic
        final_response = ""
        if messages:
            for msg in reversed(messages):
                if msg.get("source") == "Writer":
                    final_response = msg.get("content", "")
                    break

            if not final_response:
                for msg in reversed(messages):
                    if msg.get("source") == "Critic":
                        final_response = msg.get("content", "")
                        break
        
        if not final_response and messages:
            final_response = messages[-1].get("content", "")

        # Extract sources/citations and run output safety
        sources = self._extract_sources(messages)
        citations = self._build_citations(sources)

        output_status = self.safety_manager.check_output_safety(final_response, sources=sources)
        final_response = output_status.get("response", final_response)

        return self._extract_results(
            query,
            messages,
            final_response,
            sources=sources,
            citations=citations,
            input_status=input_status,
            output_status=output_status
        )
    
    def _normalize_content(self, content: Any) -> str:
        """Normalize AutoGen message content to plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(self._normalize_content(item) for item in content)
        if isinstance(content, dict):
            if "content" in content:
                return self._normalize_content(content["content"])
            if "text" in content:
                return self._normalize_content(content["text"])
            return "\n".join(f"{k}: {self._normalize_content(v)}" for k, v in content.items())
        return str(content)

    def _extract_sources(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract source metadata from message text."""
        sources = []
        seen_urls = set()

        current_title = None
        title_pattern = re.compile(r"^\s*\d+\.\s+(.*)$")
        url_pattern = re.compile(r"^\s*URL:\s*(https?://\S+)\s*$", re.IGNORECASE)

        for msg in messages:
            content = msg.get("content", "")
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue

                title_match = title_pattern.match(line)
                if title_match:
                    current_title = title_match.group(1).strip()
                    continue

                url_match = url_pattern.match(line)
                if url_match:
                    url = url_match.group(1).strip().rstrip(").,")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        sources.append({
                            "type": "webpage",
                            "title": current_title or url,
                            "url": url,
                            "authors": [],
                            "year": None,
                            "site_name": "",
                        })

        return sources

    def _build_citations(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        citation_tool = CitationTool(style="apa")
        citations = []

        for source in sources:
            index = citation_tool.add_citation(source)
            citations.append({
                "index": index,
                "title": source.get("title", f"Source {index}"),
                "url": source.get("url", ""),
                "formatted": citation_tool.format_citation(source),
            })

        citations.sort(key=lambda x: x["index"])
        return citations

    def _extract_results(
        self,
        query: str,
        messages: List[Dict[str, Any]],
        final_response: str = "",
        sources: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        input_status: Optional[Dict[str, Any]] = None,
        output_status: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract structured results from the conversation history.
        """
        research_findings = []
        plan = ""
        critique = ""
        sources = sources or []
        citations = citations or []

        for msg in messages:
            source = msg.get("source", "")
            content = msg.get("content", "")
            
            if source == "Planner" and not plan:
                plan = content
            elif source == "Researcher":
                research_findings.append(content)
            elif source == "Critic":
                critique = content
        
        num_sources = len(sources)

        if final_response:
            final_response = final_response.replace("TERMINATE", "").strip()
        
        return {
            "query": query,
            "response": final_response,
            "conversation_history": messages,
            "sources": sources,
            "citations": citations,
            "metadata": {
                "num_messages": len(messages),
                "num_sources": num_sources,
                "plan": plan,
                "research_findings": research_findings,
                "critique": critique,
                "agents_involved": list(dict.fromkeys([msg.get("source", "") for msg in messages])),
                "sources": sources,
                "safety_status": {
                    "input": input_status or {},
                    "output": output_status or {},
                },
                "safety_events": self.safety_manager.get_safety_events(),
            }
        }

    def get_agent_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions of all agents.

        Returns:
            Dictionary mapping agent names to their descriptions
        """
        return {
            "Planner": "Breaks down research queries into actionable steps",
            "Researcher": "Gathers evidence from web and academic sources",
            "Writer": "Synthesizes findings into coherent responses",
            "Critic": "Evaluates quality and provides feedback",
        }

    def visualize_workflow(self) -> str:
        """
        Generate a text visualization of the workflow.

        Returns:
            String representation of the workflow
        """
        workflow = """
AutoGen Research Workflow:

1. User Query
   ↓
2. Planner
   - Analyzes query
   - Creates research plan
   - Identifies key topics
   ↓
3. Researcher (with tools)
   - Uses web_search() tool
   - Uses paper_search() tool
   - Gathers evidence
   - Collects citations
   ↓
4. Writer
   - Synthesizes findings
   - Creates structured response
   - Adds citations
   ↓
5. Critic
   - Evaluates quality
   - Checks completeness
   - Provides feedback
   ↓
6. Decision Point
   - If APPROVED → Final Response
   - If NEEDS REVISION → Back to Writer
        """
        return workflow


def demonstrate_usage():
    """
    Demonstrate how to use the AutoGen orchestrator.
    
    This function shows a simple example of using the orchestrator.
    """
    import yaml
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Load configuration
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Create orchestrator
    orchestrator = AutoGenOrchestrator(config)
    
    # Print workflow visualization
    print(orchestrator.visualize_workflow())
    
    # Example query
    query = "What are the latest trends in human-computer interaction research?"
    
    print(f"\nProcessing query: {query}\n")
    print("=" * 70)
    
    # Process query
    result = orchestrator.process_query(query)
    
    # Display results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\nQuery: {result['query']}")
    print(f"\nResponse:\n{result['response']}")
    print(f"\nMetadata:")
    print(f"  - Messages exchanged: {result['metadata']['num_messages']}")
    print(f"  - Sources gathered: {result['metadata']['num_sources']}")
    print(f"  - Agents involved: {', '.join(result['metadata']['agents_involved'])}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    demonstrate_usage()

