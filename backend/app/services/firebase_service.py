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


def save_pipeline_run(output_data: dict, input_data: dict = None, user_id: str = "", cost: float = 0.0) -> str:
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

        data_to_save = {
            "input_data": input_data or {},
            "output_data": output_data,
            "user_id": user_id,
            "origin_port": origin,
            "destination_port": destination,
            "cost": cost,
            "timestamp": datetime.utcnow(),
        }
        
        logger.info(f"Saving pipeline run: doc_id={doc_id}, user_id={user_id}, cost={cost}, origin={origin} → {destination}")
        doc_ref.set(data_to_save)
        logger.info(f"Successfully saved pipeline run {doc_id}")
        return doc_id

    except Exception as e:
        logger.error(f"Failed to save pipeline run to Firebase: {e}")
        return ""



def get_recent_runs(user_id: str = "", limit: int = 10) -> List[dict]:
    """
    Fetches the most recent pipeline runs from Firestore.
    If user_id provided, filters to that user; otherwise returns all recent runs.
    Returns empty list if no data is available.
    """
    if db is None:
        logger.warning("Firebase not initialized. Cannot fetch history.")
        return []

    try:
        col = db.collection("pipeline_runs")
        logger.info(f"Querying pipeline_runs collection. user_id={user_id if user_id else 'ALL'}, limit={limit}")

        if user_id:
            logger.info(f"Building user-filtered query for user_id: {user_id}")
            query = (
                col.where("user_id", "==", user_id)
                   .order_by("timestamp", direction=firestore.Query.DESCENDING)
                   .limit(limit)
            )
        else:
            logger.info("Building query for all users (no user_id filter)")
            query = (
                col.order_by("timestamp", direction=firestore.Query.DESCENDING)
                   .limit(limit)
            )

        docs = list(query.stream())
        logger.info(f"Query returned {len(docs)} documents")
        
        results = []
        for i, doc in enumerate(docs):
            d = doc.to_dict()
            ts = d.get("timestamp")
            doc_user_id = d.get("user_id", "NO_USER_ID")
            doc_cost = d.get("cost", 0.0)
            logger.info(f"  Doc {i+1}: id={doc.id}, user_id={doc_user_id}, cost={doc_cost}, timestamp={ts}")
            
            results.append({
                "id": doc.id,
                "origin_port": d.get("origin_port", "—"),
                "destination_port": d.get("destination_port", "—"),
                "timestamp": ts.isoformat() if ts else "",
                "risk_level": (d.get("output_data") or {}).get("prediction", {}).get("risk_level", "—"),
                "congestion_probability": (d.get("output_data") or {}).get("prediction", {}).get("congestion_probability", 0),
                "cost": d.get("cost", 0.0),
                "input_data": d.get("input_data", {}),
            })
        
        logger.info(f"Returning {len(results)} records")
        return results

    except Exception as e:
        logger.error(f"Failed to fetch pipeline history: {e}", exc_info=True)
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