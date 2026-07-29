from google.adk import Workflow
from google.adk.workflow import START

from agents.ticket_resolution.nodes import auto_refund_node, finish_ticket_node, refuse_ticket_node, triage_refund_node, triage_ticket_node
from agents.ticket_resolution.agents.attendant.agent import attendant_agent
from agents.ticket_resolution.agents.refund_investigator.agent import refund_investigator_agent

root_agent = Workflow(
    name="ticket_resolution",
    description="descricao do agente",
    edges=[
        (START, triage_ticket_node, {
            "refuse": refuse_ticket_node,
            "attendant": attendant_agent,
            "refund_investigator": refund_investigator_agent,
        }),
        (attendant_agent, finish_ticket_node),
        (refund_investigator_agent, triage_refund_node, {
            "auto_refund": auto_refund_node
        }),
    ]
)

# msg -> direta
