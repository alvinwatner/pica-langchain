"""Simple Firestore service for tracking agent actions in real-time."""
import json
import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_client import BaseClient

logger = logging.getLogger(__name__)


class FirestoreService:
    """Simple singleton service for Firestore connections"""

    _instance = None
    _initialized = False
    db = None

    def __new__(cls, firebase_creds_json: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super(FirestoreService, cls).__new__(cls)
        return cls._instance

    def _initialize(self, firebase_creds_json: Optional[str] = None):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                cred = self._get_firebase_credentials(firebase_creds_json)
                
                if cred:
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase initialized with custom credentials")
                else:
                    firebase_admin.initialize_app()
                    logger.info("Firebase initialized with default credentials")
            else:
                logger.info("Using existing Firebase app")

            # Get the Firestore client
            self.db = firestore.client()
            self._initialized = True
            logger.info("Simple Firestore Service initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Simple Firestore Service: {str(e)}")
            self._initialized = False
            raise

    def _get_firebase_credentials(self, firebase_creds_json: Optional[str] = None):
        """Get Firebase credentials from parameter, environment variables, or file"""
        
        # First try the passed parameter
        if firebase_creds_json:
            try:
                if firebase_creds_json.startswith("{"):
                    # It's a JSON string
                    creds_dict = json.loads(firebase_creds_json)
                    logger.info("Using Firebase credentials from provided JSON parameter")
                    return credentials.Certificate(creds_dict)
                else:
                    # It's a file path
                    if os.path.exists(firebase_creds_json):
                        logger.info(f"Using Firebase credentials from provided file: {firebase_creds_json}")
                        return credentials.Certificate(firebase_creds_json)
            except Exception as e:
                logger.error(f"Failed to parse provided Firebase credentials: {str(e)}")

        # Then try environment variable
        firebase_creds_env = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if firebase_creds_env:
            try:
                if firebase_creds_env.startswith("{"):
                    creds_dict = json.loads(firebase_creds_env)
                    logger.info("Using Firebase credentials from environment variable")
                    return credentials.Certificate(creds_dict)
                else:
                    if os.path.exists(firebase_creds_env):
                        logger.info(f"Using Firebase credentials from environment file: {firebase_creds_env}")
                        return credentials.Certificate(firebase_creds_env)
            except Exception as e:
                logger.error(f"Failed to parse Firebase credentials from environment: {str(e)}")

        # Fallback to default file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        service_account_path = os.path.join(base_dir, "firebase-credentials.json")
        
        if os.path.exists(service_account_path):
            logger.info(f"Using Firebase credentials from default file: {service_account_path}")
            return credentials.Certificate(service_account_path)

        logger.warning("No Firebase credentials found. Using application default credentials.")
        return None

    def get_db(self, firebase_creds_json: Optional[str] = None) -> Optional[BaseClient]:
        """Get the Firestore client"""
        if not self._initialized:
            self._initialize(firebase_creds_json)
        return self.db