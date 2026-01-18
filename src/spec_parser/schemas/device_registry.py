"""
Device registry schemas for device type management.

Pydantic models for tracking device types, spec versions, and change history.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import fcntl


class MessageSummary(BaseModel):
    """Summary of message types in a spec version."""
    observation_count: int = 0
    config_count: int = 0
    qc_count: int = 0
    vendor_count: int = 0
    unrecognized_count: int = 0
    pending_review_count: int = 0
    field_count: int = 0


class DeviceVersion(BaseModel):
    """Single version of a device spec."""
    version: str
    pdf_hash: str
    index_path: str
    report_path: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_baseline: bool = False
    rebuild_performed: bool = True
    approval_reason: Optional[str] = None
    impact_counts: Dict[str, int] = Field(default_factory=dict)
    message_summary: MessageSummary = Field(default_factory=MessageSummary)
    unrecognized_messages: List[Dict] = Field(default_factory=list)  # Citation dicts


class DeviceType(BaseModel):
    """Device type with full version history."""
    vendor: str
    model: str
    device_name: str
    current_version: str
    spec_history: List[DeviceVersion] = Field(default_factory=list)
    
    def get_version(self, version: str) -> Optional[DeviceVersion]:
        """Get specific version from history."""
        for v in self.spec_history:
            if v.version == version:
                return v
        return None
    
    def get_current_version_obj(self) -> Optional[DeviceVersion]:
        """Get current version object."""
        return self.get_version(self.current_version)
    
    def add_version(self, version: DeviceVersion):
        """Add new version to history."""
        self.spec_history.append(version)
        self.current_version = version.version


class DeviceRegistry:
    """Registry for managing device types and versions."""
    
    def __init__(self, registry_path: Path = Path("data/device_registry.json")):
        """
        Initialize device registry.
        
        Args:
            registry_path: Path to registry JSON file
        """
        self.registry_path = registry_path
        self.devices: Dict[str, DeviceType] = {}
        self._load()
    
    def _load(self):
        """Load registry from disk."""
        if not self.registry_path.exists():
            self.devices = {}
            return
        
        try:
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
                self.devices = {
                    device_id: DeviceType(**device_data)
                    for device_id, device_data in data.items()
                }
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load registry: {e}")
            self.devices = {}
    
    def save(self):
        """Save registry to disk with atomic write and file locking."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first
        temp_path = self.registry_path.with_suffix('.tmp')
        
        try:
            # Serialize devices
            data = {
                device_id: device.model_dump()
                for device_id, device in self.devices.items()
            }
            
            # Write with exclusive lock
            with open(temp_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(data, f, indent=2)
                f.flush()
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Atomic rename
            temp_path.replace(self.registry_path)
            
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to save registry: {e}")
    
    def register_device(
        self,
        vendor: str,
        model: str,
        device_name: str,
        version: DeviceVersion
    ) -> str:
        """
        Register new device type.
        
        Args:
            vendor: Vendor name
            model: Model name
            device_name: Human-readable device name
            version: Initial version
        
        Returns:
            Device type ID (vendor_model)
        """
        device_id = f"{vendor}_{model}"
        
        if device_id in self.devices:
            raise ValueError(f"Device type already registered: {device_id}")
        
        device = DeviceType(
            vendor=vendor,
            model=model,
            device_name=device_name,
            current_version=version.version,
            spec_history=[version]
        )
        
        self.devices[device_id] = device
        self.save()
        
        return device_id
    
    def update_device_version(
        self,
        device_id: str,
        version: DeviceVersion
    ):
        """
        Add new version to existing device.
        
        Args:
            device_id: Device type identifier
            version: New version to add
        """
        if device_id not in self.devices:
            raise ValueError(f"Device type not found: {device_id}")
        
        device = self.devices[device_id]
        
        # Check if version already exists
        if device.get_version(version.version):
            raise ValueError(f"Version already exists: {version.version}")
        
        device.add_version(version)
        self.save()
    
    def get_device(self, device_id: str) -> Optional[DeviceType]:
        """Get device type by ID."""
        return self.devices.get(device_id)
    
    def list_devices(self) -> List[str]:
        """List all registered device IDs."""
        return sorted(self.devices.keys())
    
    def get_device_by_name(self, vendor: str, model: str) -> Optional[DeviceType]:
        """Get device by vendor and model."""
        device_id = f"{vendor}_{model}"
        return self.devices.get(device_id)
    
    def device_exists(self, device_id: str) -> bool:
        """Check if device type is registered."""
        return device_id in self.devices
    
    def get_latest_version(self, device_id: str) -> Optional[DeviceVersion]:
        """Get latest version for device."""
        device = self.get_device(device_id)
        if device:
            return device.get_current_version_obj()
        return None
    
    def get_version_history(self, device_id: str) -> List[DeviceVersion]:
        """Get full version history for device."""
        device = self.get_device(device_id)
        if device:
            return device.spec_history
        return []


# Convenience functions for common operations

def create_device_version(
    version: str,
    pdf_hash: str,
    index_path: str,
    report_path: str,
    is_baseline: bool = False,
    rebuild_performed: bool = True,
    approval_reason: Optional[str] = None,
    impact_counts: Optional[Dict[str, int]] = None,
    message_summary: Optional[MessageSummary] = None,
    unrecognized_messages: Optional[List[Dict]] = None
) -> DeviceVersion:
    """
    Create a DeviceVersion object with proper defaults.
    
    Args:
        version: Version string (e.g., "1.0", "3.3.1")
        pdf_hash: SHA-256 hash of source PDF
        index_path: Path to index directory
        report_path: Path to change/baseline report
        is_baseline: Whether this is the first version
        rebuild_performed: Whether index was rebuilt
        approval_reason: Reason for approval (if rebuild required)
        impact_counts: Dict of HIGH/MEDIUM/LOW counts
        message_summary: Summary of messages and fields
        unrecognized_messages: List of unrecognized message citations
    
    Returns:
        DeviceVersion object
    """
    return DeviceVersion(
        version=version,
        pdf_hash=pdf_hash,
        index_path=index_path,
        report_path=report_path,
        is_baseline=is_baseline,
        rebuild_performed=rebuild_performed,
        approval_reason=approval_reason,
        impact_counts=impact_counts or {},
        message_summary=message_summary or MessageSummary(),
        unrecognized_messages=unrecognized_messages or []
    )


def load_registry(registry_path: Path = Path("data/device_registry.json")) -> DeviceRegistry:
    """Load device registry from disk."""
    return DeviceRegistry(registry_path)
