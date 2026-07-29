from agents.ticket_resolution.agents.account_operator.agent import account_operator_agent

root_agent = account_operator_agent.clone(update={
    "mode": "chat"
})
