import API_BASE_URL from "./api.js";

document.addEventListener("DOMContentLoaded", () => {
  // ─── View Switching ───────────────────────────────────────────────────────────
  const navBtns = document.querySelectorAll(".nav-btn");
  const viewPanes = document.querySelectorAll(".view-pane");

  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.view;
      navBtns.forEach((b) => b.classList.remove("active"));
      viewPanes.forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(target).classList.add("active");

      if (target === "history-view") fetchHistory();
      if (target === "dashboard-view") {
        if (historyData.length === 0) {
          fetchHistory();
        } else {
          updateDashboard();
        }
      }
    });
  });

  // ─── Tab Switching ───────────────────────────────────────────────────────────
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabPanes.forEach((p) => p.classList.add("hidden"));
      btn.classList.add("active");
      document.getElementById(target).classList.remove("hidden");
    });
  });

  // ─── Fetch Weather Data ───────────────────────────────────────────────────
  const fetchWeatherBtn = document.getElementById("fetch-weather-btn");
  if (fetchWeatherBtn) {
    fetchWeatherBtn.addEventListener("click", async () => {
      // Get values from Route tab
      const originPort = document.getElementById("origin_port").value;
      const destinationPort = document.getElementById("destination_port").value;
      const season = document.getElementById("season").value;

      // Get values from Temporal tab
      const month = document.getElementById("month").value;
      const dayOfWeek = document.getElementById("day_of_week").value;

      if (!originPort || !destinationPort) {
        showToast("Please select origin and destination ports first", "error");
        return;
      }

      fetchWeatherBtn.disabled = true;
      fetchWeatherBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Fetching...';

      try {
        const response = await fetch(`${API_BASE_URL}/fetch_weather`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            input_data: {
              origin_port: originPort,
              destination_port: destinationPort,
              season: season,
              month: parseInt(month),
              day_of_week: parseInt(dayOfWeek),
            },
          }),
        });

        if (!response.ok) {
          throw new Error("Failed to fetch weather data");
        }

        const weatherData = await response.json();

        // Populate weather fields with fetched data
        document.getElementById("weather_forecast_severity").value =
          weatherData.weather_forecast_severity;
        document.getElementById("cyclone_probability").value =
          weatherData.cyclone_probability;
        document.getElementById("wind_speed_kmh").value =
          weatherData.wind_speed_kmh;
        document.getElementById("wave_height_m").value = weatherData.wave_height_m;
        document.getElementById("rainfall_mm").value = weatherData.rainfall_mm;
        document.getElementById("visibility_km").value = weatherData.visibility_km;

        showToast("Weather data fetched successfully");
      } catch (error) {
        console.error(error);
        showToast("Error fetching weather data: " + error.message, "error");
      } finally {
        fetchWeatherBtn.disabled = false;
        fetchWeatherBtn.innerHTML =
          '<i class="fa-solid fa-cloud"></i> Fetch Weather Data';
      }
    });
  }

  // ─── CSV Upload & Auto-fill ───────────────────────────────────────────────────
  const csvUploadInput = document.getElementById("csv-upload");
  const CSV_FIELD_MAP = {
    origin_port: "origin_port",
    destination_port: "destination_port",
    portcalls: "portcalls",
    cargo_volume_teu: "cargo_volume_teu",
    total_trade_usd: "total_trade_usd",
    portcalls_container: "portcalls_container",
    portcalls_dry_bulk: "portcalls_dry_bulk",
    portcalls_tanker: "portcalls_tanker",
    portcalls_general_cargo: "portcalls_general_cargo",
    import_container: "import_container",
    export_container: "export_container",
    berth_occupancy_rate: "berth_occupancy_rate",
    vessels_in_queue: "vessels_in_queue",
    historical_disruption_rate: "historical_disruption_rate",
    days_since_last_disruption: "days_since_last_disruption",
    active_disruptions_nearby: "active_disruptions_nearby",
    disruption_flag: "disruption_flag",
    weather_forecast_severity: "weather_forecast_severity",
    cyclone_probability: "cyclone_probability",
    wind_speed_kmh: "wind_speed_kmh",
    wave_height_m: "wave_height_m",
    rainfall_mm: "rainfall_mm",
    visibility_km: "visibility_km",
    month: "month",
    day_of_week: "day_of_week",
    trend_calls: "trend_calls",
    trend_cargo: "trend_cargo",
    portcalls_lag1: "portcalls_lag1",
    portcalls_lag2: "portcalls_lag2",
    portcalls_lag3: "portcalls_lag3",
    portcalls_lag4: "portcalls_lag4",
    portcalls_lag5: "portcalls_lag5",
    portcalls_lag6: "portcalls_lag6",
    portcalls_lag7: "portcalls_lag7",
    cargo_lag1: "cargo_lag1",
    cargo_lag2: "cargo_lag2",
    cargo_lag3: "cargo_lag3",
    cargo_lag4: "cargo_lag4",
    cargo_lag5: "cargo_lag5",
    cargo_lag6: "cargo_lag6",
    cargo_lag7: "cargo_lag7",
    rainfall_lag1: "rainfall_lag1",
    rainfall_lag2: "rainfall_lag2",
    rainfall_lag3: "rainfall_lag3",
    rainfall_lag4: "rainfall_lag4",
    rainfall_lag5: "rainfall_lag5",
    rainfall_lag6: "rainfall_lag6",
    rainfall_lag7: "rainfall_lag7",
  };

  csvUploadInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      const lines = evt.target.result
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l);
      if (lines.length < 2) return showToast("Invalid CSV format", "error");
      const headers = lines[0].split(",");
      const data = lines[1].split(",");
      headers.forEach((h, i) => {
        const id = CSV_FIELD_MAP[h.trim()];
        if (id && document.getElementById(id)) {
          document.getElementById(id).value = data[i].trim();
        }
      });
      showToast("Data auto-filled from CSV");
    };
    reader.readAsText(file);
  });

  // ─── Sample CSV Download ─────────────────────────────────────────────────────
  document
    .getElementById("download-sample-csv")
    .addEventListener("click", () => {
      const headers = Object.keys(CSV_FIELD_MAP).join(",");
      const sampleData = [
        "Singapore",
        "Shanghai (Pudong)",
        "150",
        "12000",
        "5000000",
        "80",
        "30",
        "20",
        "20",
        "6000",
        "5500",
        "0.75",
        "5",
        "0.05",
        "45",
        "0",
        "0",
        "1",
        "0.01",
        "15",
        "1.2",
        "2",
        "10",
        "4",
        "2",
        "0.5",
        "0.8",
        "145",
        "140",
        "155",
        "150",
        "148",
        "152",
        "147",
        "11500",
        "11800",
        "12200",
        "12000",
        "11900",
        "12100",
        "11700",
        "1.5",
        "2.0",
        "0.5",
        "1.2",
        "3.0",
        "0.0",
        "2.5",
      ].join(",");
      const csvContent =
        "data:text/csv;charset=utf-8," + headers + "\n" + sampleData;
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", "sample_supply_chain_data.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    });

  // ─── History Logic ───────────────────────────────────────────────────────────
  // Hits FastAPI backend — handles DB/Firebase routes
  let historyData = [];
  async function fetchHistory() {
    try {
      const response = await fetch(`${API_BASE_URL}/history`);
      if (!response.ok) {
        const body = await response.text().catch(() => "<no body>");
        console.error("History fetch failed", {
          status: response.status,
          body,
        });
        throw new Error(`Failed to fetch history: HTTP ${response.status}`);
      }
      historyData = await response.json();
      renderHistoryList();
      updateDashboard();
    } catch (err) {
      console.error(err);
      showToast("Error loading history", "error");
    }
  }

  function renderHistoryList() {
    const body = document.getElementById("history-list-body");
    body.innerHTML = historyData
      .map(
        (run) => `
      <tr>
        <td>${new Date(run.timestamp).toLocaleString()}</td>
        <td>${run.origin_port}</td>
        <td>${run.destination_port}</td>
        <td><span class="badge ${run.risk_level.toLowerCase()}">${run.risk_level}</span></td>
        <td>${(run.congestion_probability * 100).toFixed(1)}%</td>
        <td><button class="load-run-btn" data-id="${run.id}">Load</button></td>
      </tr>
    `,
      )
      .join("");

    body.querySelectorAll(".load-run-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const run = historyData.find((r) => r.id === btn.dataset.id);
        if (run) loadRunData(run);
      });
    });
  }

  function loadRunData(run) {
    Object.entries(run.input_data).forEach(([key, val]) => {
      const el = document.getElementById(key);
      if (el) el.value = val;
    });
    document.querySelector('[data-view="analyze-view"]').click();
    showToast("Historical data loaded into form");
  }

  document
    .getElementById("refresh-history-btn")
    .addEventListener("click", fetchHistory);

  // ─── Dashboard Logic ─────────────────────────────────────────────────────────
  let riskChart, trendChart;
  function updateDashboard() {
    if (historyData.length === 0) return;

    // Update Stats
    document.getElementById("total-runs-stat").textContent = historyData.length;
    const highRiskCount = historyData.filter(
      (r) => r.risk_level === "HIGH",
    ).length;
    document.getElementById("high-risk-rate-stat").textContent =
      ((highRiskCount / historyData.length) * 100).toFixed(1) + "%";
    const avgCong =
      historyData.reduce((acc, r) => acc + r.congestion_probability, 0) /
      historyData.length;
    document.getElementById("avg-congestion-stat").textContent =
      (avgCong * 100).toFixed(1) + "%";

    // Risk Distribution Chart
    const riskCounts = { HIGH: 0, MEDIUM: 0, LOW: 0 };
    historyData.forEach((r) => riskCounts[r.risk_level]++);

    if (riskChart) riskChart.destroy();
    riskChart = new Chart(document.getElementById("risk-dist-chart"), {
      type: "doughnut",
      data: {
        labels: ["High", "Medium", "Low"],
        datasets: [
          {
            data: [riskCounts.HIGH, riskCounts.MEDIUM, riskCounts.LOW],
            backgroundColor: ["#dc2626", "#d97706", "#16a34a"],
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    // Trend Chart
    const trendData = [...historyData].reverse().slice(-10);
    if (trendChart) trendChart.destroy();
    trendChart = new Chart(document.getElementById("congestion-trend-chart"), {
      type: "line",
      data: {
        labels: trendData.map((r) =>
          new Date(r.timestamp).toLocaleTimeString(),
        ),
        datasets: [
          {
            label: "Congestion Prob",
            data: trendData.map((r) => r.congestion_probability),
            borderColor: "#0284c7",
            tension: 0.3,
            fill: true,
            backgroundColor: "rgba(2, 132, 199, 0.1)",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0, max: 1 } },
      },
    });
  }

  // ─── Form Submission ──────────────────────────────────────────────────────────
  // Hits Python FastAPI backend (port 8000) — handles ML pipeline
  const form = document.getElementById("pipeline-form");
  const loadingState = document.getElementById("loading-spinner");
  const advisoryCard = document.getElementById("advisory-card");
  const predictionCard = document.getElementById("prediction-card");
  const simulationCard = document.getElementById("simulation-card");
  const recommendationCard = document.getElementById("recommendation-card");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    [advisoryCard, predictionCard, simulationCard, recommendationCard].forEach(
      (c) => c.classList.add("hidden"),
    );
    loadingState.classList.remove("hidden");

    // Fields that must remain as strings (not coerced to numbers)
    const STRING_FIELDS = new Set(["origin_port", "destination_port"]);

    const inputData = {};
    Object.values(CSV_FIELD_MAP).forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (el.tagName === "SELECT" || STRING_FIELDS.has(id)) {
        inputData[id] = el.value;
      } else {
        const parsed = parseFloat(el.value);
        inputData[id] = isNaN(parsed) ? 0 : parsed;
      }
    });

    // Extra fields not in CSV map but in form
    inputData.cargo_type = document.getElementById("cargo_type").value;
    inputData.season = document.getElementById("season").value;

    try {
      const response = await fetch(`${API_BASE_URL}/run_pipeline`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ input_data: inputData }),
      });

      if (!response.ok) throw new Error("Pipeline run failed");
      const data = await response.json();
      loadingState.classList.add("hidden");

      renderPrediction(data.prediction);
      if (data.simulation) renderSimulation(data.simulation);
      if (data.advisory) renderAdvisory(data.advisory);
      if (data.recommendation) renderRecommendations(data.recommendation);

      showToast("Intelligence analysis complete");
      fetchHistory(); // Refresh history in background
    } catch (error) {
      console.error(error);
      showToast(error.message, "error");
      loadingState.classList.add("hidden");
    }
  });

  function renderAdvisory(text) {
    advisoryCard.classList.remove("hidden");
    document.getElementById("advisory-text").textContent = text;
  }

  function renderPrediction(pred) {
    predictionCard.classList.remove("hidden");
    const badge = document.getElementById("risk-badge");
    badge.textContent = pred.risk_level;
    badge.className = `badge ${pred.risk_level.toLowerCase()}`;
    const probPct = (pred.congestion_probability * 100).toFixed(1);
    document.getElementById("prob-val").textContent = `${probPct}%`;
    document.getElementById("occ-val").textContent =
      `${(pred.predicted_berth_occupancy_t_plus_2 * 100).toFixed(1)}%`;
    setTimeout(() => {
      document.getElementById("prob-bar").style.width = `${probPct}%`;
    }, 100);
  }

  function renderSimulation(sim) {
    simulationCard.classList.remove("hidden");
    const congBadge = document.getElementById("congestion-badge");
    congBadge.textContent = sim.congestion_level;
    congBadge.className = `badge ${sim.congestion_level.toLowerCase()}`;
    document.getElementById("sim-route-label").textContent =
      `${sim.origin_port} → ${sim.destination_port}`;
    document.getElementById("delay-val").textContent =
      `${sim.estimated_delay_hours.toFixed(1)} hrs`;
    document.getElementById("delay-p90-val").textContent =
      `${sim.delay_p90.toFixed(1)} hrs`;
    document.getElementById("disruption-prob-val").textContent =
      `${(sim.prob_disruption * 100).toFixed(1)}%`;
    document.getElementById("sla-breach-val").textContent =
      `${(sim.prob_missed_sla * 100).toFixed(1)}%`;

    if (sim.recommended_route) {
      document.getElementById("recommended-route-block").style.display = "flex";
      document.getElementById("recommended-route-text").textContent =
        sim.recommended_route;
    }
  }

  function renderRecommendations(recs) {
    recommendationCard.classList.remove("hidden");
    const container = document.getElementById("routes-container");
    container.innerHTML = recs
      .map(
        (rec) => `
      <div class="route-item">
        <div class="route-item-main">
          <div class="route-name">${rec.route}</div>
          <div class="route-reason">${rec.reason}</div>
        </div>
        <div class="route-metrics">
          <span>Cost: <strong>$${rec.cost.toLocaleString()}</strong></span>
          <span>Delay Factor: <strong>${rec.delay_factor.toFixed(2)}</strong></span>
        </div>
      </div>
    `,
      )
      .join("");
  }

  function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.style.cssText = `position: fixed; bottom: 2rem; right: 2rem; background: ${type === "error" ? "#dc2626" : "#16a34a"}; color: white; padding: 1rem 2rem; border-radius: 12px; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.1);`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  fetchHistory();
});
