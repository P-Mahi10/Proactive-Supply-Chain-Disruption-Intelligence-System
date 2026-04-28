import json
import os
import uuid
from typing import Dict, List, Union
from pathlib import Path
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize Firebase
backend_dir = Path(__file__).resolve().parent.parent.parent
env_service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
env_service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

candidate_paths = []
if env_service_account_path:
    candidate_paths.append(Path(env_service_account_path))
candidate_paths.append(Path("/etc/secrets/serviceAccountKey.json"))
candidate_paths.append(backend_dir / "serviceAccountKey.json")
candidate_paths.append(backend_dir.parent / "serviceAccountKey.json")

service_account_path = next((path for path in candidate_paths if path.exists()), None)

db = None

try:
    if env_service_account_json:
        service_account_info = json.loads(env_service_account_json)
        cred = credentials.Certificate(service_account_info)
        logger.info("Using Firebase credentials from FIREBASE_SERVICE_ACCOUNT_JSON.")
    elif service_account_path is not None:
        logger.info(f"Using Firebase credentials from: {service_account_path}")
        cred = credentials.Certificate(str(service_account_path))
    else:
        cred = None

    if cred is not None:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Firebase initialized successfully.")
    else:
        logger.warning("Firebase credentials not found. Input saving will be skipped.")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")


def save_pipeline_run(output_data: dict, input_data: dict = None, user_id: str = "") -> str:
    """
    Saves the full pipeline run (inputs + outputs) to Firebase Firestore.
    Returns the document ID.
    """
    if db is None:
        logger.warning("Firebase is not initialized. Skipping save.")
        return ""

    try:
        doc_id = str(uuid.uuid4())
        doc_ref = db.collection("pipeline_runs").document(doc_id)

        origin = (input_data or {}).get("origin_port", "Unknown")
        destination = (input_data or {}).get("destination_port", "Unknown")

        doc_ref.set({
            "input_data": input_data or {},
            "output_data": output_data,
            "user_id": user_id,
            "origin_port": origin,
            "destination_port": destination,
            "timestamp": datetime.utcnow(),
        })

        logger.info(f"Saved pipeline run {doc_id} ({origin} → {destination})")
        return doc_id

    except Exception as e:
        logger.error(f"Failed to save pipeline run to Firebase: {e}")
        return ""


def get_recent_runs(user_id: str = "", limit: int = 10) -> List[dict]:
    """
    Fetches the most recent pipeline runs from Firestore.
    If user_id provided, filters to that user; otherwise returns all recent runs.
    """
    if db is None:
        logger.warning("Firebase not initialized. Cannot fetch history.")
        return []

    try:
        col = db.collection("pipeline_runs")

        if user_id:
            query = (
                col.where("user_id", "==", user_id)
                   .order_by("timestamp", direction=firestore.Query.DESCENDING)
                   .limit(limit)
            )
        else:
            query = (
                col.order_by("timestamp", direction=firestore.Query.DESCENDING)
                   .limit(limit)
            )

        docs = query.stream()
        results = []
        for doc in docs:
            d = doc.to_dict()
            ts = d.get("timestamp")
            results.append({
                "id": doc.id,
                "origin_port": d.get("origin_port", "—"),
                "destination_port": d.get("destination_port", "—"),
                "timestamp": ts.isoformat() if ts else "",
                "risk_level": (d.get("output_data") or {}).get("prediction", {}).get("risk_level", "—"),
                "congestion_probability": (d.get("output_data") or {}).get("prediction", {}).get("congestion_probability", 0),
                "input_data": d.get("input_data", {}),
            })
        return results

    except Exception as e:
        logger.error(f"Failed to fetch pipeline history: {e}")
        return []


def save_chat_message(conversation_id: str, message: Dict[str, Union[str, int, float, bool, dict, list]]) -> bool:
    if db is None:
        logger.warning("Firebase is not initialized. Skipping chat save.")
        return False

    try:
        db.collection("ai_conversations").document(conversation_id).collection("messages").add(message)
        return True
    except Exception as e:
        logger.error(f"Failed to save chat message to Firebase: {e}")
        return False