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

    async def update_workflow_execution(
        self,
        workflow_id: str,
        current_step_index: int,
        total_steps: int,
        step_status: str,
        overall_status: str,
        status_message: str,
        platform: Optional[str] = None,
    ) -> bool:
        """Update workflow execution status in Firestore.

        This method tracks workflow execution progress for real-time visualization
        on the Flutter canvas. Status updates are written to a separate collection
        from general agent actions.

        Args:
            workflow_id: The ID of the workflow being executed
            current_step_index: Zero-based index of the current step
            total_steps: Total number of steps in the workflow
            step_status: Status of current step ('pending', 'running', 'success', 'failed')
            overall_status: Overall workflow status ('running', 'completed', 'failed')
            status_message: Human-readable status message
            platform: Optional platform name for the current step

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db = self._get_db()
            if not db:
                return False

            # Use user_id as document ID for workflow executions
            doc_ref = db.collection("workflow_executions").document(self.user_id)

            # Create history entry
            history_entry = {
                "step_index": current_step_index,
                "step_status": step_status,
                "status_message": status_message,
                "platform": platform,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Get current document
            doc = doc_ref.get()

            if doc.exists:
                # Document exists, update it
                doc_ref.update(
                    {
                        "workflow_id": workflow_id,
                        "current_step_index": current_step_index,
                        "total_steps": total_steps,
                        "step_status": step_status,
                        "overall_status": overall_status,
                        "status_message": status_message,
                        "current_platform": platform,
                        "history": firestore.ArrayUnion([history_entry]),
                        "last_updated": firestore.SERVER_TIMESTAMP,
                    }
                )
            else:
                # Document doesn't exist, create it
                doc_ref.set(
                    {
                        "workflow_id": workflow_id,
                        "current_step_index": current_step_index,
                        "total_steps": total_steps,
                        "step_status": step_status,
                        "overall_status": overall_status,
                        "status_message": status_message,
                        "current_platform": platform,
                        "history": [history_entry],
                        "created_at": firestore.SERVER_TIMESTAMP,
                        "last_updated": firestore.SERVER_TIMESTAMP,
                    }
                )

            logger.info(
                f"Updated workflow execution for {self.user_id}: "
                f"workflow={workflow_id}, step={current_step_index}/{total_steps}, "
                f"status={step_status}"
            )
            return True

        except Exception as e:
            logger.info(f"Error updating workflow execution: {str(e)}")
            return False

    async def cleanup_workflow_execution(self) -> bool:
        """Delete the workflow execution document for a user.

        This should be called after workflow execution completes to clean up
        the tracking data.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db = self._get_db()
            if not db:
                return False

            doc_ref = db.collection("workflow_executions").document(self.user_id)

            doc = doc_ref.get()
            if doc.exists:
                doc_ref.delete()
                logger.info(
                    f"Successfully deleted workflow execution document for {self.user_id}"
                )
                return True
            else:
                logger.debug(
                    f"Workflow execution document for {self.user_id} does not exist"
                )
                return True

        except Exception as e:
            logger.error(f"Error deleting workflow execution document: {str(e)}")
            return False


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
        self, action: str, platform: str, session_id: Optional[str] = None
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

    async def update_workflow_execution(
        self,
        workflow_id: str,
        current_step_index: int,
        total_steps: int,
        step_status: str,
        overall_status: str,
        status_message: str,
        platform: Optional[str] = None,
    ) -> bool:
        logger.debug(
            f"Dummy workflow execution tracking: "
            f"workflow={workflow_id}, step={current_step_index}/{total_steps}"
        )
        return True

    async def cleanup_workflow_execution(self) -> bool:
        logger.debug("Dummy workflow execution tracking: cleaned up")
        return True
