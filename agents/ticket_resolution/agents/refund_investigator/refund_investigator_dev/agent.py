from agents.ticket_resolution.agents.refund_investigator.agent import refund_investigator_agent

root_agent = refund_investigator_agent.clone(update={
    "mode": "chat"
})
