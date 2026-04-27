document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('pipeline-form');
    const loadingState = document.getElementById('loading-spinner');
    
    // Cards
    const predictionCard = document.getElementById('prediction-card');
    const simulationCard = document.getElementById('simulation-card');
    const recommendationCard = document.getElementById('recommendation-card');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Hide cards, show loading
        predictionCard.classList.add('hidden');
        simulationCard.classList.add('hidden');
        recommendationCard.classList.add('hidden');
        loadingState.classList.remove('hidden');

        // Gather form data
        const formData = new FormData(form);
        const inputData = {};
        for (let [key, value] of formData.entries()) {
            const floatVal = parseFloat(value);
            inputData[key] = isNaN(floatVal) ? value : floatVal;
        }

        // Add some required mock fields that the model might expect but aren't in the form
        const payload = {
            input_data: {
                ...inputData,
                month: 11,
                day_of_week: 6,
                total_trade_usd: 435498,
                rolling_avg_calls_28d: 60,
                rolling_avg_container_28d: 300000,
                berth_occupancy_rate: 0.0,
                vessels_in_queue: 0,
                cyclone_probability: 0.05,
                wave_height_m: 0.0,
                visibility_km: 9.29,
                historical_disruption_rate: 0.0,
                days_since_last_disruption: -1,
                active_disruptions_nearby: 0
            }
        };

        try {
            const headers = {
                'Content-Type': 'application/json'
            };
            
            if (window.firebaseAuthToken) {
                headers['Authorization'] = `Bearer ${window.firebaseAuthToken}`;
            }
            
            const response = await fetch('http://localhost:8000/run_pipeline', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const data = await response.json();
            
            // Hide loading
            loadingState.classList.add('hidden');

            // Render Prediction
            renderPrediction(data.prediction);
            
            // Render Simulation
            if (data.simulation) {
                renderSimulation(data.simulation);
            }
            
            // Render Recommendations
            if (data.recommendation && data.recommendation.length > 0) {
                renderRecommendations(data.recommendation);
            }

        } catch (error) {
            console.error(error);
            alert("Failed to connect to the backend API. Ensure the FastAPI server is running on port 8000.");
            loadingState.classList.add('hidden');
        }
    });

    function renderPrediction(pred) {
        predictionCard.classList.remove('hidden');
        
        // Badge
        const badge = document.getElementById('risk-badge');
        badge.textContent = pred.risk_level;
        badge.className = `badge ${pred.risk_level.toLowerCase()}`;
        
        // Values
        const probPct = (pred.congestion_probability * 100).toFixed(1);
        const occPct = (pred.predicted_berth_occupancy_t_plus_2 * 100).toFixed(1);
        
        document.getElementById('prob-val').textContent = `${probPct}%`;
        document.getElementById('occ-val').textContent = `${occPct}%`;
        
        // Progress bar
        setTimeout(() => {
            document.getElementById('prob-bar').style.width = `${probPct}%`;
        }, 100);
    }

    function renderSimulation(sim) {
        simulationCard.classList.remove('hidden');
        document.getElementById('delay-val').textContent = `${sim.estimated_delay_hours.toFixed(1)} hrs`;
        document.getElementById('queue-val').textContent = Math.round(sim.queue_size);
    }

    function renderRecommendations(recs) {
        recommendationCard.classList.remove('hidden');
        const container = document.getElementById('routes-container');
        container.innerHTML = ''; // clear

        recs.forEach(rec => {
            const el = document.createElement('div');
            el.className = 'route-item';
            el.innerHTML = `
                <div class="route-name">${rec.route}</div>
                <div class="route-metrics">
                    <span>Cost: <strong>$${rec.cost.toFixed(2)}</strong></span>
                    <span>Est Time: <strong>${rec.delay_factor.toFixed(1)} hrs</strong></span>
                </div>
            `;
            container.appendChild(el);
        });
    }
});
