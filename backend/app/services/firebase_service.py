import os
import uuid
from typing import Dict, Union
from pathlib import Path
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize Firebase
backend_dir = Path(__file__).resolve().parent.parent.parent
env_service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
candidate_paths = []

if env_service_account_path:
    candidate_paths.append(Path(env_service_account_path))

candidate_paths.append(Path("/etc/secrets/serviceAccount"))
candidate_paths.append(backend_dir.parent / "serviceAccount")

service_account_path = next((path for path in candidate_paths if path.exists()), None)

db = None

try:
    if service_account_path is not None:
        cred = credentials.Certificate(str(service_account_path))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Firebase initialized successfully.")
    else:
        logger.warning("Firebase credentials not found. Input saving will be skipped.")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")


def save_pipeline_run(output_data: dict) -> str:
    """
    Saves the prediction resulting output to Firebase Firestore.
    Returns the document ID.
    """
    if db is None:
        logger.warning("Firebase is not initialized. Skipping save.")
        return ""

    try:
        doc_ref = db.collection("pipeline_runs").document(str(uuid.uuid4()))
        doc_ref.set({
            "output_data": output_data,
            "timestamp": datetime.utcnow()
        })
        logger.info(f"Successfully saved pipeline run to Firebase with ID: {doc_ref.id}")
        return doc_ref.id
    except Exception as e:
        logger.error(f"Failed to save pipeline run to Firebase: {e}")
        return ""
