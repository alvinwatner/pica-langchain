import logging
from typing import Optional, List
from datetime import datetime

from firebase_admin import firestore
from google.cloud.firestore_v1.base_client import BaseClient
from .firestore_service import FirestoreService

logger = logging.getLogger(__name__)


class ActionTrackingService:
    """Simple service for tracking agent actions in Firestore."""

    def __init__(
        self, firestore_service: FirestoreService, user_id: str = "default"
    ):
        """Initialize the action tracking service.

        Args:
            firestore_service: The Firestore service instance
            user_id: User identifier for the document (defaults to "default")
        """
        self.firestore_service = firestore_service
        self.collection_name = "agent_actions"
        self.user_id = user_id

    def _get_db(self) -> Optional[BaseClient]:
        """Get the Firestore client"""
        db = self.firestore_service.get_db()
        if not db:
            logger.error(
                "Failed to get Firestore client - Firebase may not be initialized properly"
            )
        return db

    async def update_action(
        self, action: str, platform: str, session_id: Optional[str] = None
    ) -> bool:
        """Update the current action and add to history.

        Args:
            action: The action description to track
            platform: The platform the action belongs to
            session_id: Optional session identifier (defaults to user_id)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db = self._get_db()
            if not db:
                return False

            # Use session_id if provided, otherwise use user_id
            doc_id = session_id or self.user_id
            doc_ref = db.collection(self.collection_name).document(doc_id)

            # Create action entry with timestamp
            action_entry = {
                "action": action,
                "platform": platform,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Get current document
            doc = doc_ref.get()

            if doc.exists:
                # Document exists, update it
                doc_ref.update(
                    {
                        "current_action": action,
                        "current_platform": platform,
                        "history": firestore.ArrayUnion([action_entry]),
                        "last_updated": firestore.SERVER_TIMESTAMP,
                    }
                )
            else:
                # Document doesn't exist, create it
                doc_ref.set(
                    {
                        "current_action": action,
                        "current_platform": platform,
                        "history": [action_entry],
                        "created_at": firestore.SERVER_TIMESTAMP,
                        "last_updated": firestore.SERVER_TIMESTAMP,
                    }
                )

            logger.debug(f"Updated action tracking for {doc_id}: {action}")
            return True

        except Exception as e:
            logger.error(f"Error updating action tracking: {str(e)}")
            return False

    async def clear_current_action(self, session_id: Optional[str] = None) -> bool:
        """Clear the current action (set to None).

        Args:
            session_id: Optional session identifier (defaults to user_id)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db = self._get_db()
            if not db:
                return False

            doc_id = session_id or self.user_id
            doc_ref = db.collection(self.collection_name).document(doc_id)

            doc_ref.update(
                {"current_action": None, "last_updated": firestore.SERVER_TIMESTAMP}
            )

            logger.debug(f"Cleared current action for {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Error clearing current action: {str(e)}")
            return False

    async def cleanup_action_tracking(self, session_id: Optional[str] = None) -> bool:
        """Delete the action tracking document for a user/session.

        This is useful to call after a stream completes to clean up the tracking data
        and prepare for the next conversation.

        Args:
            session_id: Optional session identifier (defaults to user_id)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db = self._get_db()
            if not db:
                return False

            doc_id = session_id or self.user_id
            doc_ref = db.collection(self.collection_name).document(doc_id)

            # Check if document exists before trying to delete
            doc = doc_ref.get()
            if doc.exists:
                doc_ref.delete()
                logger.info(f"Successfully deleted action tracking document for {doc_id}")
                return True
            else:
                logger.debug(f"Action tracking document for {doc_id} does not exist, nothing to delete")
                return True

        except Exception as e:
            logger.error(f"Error deleting action tracking document: {str(e)}")
            return False            

    async def get_action_history(
        self, session_id: Optional[str] = None, limit: int = 50
    ) -> List[dict]:
        """Get the action history for a user/session.

        Args:
            session_id: Optional session identifier (defaults to user_id)
            limit: Maximum number of history entries to return

        Returns:
            List of action history entries
        """
        try:
            db = self._get_db()
            if not db:
                return []

            doc_id = session_id or self.user_id
            doc_ref = db.collection(self.collection_name).document(doc_id)

            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                history = data.get("history", [])
                # Return the last 'limit' entries
                return history[-limit:] if len(history) > limit else history
            else:
                return []

        except Exception as e:
            logger.error(f"Error getting action history: {str(e)}")
            return []


def initialize_firestore_service(
    firebase_creds_json: Optional[str] = None,
    user_id: Optional[str] = None,
) -> ActionTrackingService:
    """Initialize and return an ActionTrackingService instance.

    Args:
        firebase_creds_json: Optional Firebase credentials JSON string or file path

    Returns:
        ActionTrackingService instance
    """
    try:
        # Create the simple Firestore service
        firestore_service = FirestoreService(firebase_creds_json)

        # Create and return the action tracking service
        action_service = ActionTrackingService(firestore_service, user_id=user_id)

        logger.info("Action tracking service initialized successfully")
        return action_service

    except Exception as e:
        logger.error(f"Failed to initialize action tracking service: {str(e)}")
        # Return a dummy service that logs but doesn't fail
        return DummyActionTrackingService()


class DummyActionTrackingService:
    """Dummy service for when Firestore isn't available."""

    async def update_action(
        self, action: str, session_id: Optional[str] = None
    ) -> bool:
        logger.debug(f"Dummy action tracking: {action}")
        return True

    async def clear_current_action(self, session_id: Optional[str] = None) -> bool:
        logger.debug("Dummy action tracking: cleared current action")
        return True

    async def get_action_history(
        self, session_id: Optional[str] = None, limit: int = 50
    ) -> List[dict]:
        return []
