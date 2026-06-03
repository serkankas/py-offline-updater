"""State management for update engine."""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


logger = logging.getLogger('update_engine')


class StateManager:
    """Manages update state for power failure recovery."""

    def __init__(self, state_file: Path):
        """Initialize state manager.

        Args:
            state_file: Path to state.json file
        """
        self.state_file = state_file
        self.state: Dict[str, Any] = {}

    def load(self) -> Optional[Dict[str, Any]]:
        """Load state from file.

        Returns:
            State dictionary if valid, None otherwise
        """
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            self.state = data
            logger.info(f"Loaded state: {self.state.get('status', 'unknown')}")
            return self.state

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load state file: {e}")
            return None

    def save(self, state: Dict[str, Any]) -> None:
        """Save state to file.

        Args:
            state: State dictionary to save
        """
        state['last_updated'] = datetime.now().isoformat()

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

        self.state = state
        logger.debug(f"State saved: {state.get('status', 'unknown')}")

    def update(self, **kwargs) -> None:
        """Update specific state fields.

        Args:
            **kwargs: Fields to update in state
        """
        self.state.update(kwargs)
        self.save(self.state)

    def clear(self) -> None:
        """Clear state file."""
        if self.state_file.exists():
            self.state_file.unlink()
            logger.info("State file cleared")
        self.state = {}

    def is_update_in_progress(self) -> bool:
        """Check if an update is in progress.

        Returns:
            True if update is in progress
        """
        return self.state.get('status') == 'in_progress'

    def get_current_action(self) -> Optional[int]:
        """Get index of current action being executed.

        Returns:
            Action index or None
        """
        return self.state.get('current_action')

    def mark_action_complete(self, action_index: int) -> None:
        """Mark an action as complete.

        Args:
            action_index: Index of completed action
        """
        completed = self.state.get('completed_actions', [])
        if action_index not in completed:
            completed.append(action_index)
        self.update(
            completed_actions=completed,
            current_action=None
        )

    def mark_action_started(self, action_index: int, action_name: str) -> None:
        """Mark an action as started.

        Args:
            action_index: Index of action
            action_name: Name of action
        """
        self.update(
            current_action=action_index,
            current_action_name=action_name,
            status='in_progress'
        )

    def mark_update_complete(self, success: bool) -> None:
        """Mark update as complete.

        Args:
            success: Whether update was successful
        """
        self.update(
            status='completed' if success else 'failed',
            completed_at=datetime.now().isoformat()
        )
