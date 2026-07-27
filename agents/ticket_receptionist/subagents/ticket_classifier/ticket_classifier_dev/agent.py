from agents.ticket_receptionist.subagents.ticket_classifier.agent import ticket_classifier_subagent

root_agent = ticket_classifier_subagent.clone(update={
    "mode": "chat"
})


