"""Factory module for dynamic CrewAI Agent instantiation from YAML configurations."""

import os
import logging
from typing import List, Optional, Tuple
from crewai import Agent

from src.config_loader import AgentYamlConfig, ManagerYamlConfig, TeamYamlConfig
from src.agents.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


def load_prompt_content(prompt_path: Optional[str]) -> str:
    """
    Load custom prompt text file content if specified and path exists.
    
    :param prompt_path: Path to prompt text file
    :return: Content of prompt file or empty string if not found
    """
    if not prompt_path:
        return ""

    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                logger.info(f"Successfully loaded prompt file: {prompt_path}")
                return content
        except Exception as e:
            logger.warning(f"Failed to read prompt file '{prompt_path}': {e}")
            return ""

    logger.warning(f"Prompt file not found at path: {prompt_path}")
    return ""


def create_agent_from_yaml(agent_cfg: AgentYamlConfig) -> Agent:
    """
    Instantiate a CrewAI Agent from YAML agent configuration.
    
    :param agent_cfg: Validated AgentYamlConfig model instance
    :return: Configured CrewAI Agent instance
    """
    # Load prompt text if available
    prompt_text = load_prompt_content(agent_cfg.prompt_file)
    backstory = agent_cfg.backstory or ""
    if prompt_text:
        backstory = f"{backstory}\n\n[Prompt Instructions]\n{prompt_text}".strip()

    # Resolve assigned tools from registry
    agent_tools = []
    if agent_cfg.tools:
        for tool_name in agent_cfg.tools:
            if tool_name in TOOL_REGISTRY:
                agent_tools.append(TOOL_REGISTRY[tool_name])
            else:
                logger.warning(f"Tool '{tool_name}' requested by agent '{agent_cfg.name}' not found in TOOL_REGISTRY.")

    logger.info(
        f"Creating CrewAI Agent '{agent_cfg.name}' (Role: '{agent_cfg.role}', "
        f"LLM: '{agent_cfg.llm_model}', Tools: {len(agent_tools)})"
    )

    return Agent(
        role=agent_cfg.role,
        goal=agent_cfg.goal,
        backstory=backstory,
        llm=agent_cfg.llm_model,
        tools=agent_tools,
        verbose=True,
        allow_delegation=False,
    )


def create_manager_agent_from_yaml(manager_cfg: ManagerYamlConfig) -> Agent:
    """
    Instantiate a Manager CrewAI Agent from YAML manager configuration.
    
    :param manager_cfg: Validated ManagerYamlConfig model instance
    :return: Configured Manager CrewAI Agent instance
    """
    logger.info(f"Creating Manager Agent '{manager_cfg.name}' (LLM: '{manager_cfg.llm_model}')")

    return Agent(
        role=manager_cfg.role,
        goal=manager_cfg.goal,
        backstory="Senior Lead Orchestrator responsible for team delegation, trade strategy validation, and overall risk management.",
        llm=manager_cfg.llm_model,
        tools=[],
        verbose=True,
        allow_delegation=True,
    )


def build_agents_from_team_config(team_config: TeamYamlConfig) -> Tuple[List[Agent], Optional[Agent]]:
    """
    Instantiate all worker agents and optional manager agent from team YAML configuration.
    
    :param team_config: Validated TeamYamlConfig instance
    :return: Tuple of (list of worker Agents, optional manager Agent)
    """
    worker_agents: List[Agent] = []
    for agent_cfg in team_config.agents:
        agent = create_agent_from_yaml(agent_cfg)
        worker_agents.append(agent)

    manager_agent: Optional[Agent] = None
    if team_config.team.architecture == "hierarchical" and team_config.manager:
        manager_agent = create_manager_agent_from_yaml(team_config.manager)

    return worker_agents, manager_agent
