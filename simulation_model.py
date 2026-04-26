from simulation_model import SimulationModel, format_for_llm

sim = SimulationModel()
sim.load_calibration("calibration.json")

# risk_scores come directly from your prediction model output
result = sim.run(
    origin_port_id      = "port776",
    destination_port_id = "port1114",
    risk_scores         = prediction_model.predict(features),  # {port_id: 0-1}
    season              = "monsoon",
    n_runs              = 1000,
)

# Pass to LLM with company-specific cost parameters from DB
llm_input = format_for_llm(result, company_context={
    "fuel_rate":          company.fuel_rate,
    "sla_penalty_per_hr": company.sla_penalty,
    "cargo_value_usd":    shipment.cargo_value,
    "deal_discount_pct":  company.discount,
})