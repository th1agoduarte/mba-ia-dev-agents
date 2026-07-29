from agents.ticket_resolution.agents.attendant.agent import attendant_agent

root_agent = attendant_agent.clone(update={
    "mode": "chat"
})
