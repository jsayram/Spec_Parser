"""
Spec version change detector and report generator.

Compares spec versions, generates change reports, and determines rebuild requirements.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from ..utils.hashing import compute_file_hash
from ..validation.impact_classifier import classify_change, ImpactLevel, ChangeType
from ..extractors.message_parser import MessageParser, MessageInventory
from ..schemas.citation import Citation


@dataclass
class BlockChange:
    """Single block-level change between versions."""
    impact_level: ImpactLevel
    change_type: ChangeType
    reasoning: str
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    old_citation: Optional[Citation] = None
    new_citation: Optional[Citation] = None


@dataclass
class RebuildDecision:
    """Decision on whether rebuild is required."""
    required: bool
    reason: str
    impact_counts: Dict[str, int]
    message_changes: Dict[str, List[str]] = field(default_factory=dict)
    field_changes: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class SpecDiff:
    """Complete diff between two spec versions."""
    old_version: str
    new_version: str
    changes: List[BlockChange]
    old_inventory: Optional[MessageInventory] = None
    new_inventory: Optional[MessageInventory] = None
    rebuild_required: bool = False
    is_baseline: bool = False
    pdf_hash_changed: bool = True


class SpecChangeDetector:
    """Detect and analyze changes between spec versions."""
    
    def __init__(self, output_dir: Path):
        """
        Initialize change detector.
        
        Args:
            output_dir: Base output directory for reports
        """
        self.output_dir = Path(output_dir)
        self.message_parser = MessageParser()
    
    def compare_specs(
        self,
        old_pdf_path: Optional[Path],
        new_pdf_path: Path,
        old_json_path: Optional[Path],
        new_json_path: Path,
        old_version: str,
        new_version: str,
        device_type: str
    ) -> SpecDiff:
        """
        Compare two spec versions.
        
        Args:
            old_pdf_path: Path to old PDF (None for baseline)
            new_pdf_path: Path to new PDF
            old_json_path: Path to old JSON sidecar (None for baseline)
            new_json_path: Path to new JSON sidecar
            old_version: Old version string
            new_version: New version string
            device_type: Device type identifier
        
        Returns:
            SpecDiff with complete change analysis
        """
        # Baseline case (first version)
        if old_pdf_path is None or old_json_path is None:
            return self._create_baseline(new_pdf_path, new_json_path, new_version, device_type)
        
        # Check PDF hashes
        old_hash = compute_file_hash(old_pdf_path)
        new_hash = compute_file_hash(new_pdf_path)
        
        if old_hash == new_hash:
            # No changes - identical PDFs
            return SpecDiff(
                old_version=old_version,
                new_version=new_version,
                changes=[],
                rebuild_required=False,
                pdf_hash_changed=False
            )
        
        # Parse message inventories
        old_inventory = self.message_parser.parse_spec(old_json_path, device_type)
        new_inventory = self.message_parser.parse_spec(new_json_path, device_type)
        
        # Compare JSON sidecars block-by-block
        changes = self._compare_json_sidecars(old_json_path, new_json_path)
        
        # Determine rebuild decision
        rebuild_decision = self._should_rebuild(changes, old_inventory, new_inventory)
        
        return SpecDiff(
            old_version=old_version,
            new_version=new_version,
            changes=changes,
            old_inventory=old_inventory,
            new_inventory=new_inventory,
            rebuild_required=rebuild_decision.required,
            is_baseline=False,
            pdf_hash_changed=True
        )
    
    def _create_baseline(
        self,
        pdf_path: Path,
        json_path: Path,
        version: str,
        device_type: str
    ) -> SpecDiff:
        """Create baseline diff for first version."""
        inventory = self.message_parser.parse_spec(json_path, device_type)
        
        return SpecDiff(
            old_version="none",
            new_version=version,
            changes=[],
            new_inventory=inventory,
            rebuild_required=False,
            is_baseline=True,
            pdf_hash_changed=True
        )
    
    def _compare_json_sidecars(
        self,
        old_json_path: Path,
        new_json_path: Path
    ) -> List[BlockChange]:
        """Compare JSON sidecars block-by-block using content hashes."""
        with open(old_json_path, 'r') as f:
            old_doc = json.load(f)
        with open(new_json_path, 'r') as f:
            new_doc = json.load(f)
        
        changes = []
        
        # Build hash maps for efficient comparison
        old_blocks_by_hash = self._build_block_hash_map(old_doc)
        new_blocks_by_hash = self._build_block_hash_map(new_doc)
        
        # Find removed blocks
        for content_hash, block in old_blocks_by_hash.items():
            if content_hash not in new_blocks_by_hash:
                impact = classify_change(
                    old_content=block.get("markdown", ""),
                    new_content=None,
                    block_type=block.get("type", "text")
                )
                changes.append(BlockChange(
                    impact_level=impact.level,
                    change_type=impact.change_type,
                    reasoning=impact.reasoning,
                    old_content=block.get("markdown", "")[:200],
                    old_citation=self._extract_citation(block)
                ))
        
        # Find added blocks
        for content_hash, block in new_blocks_by_hash.items():
            if content_hash not in old_blocks_by_hash:
                impact = classify_change(
                    old_content=None,
                    new_content=block.get("markdown", ""),
                    block_type=block.get("type", "text")
                )
                changes.append(BlockChange(
                    impact_level=impact.level,
                    change_type=impact.change_type,
                    reasoning=impact.reasoning,
                    new_content=block.get("markdown", "")[:200],
                    new_citation=self._extract_citation(block)
                ))
        
        return changes
    
    def _build_block_hash_map(self, doc: Dict) -> Dict[str, Dict]:
        """Build map of content_hash -> block for quick lookup."""
        hash_map = {}
        for page_data in doc:
            for block in page_data.get("blocks", []):
                content_hash = block.get("content_hash")
                if content_hash:
                    hash_map[content_hash] = block
        return hash_map
    
    def _extract_citation(self, block: Dict) -> Citation:
        """Extract citation from block."""
        page = block.get("page", 1)  # Default to page 1, not 0 (pages are 1-indexed)
        block_id = block.get("block_id", 0)
        block_type = block.get("type", "text")
        
        return Citation(
            page=page,
            bbox=tuple(block.get("bbox", [0, 0, 0, 0])),
            source=block.get("source", "text"),
            content_type=block_type,
            citation_id=f"p{page}_b{block_id}"
        )
    
    def _should_rebuild(
        self,
        changes: List[BlockChange],
        old_inventory: MessageInventory,
        new_inventory: MessageInventory
    ) -> RebuildDecision:
        """Determine if rebuild is required based on changes."""
        impact_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        for change in changes:
            impact_counts[change.impact_level.value] += 1
        
        # Analyze message changes
        message_changes = self._analyze_message_changes(old_inventory, new_inventory)
        field_changes = self._analyze_field_changes(old_inventory, new_inventory)
        
        # Rebuild required if ANY HIGH or MEDIUM impact
        rebuild_required = impact_counts["HIGH"] > 0 or impact_counts["MEDIUM"] > 0
        
        # Build reason
        if rebuild_required:
            parts = []
            if impact_counts["HIGH"] > 0:
                parts.append(f"{impact_counts['HIGH']} HIGH-impact changes")
            if impact_counts["MEDIUM"] > 0:
                parts.append(f"{impact_counts['MEDIUM']} MEDIUM-impact changes")
            
            msg_summary = []
            if message_changes["added"]:
                msg_summary.append(f"{len(message_changes['added'])} messages added")
            if message_changes["removed"]:
                msg_summary.append(f"{len(message_changes['removed'])} messages removed")
            
            if msg_summary:
                parts.append(f"({', '.join(msg_summary)})")
            
            reason = " + ".join(parts) + " require full rebuild"
        else:
            reason = f"{impact_counts['LOW']} LOW-impact documentation changes only - no rebuild needed"
        
        return RebuildDecision(
            required=rebuild_required,
            reason=reason,
            impact_counts=impact_counts,
            message_changes=message_changes,
            field_changes=field_changes
        )
    
    def _analyze_message_changes(
        self,
        old_inv: MessageInventory,
        new_inv: MessageInventory
    ) -> Dict[str, List[str]]:
        """Analyze message type changes between versions."""
        old_msgs = {m.message_id for m in old_inv.recognized_messages + old_inv.unrecognized_messages}
        new_msgs = {m.message_id for m in new_inv.recognized_messages + new_inv.unrecognized_messages}
        
        return {
            "added": sorted(list(new_msgs - old_msgs)),
            "removed": sorted(list(old_msgs - new_msgs)),
            "unchanged": sorted(list(old_msgs & new_msgs))
        }
    
    def _analyze_field_changes(
        self,
        old_inv: MessageInventory,
        new_inv: MessageInventory
    ) -> Dict[str, List[str]]:
        """Analyze field spec changes between versions."""
        old_fields = {f.field_id for f in old_inv.field_specs}
        new_fields = {f.field_id for f in new_inv.field_specs}
        
        return {
            "added": sorted(list(new_fields - old_fields)),
            "removed": sorted(list(old_fields - new_fields)),
            "unchanged": sorted(list(old_fields & new_fields))
        }
    
    def generate_report(
        self,
        diff: SpecDiff,
        device_type: str,
        vendor: str,
        model: str,
        session_dir: Optional[Path] = None
    ) -> Path:
        """
        Generate change report markdown file.
        
        Args:
            diff: SpecDiff to generate report from
            device_type: Device type identifier
            vendor: Vendor name
            model: Model name
            session_dir: Optional session directory to save reports in
        
        Returns:
            Path to generated report
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if diff.is_baseline:
            filename = f"BASELINE_v{diff.new_version}_{timestamp}.md"
            content = self._generate_baseline_report(diff, vendor, model)
        else:
            filename = f"CHANGES_v{diff.old_version}_to_v{diff.new_version}_{timestamp}.md"
            if not diff.pdf_hash_changed:
                # Special case: no changes
                content = self._generate_no_change_report(diff, vendor, model)
            else:
                content = self._generate_change_report(diff, vendor, model)
        
        # Save report - use session_dir/reports if provided, otherwise fallback to device version dir
        if session_dir:
            report_path = session_dir / "reports" / filename
        else:
            report_path = self.output_dir / f"{vendor}_{model}_v{diff.new_version}" / filename
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w') as f:
            f.write(content)
        
        # Also generate pending review report if there are unrecognized messages
        if diff.new_inventory and diff.new_inventory.unrecognized_messages:
            self._generate_pending_review_report(timestamp)
        
        return report_path
    
    def _generate_baseline_report(self, diff: SpecDiff, vendor: str, model: str) -> str:
        """Generate baseline report for first version."""
        inv = diff.new_inventory
        
        lines = [
            f"# Baseline Report v{diff.new_version}",
            f"**Device:** {vendor} {model}",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Extraction Summary",
            f"**Total Messages:** {len(inv.recognized_messages) + len(inv.unrecognized_messages)}",
            f"**Total Fields:** {len(inv.field_specs)}",
            "",
            "## Message Inventory"
        ]
        
        # Group by category
        for category, messages in inv.categories.items():
            if messages:
                lines.append(f"\n### {category.replace('_', ' ').title()}")
                lines.append(", ".join(messages))
        
        # Unrecognized messages
        if inv.unrecognized_messages:
            lines.append("\n### ⚠️ Unrecognized Messages (Auto-Accepted for Review)")
            for msg in inv.unrecognized_messages:
                citations_str = ", ".join([
                    f"Page {c.page}, Citation {c.citation_id}, BBox({', '.join(map(str, c.bbox))})"
                    for c in msg.citations
                ])
                lines.append(f"- **{msg.message_id}** {msg.direction} - {citations_str}")
        
        lines.append("\n## Field Specifications")
        lines.append(f"**Total:** {len(inv.field_specs)} legacy fields + {len(inv.extracted_fields)} detailed fields")
        
        # Add detailed field specifications per message
        if inv.message_schemas:
            lines.append("\n### Detailed Message Schemas")
            for message_id, schema in sorted(inv.message_schemas.items()):
                lines.append(f"\n#### {message_id}: {schema.description}")
                lines.append(f"**Location:** Page {schema.source_citation.page}, Citation {schema.citation}")
                
                if schema.fields:
                    lines.append(f"\n**Fields ({len(schema.fields)}):**")
                    lines.append("\n| Field | Type | Opt | Description | Example |")
                    lines.append("|-------|------|-----|-------------|---------|")
                    
                    for field in schema.fields:
                        opt = field.optionality or "-"
                        desc = (field.description[:50] + "...") if field.description and len(field.description) > 50 else (field.description or "-")
                        lines.append(f"| `{field.name}` | {field.data_type} | {opt} | {desc} | - |")
                else:
                    lines.append("\n*No fields extracted for this message*")
        else:
            lines.append("\n*Phase 2 field extraction not yet complete*")
        
        lines.append("\n## No Comparison")
        lines.append("This is the initial onboarding - no previous version to compare.")
        
        return "\n".join(lines)
    
    def _generate_change_report(self, diff: SpecDiff, vendor: str, model: str) -> str:
        """Generate change report between versions."""
        rebuild_dec = self._should_rebuild(diff.changes, diff.old_inventory, diff.new_inventory)
        
        lines = [
            f"# Change Report v{diff.old_version} → v{diff.new_version}",
            f"**Device:** {vendor} {model}",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Rebuild Decision",
            f"**Required:** {'YES' if rebuild_dec.required else 'NO'}",
            f"**Reason:** {rebuild_dec.reason}",
            "",
            "## Impact Summary",
            f"- HIGH: {rebuild_dec.impact_counts['HIGH']}",
            f"- MEDIUM: {rebuild_dec.impact_counts['MEDIUM']}",
            f"- LOW: {rebuild_dec.impact_counts['LOW']}",
            ""
        ]
        
        # HIGH impact changes
        high_changes = [c for c in diff.changes if c.impact_level == ImpactLevel.HIGH]
        if high_changes:
            lines.append("## HIGH Impact Changes")
            for change in high_changes:
                lines.append(self._format_change(change))
        
        # MEDIUM impact changes
        med_changes = [c for c in diff.changes if c.impact_level == ImpactLevel.MEDIUM]
        if med_changes:
            lines.append("## MEDIUM Impact Changes")
            for change in med_changes:
                lines.append(self._format_change(change))
        
        return "\n".join(lines)
    
    def _generate_no_change_report(self, diff: SpecDiff, vendor: str, model: str) -> str:
        """Generate report when no changes detected."""
        return f"""# No Changes Detected

**Device:** {vendor} {model}
**Versions:** v{diff.old_version} → v{diff.new_version}
**Generated:** {datetime.now().isoformat()}

## Status
No changes detected - spec identical to v{diff.old_version}.

PDF hash comparison shows no modifications.
"""
    
    def _format_change(self, change: BlockChange) -> str:
        """Format a single change for display."""
        lines = [f"\n**Impact:** {change.impact_level.value}"]
        lines.append(f"**Change:** {change.change_type.value}")
        
        if change.old_citation:
            lines.append(f"**Old:** Page {change.old_citation.page}, Citation {change.old_citation.citation_id}, BBox({', '.join(map(str, change.old_citation.bbox))})")
        
        if change.new_citation:
            lines.append(f"**New:** Page {change.new_citation.page}, Citation {change.new_citation.citation_id}, BBox({', '.join(map(str, change.new_citation.bbox))})")
        
        lines.append(f"**Reasoning:** {change.reasoning}")
        
        return "\n".join(lines)
    
    def _generate_pending_review_report(self, timestamp: str):
        """Generate consolidated pending review report across all devices."""
        custom_msg_path = Path("data/custom_messages.json")
        if not custom_msg_path.exists():
            return
        
        with open(custom_msg_path, 'r') as f:
            custom_msgs = json.load(f)
        
        report_path = Path("data") / f"PENDING_REVIEW_{timestamp}.md"
        
        lines = [
            "# Pending Message Review",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Summary"
        ]
        
        total_pending = sum(
            len([m for m in msgs.values() if m.get("review_status") == "pending"])
            for msgs in custom_msgs.values()
        )
        lines.append(f"**Total Pending:** {total_pending} messages")
        
        for device_type, messages in custom_msgs.items():
            pending = {k: v for k, v in messages.items() if v.get("review_status") == "pending"}
            if pending:
                lines.append(f"\n## {device_type}")
                for msg_id, msg_data in pending.items():
                    citations = msg_data.get("citations", [])
                    cit_str = ", ".join([f"Page {c['page']}" for c in citations])
                    lines.append(f"- **{msg_id}** ({len(citations)}× - {cit_str})")
        
        # Add review instructions with examples
        lines.append("\n## How to Review")
        lines.append("")
        lines.append("| Action | When to Use |")
        lines.append("|--------|-------------|")
        lines.append("| `approve` | Valid vendor-specific message, add to device profile |")
        lines.append("| `reject` | Extraction error (e.g., field name mistaken for message) |")
        lines.append("| `defer` | Needs investigation, keep in pending queue |")
        
        # Generate example commands using actual data
        lines.append("\n## Example Commands")
        lines.append("```bash")
        
        # Use first device and first message as example
        first_device = next(iter(custom_msgs.keys()), "<device_type>")
        first_pending = None
        for device_type, messages in custom_msgs.items():
            for msg_id, msg_data in messages.items():
                if msg_data.get("review_status") == "pending":
                    first_pending = (device_type, msg_id)
                    break
            if first_pending:
                break
        
        if first_pending:
            dev, msg = first_pending
            lines.append(f"# Approve as valid vendor message")
            lines.append(f"spec-parser device review-message \\")
            lines.append(f"  --device-type {dev} \\")
            lines.append(f"  --message {msg} \\")
            lines.append(f"  --action approve \\")
            lines.append(f"  --notes \"Confirmed vendor-specific message\"")
            lines.append("")
            lines.append(f"# Reject as extraction error")
            lines.append(f"spec-parser device review-message \\")
            lines.append(f"  --device-type {dev} \\")
            lines.append(f"  --message {msg} \\")
            lines.append(f"  --action reject \\")
            lines.append(f"  --notes \"Not a message - field name extracted in error\"")
            lines.append("")
            lines.append(f"# Defer for later investigation")
            lines.append(f"spec-parser device review-message \\")
            lines.append(f"  --device-type {dev} \\")
            lines.append(f"  --message {msg} \\")
            lines.append(f"  --action defer \\")
            lines.append(f"  --notes \"Need to verify against POCT1-A2 standard\"")
        else:
            lines.append("spec-parser device review-message --device-type <name> --message <id> --action approve|reject|defer --notes \"...\"")
        
        lines.append("```")
        
        with open(report_path, 'w') as f:
            f.write("\n".join(lines))
