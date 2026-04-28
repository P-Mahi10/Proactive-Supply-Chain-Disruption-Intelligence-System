# Proactive Supply Chain Disruption Intelligence System

Predict. Simulate. Optimize.

An AI-powered decision support system designed to anticipate and mitigate supply chain disruptions at the port level through predictive analytics, simulation, and intelligent recommendations.

## Overview

Global supply chains are increasingly vulnerable to disruptions caused by weather, congestion, and operational inefficiencies. Most existing systems are reactive, responding only after issues arise.

This project introduces a proactive intelligence pipeline that:

- Predicts congestion risk in advance
- Simulates operational impact
- Recommends optimal routing decisions

## Key Features

### Disruption Risk Prediction
Forecasts congestion probability and risk levels using ML models.

### T+2 Forecasting
Predicts future congestion and berth occupancy.

### Simulation Engine
Estimates delay, queue size, and operational impact.

### Adaptive Triggering Logic
Runs simulation only when risk crosses a threshold.

### Route Recommendation System
Suggests optimal routes based on cost, delay, and risk.

### End-to-End Pipeline
Integrated flow: Prediction -> Simulation -> Recommendation.

## System Architecture

User (Frontend)
			|
			v
Frontend (Vercel)
			|
			v
Backend API (FastAPI - Render)
			|
			v
Intelligence Layer
	- Prediction Model (XGBoost)
	- Simulation Engine (SimPy)
	- Solution Engine (Gemma AI)
			|
			v
Data Layer (PostgreSQL / Firebase)
			|
			v
External AI (Google Gemma via OpenRouter)

## Process Flow

User Input
		|
		v
Prediction Model
		|
		v
Risk Evaluation (Threshold)
	 |            |
	 v            v
Low Risk     High Risk
	 |            |
	 v            v
Output     Simulation Engine
								|
								v
				 Solution Engine
								|
								v
						Final Output

## Tech Stack

### Backend and APIs
- FastAPI (Python)
- Node.js (Express)

### AI and Analytics
- XGBoost
- scikit-learn
- NumPy, Pandas

### Simulation
- SimPy

### Data Layer
- PostgreSQL
- Firebase (Auth and storage)

### Frontend
- HTML, CSS, JavaScript

### Infrastructure
- Docker and Docker Compose
- Nginx (Reverse Proxy)
- Vercel (Frontend Hosting)
- Render (Backend Deployment)

## Google Technologies Used

- Firebase: authentication and real-time data storage
- Gemma (Google AI): intelligent recommendations and solution generation

## Deployment

- Frontend: Vercel
- Backend: Render (Dockerized FastAPI service)
- Database: PostgreSQL
- Auth and Data: Firebase

## API Endpoints

| Endpoint | Description |
| --- | --- |
| /run_pipeline | Full pipeline (prediction + simulation + recommendation) |
| /predict | Congestion prediction |
| /simulate | Delay and impact simulation |
| /recommend | Route recommendations |

## Example Output

```json
{
	"prediction": {
		"congestion_probability": 0.92,
		"risk_level": "HIGH"
	},
	"simulation": {
		"estimated_delay_hours": 12.5,
		"queue_size": 8
	},
	"recommendation": [
		{
			"route": "Route B",
			"cost": 1200,
			"delay_factor": 6.2
		}
	]
}
```

## Use Cases

- Logistics planning and optimization
- Port authority decision support
- Supply chain risk management
- Real-time disruption analysis

## Future Enhancements

- Real-time data integration (weather, vessel tracking)
- Multi-port global network simulation
- Advanced time-series and deep learning models
- Scenario-based "what-if" analysis dashboard
- Full SaaS deployment
