import express from "express";
import pkg from "pg";
import admin from "firebase-admin";
import fs from "fs";
import path from "path";
import cors from "cors";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

/* PostgreSQL */
const { Pool } = pkg;
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

/* Firebase */
const envServiceAccountPath = process.env.FIREBASE_SERVICE_ACCOUNT_PATH;

const candidatePaths = [
  envServiceAccountPath, // env override
  "/etc/secrets/serviceAccountKey.json", // Render secret
  path.join(process.cwd(), "serviceAccountKey.json"), // local
];

let firestore = null;

try {
  const resolvedPath = candidatePaths.find((p) => p && fs.existsSync(p));

  if (!resolvedPath) {
    throw new Error("No Firebase credentials found");
  }

  console.log("Using Firebase credentials from:", resolvedPath);

  const serviceAccount = JSON.parse(fs.readFileSync(resolvedPath, "utf8"));

  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
  });

  firestore = admin.firestore();
  console.log("Firebase initialized successfully");
} catch (error) {
  console.warn("Firebase credentials not found. Chat saving will be skipped.");
}

/* TEST ROUTE */
app.get("/", (req, res) => {
  res.send("Server running 🚀");
});

/* GET BEST ROUTES */
app.get("/routes", async (req, res) => {
  const result = await pool.query(`
    SELECT r.origin, r.destination, tm.name,
           rm.cost_per_unit, rm.estimated_time_hours
    FROM route_metrics rm
    JOIN route_options ro ON rm.route_option_id = ro.id
    JOIN routes r ON ro.route_id = r.id
    JOIN transport_modes tm ON ro.transport_mode_id = tm.id
    WHERE rm.condition_type = 'current'
    ORDER BY rm.cost_per_unit ASC
    LIMIT 5;
  `);

  res.json(result.rows);
});

/* SAVE CHAT */
app.post("/chat", async (req, res) => {
  const { conversationId, message } = req.body;

  if (!firestore) {
    return res.status(503).send("Firebase not initialized");
  }

  await firestore
    .collection("ai_conversations")
    .doc(conversationId)
    .collection("messages")
    .add(message);

  res.send("Message saved");
});

/* START SERVER (Render compatible) */
const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
