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
service_account_path = backend_dir / "serviceAccountKey.json"

db = None

try:
    if service_account_path.exists():
        cred = credentials.Certificate(str(service_account_path))
        if not firebase_admin._apps:
            firebase_admin.initializeApp(cred)
        db = firestore.client()
        logger.info("Firebase initialized successfully.")
    else:
        logger.warning(f"Firebase credentials not found at {service_account_path}. Input saving will be skipped.")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")


def save_pipeline_input(input_data: Dict[str, Union[float, str]]) -> str:
    """
    Saves the prediction input data to Firebase Firestore.
    Returns the document ID.
    """
    if db is None:
        logger.warning("Firebase is not initialized. Skipping save.")
        return ""

    try:
        doc_ref = db.collection("pipeline_inputs").document(str(uuid.uuid4()))
        doc_ref.set({
            "input_data": input_data,
            "timestamp": datetime.utcnow()
        })
        logger.info(f"Successfully saved input data to Firebase with ID: {doc_ref.id}")
        return doc_ref.id
    except Exception as e:
        logger.error(f"Failed to save input data to Firebase: {e}")
        return ""
