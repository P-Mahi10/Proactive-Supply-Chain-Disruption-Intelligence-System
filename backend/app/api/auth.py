import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth

from app.utils.logger import get_logger

logger = get_logger(__name__)

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify the Firebase ID Token.
    Returns the decoded token (which includes user info) if valid,
    raises HTTP 401 Unauthorized otherwise.

    If SKIP_AUTH environment variable is set to 'true', it bypasses verification
    and returns a mock user.
    """
    if os.environ.get("SKIP_AUTH", "false").lower() == "true":
        logger.info("Bypassing Firebase token verification (SKIP_AUTH=true).")
        return {"uid": "test_user_123", "email": "test@example.com"}

    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.error(f"Error verifying Firebase ID token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
