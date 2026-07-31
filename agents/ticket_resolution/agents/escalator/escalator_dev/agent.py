from agents.ticket_resolution.agents.escalator.agent import escalator_agent

root_agent = escalator_agent.clone(update={
    "mode": "chat"
})
