#!/usr/bin/env python3
"""
Safe File Operations Module
Handles atomic file writes, backups, and safe file operations (FIX HIGH-2, MEDIUM-4)
"""

import os
import shutil
import json
import pickle
import tempfile
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager
import logging

logger = logging.getLogger('trading_system')


# ============================================================================
# ATOMIC FILE OPERATIONS
# ============================================================================

def atomic_write_json(filepath: str, data: Any, create_backup: bool = True) -> None:
    """
    Write JSON file atomically with optional backup

    Args:
        filepath: Target file path
        data: Data to write
        create_backup: Whether to backup existing file

    Raises:
        IOError: If write fails
    """
    filepath = Path(filepath)

    # Create backup if file exists
    if create_backup and filepath.exists():
        backup_path = Path(str(filepath) + '.backup')
        try:
            shutil.copy2(filepath, backup_path)
        except Exception as e:
            logger.warning(f"Failed to create backup of {filepath}: {e}")

    # Write to temporary file first
    temp_fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f'.{filepath.name}.',
        suffix='.tmp'
    )

    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename (POSIX guarantees atomicity)
        os.replace(temp_path, filepath)
        logger.debug(f"Atomically wrote {filepath}")

    except Exception as e:
        # Clean up temp file on failure
        try:
            os.remove(temp_path)
        except:
            pass
        raise IOError(f"Failed to write {filepath}: {e}") from e


def atomic_write_pickle(filepath: str, data: Any, create_backup: bool = True) -> None:
    """Write pickle file atomically with optional backup"""
    filepath = Path(filepath)

    # Create backup if file exists
    if create_backup and filepath.exists():
        backup_path = Path(str(filepath) + '.backup')
        try:
            shutil.copy2(filepath, backup_path)
        except Exception as e:
            logger.warning(f"Failed to create backup of {filepath}: {e}")

    # Write to temporary file first
    temp_fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f'.{filepath.name}.',
        suffix='.tmp'
    )

    try:
        with os.fdopen(temp_fd, 'wb') as f:
            pickle.dump(data, f)
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename
        os.replace(temp_path, filepath)
        logger.debug(f"Atomically wrote {filepath}")

    except Exception as e:
        try:
            os.remove(temp_path)
        except:
            pass
        raise IOError(f"Failed to write {filepath}: {e}") from e


def safe_read_json(filepath: str, default: Optional[Any] = None) -> Any:
    """
    Safely read JSON file with automatic backup recovery

    Args:
        filepath: File to read
        default: Value to return if file doesn't exist

    Returns:
        Loaded data or default

    Raises:
        ValueError: If JSON is invalid and no backup available
    """
    filepath = Path(filepath)

    if not filepath.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Corrupt JSON in {filepath}: {e}")

        # Try backup
        backup_path = Path(str(filepath) + '.backup')
        if backup_path.exists():
            logger.info(f"Attempting to recover from backup: {backup_path}")
            try:
                with open(backup_path, 'r') as f:
                    data = json.load(f)
                logger.info("Successfully recovered from backup")
                return data
            except Exception as backup_error:
                logger.error(f"Backup also corrupt: {backup_error}")

        if default is not None:
            logger.warning(f"Returning default value due to corrupt file")
            return default

        raise ValueError(f"Corrupt JSON file and no valid backup: {filepath}") from e


def safe_read_pickle(filepath: str, default: Optional[Any] = None) -> Any:
    """Safely read pickle file with automatic backup recovery"""
    filepath = Path(filepath)

    if not filepath.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    except (pickle.UnpicklingError, EOFError) as e:
        logger.error(f"Corrupt pickle in {filepath}: {e}")

        # Try backup
        backup_path = Path(str(filepath) + '.backup')
        if backup_path.exists():
            logger.info(f"Attempting to recover from backup: {backup_path}")
            try:
                with open(backup_path, 'rb') as f:
                    data = pickle.load(f)
                logger.info("Successfully recovered from backup")
                return data
            except Exception as backup_error:
                logger.error(f"Backup also corrupt: {backup_error}")

        if default is not None:
            logger.warning(f"Returning default value due to corrupt file")
            return default

        raise ValueError(f"Corrupt pickle file and no valid backup: {filepath}") from e


# ============================================================================
# SAFE FILE CONTEXT MANAGERS
# ============================================================================

@contextmanager
def safe_open_write(filepath: str, mode: str = 'w', encoding: str = 'utf-8'):
    """
    Context manager for safe file writing with automatic cleanup on error

    Usage:
        with safe_open_write('data.txt') as f:
            f.write('data')
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f'.{filepath.name}.',
        suffix='.tmp'
    )

    try:
        # Open temp file
        if 'b' in mode:
            f = os.fdopen(temp_fd, mode)
        else:
            f = os.fdopen(temp_fd, mode, encoding=encoding)

        yield f

        # Flush and sync before closing
        f.flush()
        os.fsync(f.fileno())
        f.close()

        # Atomic rename on success
        os.replace(temp_path, filepath)

    except Exception:
        # Clean up temp file on error
        try:
            os.remove(temp_path)
        except:
            pass
        raise


@contextmanager
def safe_open_read(filepath: str, mode: str = 'r', encoding: str = 'utf-8', try_backup: bool = True):
    """
    Context manager for safe file reading with automatic backup recovery

    Usage:
        with safe_open_read('data.txt') as f:
            data = f.read()
    """
    filepath = Path(filepath)

    try:
        if 'b' in mode:
            with open(filepath, mode) as f:
                yield f
        else:
            with open(filepath, mode, encoding=encoding) as f:
                yield f
    except (IOError, OSError) as e:
        if not try_backup:
            raise

        # Try backup
        backup_path = Path(str(filepath) + '.backup')
        if backup_path.exists():
            logger.warning(f"Primary file failed, trying backup: {backup_path}")
            if 'b' in mode:
                with open(backup_path, mode) as f:
                    yield f
            else:
                with open(backup_path, mode, encoding=encoding) as f:
                    yield f
        else:
            raise


# ============================================================================
# DIRECTORY AND CLEANUP UTILITIES
# ============================================================================

def ensure_directory(dirpath: str) -> Path:
    """Ensure directory exists, create if not"""
    path = Path(dirpath)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_old_backups(directory: str, pattern: str = '*.backup', days: int = 30) -> int:
    """
    Remove backup files older than specified days

    Args:
        directory: Directory to clean
        pattern: File pattern to match
        days: Remove files older than this many days

    Returns:
        Number of files removed
    """
    import time

    directory = Path(directory)
    if not directory.exists():
        return 0

    cutoff_time = time.time() - (days * 86400)
    removed_count = 0

    for filepath in directory.glob(pattern):
        try:
            if filepath.stat().st_mtime < cutoff_time:
                filepath.unlink()
                removed_count += 1
                logger.debug(f"Removed old backup: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to remove {filepath}: {e}")

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old backup files from {directory}")

    return removed_count


# ============================================================================
# STATE FILE OPERATIONS
# ============================================================================

class StateManager:
    """Manages safe reading/writing of state files"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        ensure_directory(self.base_dir)

    def save_state(self, name: str, data: Any, format: str = 'json') -> None:
        """
        Save state atomically

        Args:
            name: State name (e.g., 'portfolio', 'positions')
            data: Data to save
            format: 'json' or 'pickle'
        """
        if format == 'json':
            filepath = self.base_dir / f"{name}.json"
            atomic_write_json(filepath, data, create_backup=True)
        elif format == 'pickle':
            filepath = self.base_dir / f"{name}.pkl"
            atomic_write_pickle(filepath, data, create_backup=True)
        else:
            raise ValueError(f"Unknown format: {format}")

    def load_state(self, name: str, format: str = 'json', default: Optional[Any] = None) -> Any:
        """
        Load state safely

        Args:
            name: State name
            format: 'json' or 'pickle'
            default: Default value if not found

        Returns:
            Loaded state or default
        """
        if format == 'json':
            filepath = self.base_dir / f"{name}.json"
            return safe_read_json(filepath, default=default)
        elif format == 'pickle':
            filepath = self.base_dir / f"{name}.pkl"
            return safe_read_pickle(filepath, default=default)
        else:
            raise ValueError(f"Unknown format: {format}")

    def state_exists(self, name: str, format: str = 'json') -> bool:
        """Check if state file exists"""
        if format == 'json':
            return (self.base_dir / f"{name}.json").exists()
        elif format == 'pickle':
            return (self.base_dir / f"{name}.pkl").exists()
        return False


# ============================================================================
# LEGACY COMPATIBILITY WRAPPERS
# ============================================================================

def open_safe(*args, **kwargs):
    """
    Drop-in replacement for open() that uses safe_open_write/read

    Detects mode and uses appropriate safe wrapper
    """
    mode = args[1] if len(args) > 1 else kwargs.get('mode', 'r')

    if 'w' in mode or 'a' in mode:
        return safe_open_write(*args, **kwargs)
    else:
        return safe_open_read(*args, **kwargs)
