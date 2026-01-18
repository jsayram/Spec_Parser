"""
CLI commands for device lifecycle management.

Commands for device onboarding, spec updates, and message review.
"""

import sys
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
import click
from loguru import logger

from ...parsers.pymupdf_extractor import PyMuPDFExtractor
from ...parsers.ocr_processor import OCRProcessor
from ...parsers.json_sidecar import JSONSidecarWriter
from ...search.faiss_indexer import FAISSIndexer
from ...search.bm25_searcher import BM25Searcher
from ...validation.spec_diff import SpecChangeDetector
from ...schemas.device_registry import (
    DeviceRegistry, DeviceVersion, MessageSummary, create_device_version
)
from ...utils.hashing import compute_file_hash


@click.group(name="device")
def device_commands():
    """Device lifecycle management commands."""
    pass


@device_commands.command(name="onboard")
@click.option("--vendor", required=True, help="Vendor name (e.g., Abbott)")
@click.option("--model", required=True, help="Model name (e.g., InfoHQ)")
@click.option("--device-name", required=True, help="Human-readable device name")
@click.option("--spec-version", required=True, help="Spec version (e.g., 3.3.1)")
@click.option("--spec-pdf", required=True, type=click.Path(exists=True), help="Path to spec PDF")
@click.option("--output-dir", default="data/spec_output", help="Output directory")
def onboard_device(vendor: str, model: str, device_name: str, spec_version: str, 
                   spec_pdf: str, output_dir: str):
    """
    Onboard new device type with initial spec version.
    
    Extracts PDF, parses messages/fields, generates baseline report,
    and registers device in registry.
    """
    logger.info(f"Onboarding device: {vendor} {model} v{spec_version}")
    
    spec_pdf_path = Path(spec_pdf)
    output_base = Path(output_dir)
    device_id = f"{vendor}_{model}"
    
    # Check if device already registered
    registry = DeviceRegistry()
    if registry.device_exists(device_id):
        logger.error(f"Device already registered: {device_id}")
        logger.info("Use 'update-device-spec' to add new version")
        sys.exit(1)
    
    # Compute PDF hash
    pdf_hash = compute_file_hash(spec_pdf_path)
    
    # Create version-specific output directory
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_dir = output_base / f"{timestamp}_{vendor.lower()}{model.lower()}"
    version_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Extracting PDF with PyMuPDF + OCR...")
    
    # Extract PDF
    extractor = PyMuPDFExtractor()
    pages = extractor.extract(spec_pdf_path)
    
    # Run OCR on images
    ocr_processor = OCRProcessor()
    for page in pages:
        ocr_processor.process_page(page)
    
    # Write JSON sidecar
    json_path = version_dir / "json" / "document.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_writer = JSONSidecarWriter()
    json_writer.write_document(pages, json_path, device_type)
    
    # Write markdown
    from ...parsers.markdown_builder import build_markdown
    md_dir = version_dir / "markdown"
    md_dir.mkdir(exist_ok=True)
    md_path = md_dir / "full_document.md"
    markdown_content = build_markdown(pages)
    md_path.write_text(markdown_content)
    
    logger.info("Building search indices...")
    
    # Build FAISS index
    index_dir = version_dir / "index"
    index_dir.mkdir(exist_ok=True)
    faiss_indexer = FAISSIndexer(index_dir)
    faiss_indexer.index_document(json_path)
    
    # Build BM25 index
    bm25_searcher = BM25Searcher(index_dir)
    bm25_searcher.index_document(json_path)
    
    logger.info("Analyzing messages and generating baseline report...")
    
    # Generate baseline report
    detector = SpecChangeDetector(output_base)
    diff = detector.compare_specs(
        old_pdf_path=None,
        new_pdf_path=spec_pdf_path,
        old_json_path=None,
        new_json_path=json_path,
        old_version="none",
        new_version=spec_version,
        device_type=device_id
    )
    
    report_path = detector.generate_report(diff, device_id, vendor, model)
    
    # Build message summary
    inv = diff.new_inventory
    message_summary = MessageSummary(
        observation_count=len(inv.categories.get("observation", [])),
        config_count=len(inv.categories.get("config", [])),
        qc_count=len(inv.categories.get("qc", [])),
        vendor_count=len(inv.categories.get("vendor_specific", [])),
        unrecognized_count=len(inv.unrecognized_messages),
        pending_review_count=len(inv.unrecognized_messages),
        field_count=len(inv.field_specs)
    )
    
    # Convert unrecognized messages to serializable format
    unrecognized_data = []
    for msg in inv.unrecognized_messages:
        for citation in msg.citations:
            unrecognized_data.append({
                "message_id": msg.message_id,
                "direction": msg.direction,
                "page": citation.page,
                "bbox": citation.bbox,
                "block_id": citation.block_id,
                "source": citation.source
            })
    
    # Create device version
    device_version = create_device_version(
        version=spec_version,
        pdf_hash=pdf_hash,
        index_path=str(index_dir.relative_to(output_base)),
        report_path=str(report_path.relative_to(output_base)),
        is_baseline=True,
        rebuild_performed=True,
        approval_reason="Initial onboarding",
        impact_counts={},
        message_summary=message_summary,
        unrecognized_messages=unrecognized_data
    )
    
    # Register device
    registry.register_device(vendor, model, device_name, device_version)
    
    logger.success(f"Device onboarded: {device_id} v{spec_version}")
    logger.info(f"Index: {index_dir}")
    logger.info(f"Report: {report_path}")
    logger.info(f"Messages: {message_summary.field_count} fields, "
                f"{message_summary.unrecognized_count} unrecognized")


@device_commands.command(name="update")
@click.option("--device-type", required=True, help="Device type ID (vendor_model)")
@click.option("--spec-version", required=True, help="New spec version")
@click.option("--spec-pdf", required=True, type=click.Path(exists=True), help="Path to new spec PDF")
@click.option("--approve", help="Approval reason (required if rebuild needed)")
@click.option("--output-dir", default="data/spec_output", help="Output directory")
def update_device_spec(device_type: str, spec_version: str, spec_pdf: str,
                       approve: Optional[str], output_dir: str):
    """
    Update device spec to new version.
    
    Compares with previous version, generates change report,
    and rebuilds index if HIGH/MEDIUM impact changes detected.
    """
    logger.info(f"Updating device: {device_type} → v{spec_version}")
    
    spec_pdf_path = Path(spec_pdf)
    output_base = Path(output_dir)
    
    # Load registry
    registry = DeviceRegistry()
    device = registry.get_device(device_type)
    if not device:
        logger.error(f"Device not registered: {device_type}")
        logger.info("Use 'onboard-device' first")
        sys.exit(1)
    
    # Get previous version
    prev_version = device.get_current_version_obj()
    if not prev_version:
        logger.error(f"No previous version found for {device_type}")
        sys.exit(1)
    
    # Compute PDF hash
    new_pdf_hash = compute_file_hash(spec_pdf_path)
    
    # Check if PDF unchanged
    if new_pdf_hash == prev_version.pdf_hash:
        logger.warning(f"No changes detected - spec identical to v{prev_version.version}")
        logger.info("PDF hash matches previous version, skipping extraction")
        sys.exit(0)
    
    # Create version-specific output directory
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    vendor, model = device_type.split('_', 1)
    version_dir = output_base / f"{timestamp}_{vendor.lower()}{model.lower()}"
    version_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Extracting new spec version...")
    
    # Extract PDF
    extractor = PyMuPDFExtractor()
    pages = extractor.extract(spec_pdf_path)
    
    # Run OCR
    ocr_processor = OCRProcessor()
    for page in pages:
        ocr_processor.process_page(page)
    
    # Write JSON sidecar
    json_path = version_dir / "json" / "document.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_writer = JSONSidecarWriter()
    json_writer.write_document(pages, json_path, device_type)
    
    # Get old JSON path - use pathlib for cross-platform compatibility
    index_path = Path(prev_version.index_path)
    old_json_path = output_base / str(index_path.parent.parent / "json" / "document.json")
    old_pdf_path = spec_pdf_path  # TODO: Store old PDF path in registry?
    
    logger.info("Comparing with previous version...")
    
    # Generate diff
    detector = SpecChangeDetector(output_base)
    diff = detector.compare_specs(
        old_pdf_path=None,  # We don't have old PDF stored
        new_pdf_path=spec_pdf_path,
        old_json_path=old_json_path,
        new_json_path=json_path,
        old_version=prev_version.version,
        new_version=spec_version,
        device_type=device_type
    )
    
    # Generate change report
    report_path = detector.generate_report(diff, device_type, vendor, model)
    
    logger.info(f"Change report: {report_path}")
    
    # Check if rebuild required
    if diff.rebuild_required:
        if not approve:
            logger.error("Rebuild required due to HIGH/MEDIUM impact changes")
            logger.error("Provide approval reason with --approve \"reason\"")
            logger.info(f"See change report: {report_path}")
            sys.exit(1)
        
        logger.info(f"Approval provided: {approve}")
        logger.info("Rebuilding index...")
        
        # Write markdown
        from ...parsers.markdown_builder import build_markdown
        md_dir = version_dir / "markdown"
        md_dir.mkdir(exist_ok=True)
        md_path = md_dir / "full_document.md"
        markdown_content = build_markdown(pages)
        md_path.write_text(markdown_content)
        
        # Build indices
        index_dir = version_dir / "index"
        index_dir.mkdir(exist_ok=True)
        faiss_indexer = FAISSIndexer(index_dir)
        faiss_indexer.index_document(json_path)
        
        bm25_searcher = BM25Searcher(index_dir)
        bm25_searcher.index_document(json_path)
        
        rebuild_performed = True
    else:
        logger.info("No rebuild needed - LOW impact changes only")
        # Reuse previous index
        index_dir = output_base / prev_version.index_path
        rebuild_performed = False
    
    # Build message summary
    inv = diff.new_inventory
    message_summary = MessageSummary(
        observation_count=len(inv.categories.get("observation", [])),
        config_count=len(inv.categories.get("config", [])),
        qc_count=len(inv.categories.get("qc", [])),
        vendor_count=len(inv.categories.get("vendor_specific", [])),
        unrecognized_count=len(inv.unrecognized_messages),
        pending_review_count=len(inv.unrecognized_messages),
        field_count=len(inv.field_specs)
    )
    
    # Create new version
    device_version = create_device_version(
        version=spec_version,
        pdf_hash=new_pdf_hash,
        index_path=str(index_dir.relative_to(output_base)),
        report_path=str(report_path.relative_to(output_base)),
        is_baseline=False,
        rebuild_performed=rebuild_performed,
        approval_reason=approve,
        impact_counts={"HIGH": 0, "MEDIUM": 0, "LOW": len(diff.changes)},
        message_summary=message_summary
    )
    
    # Update registry
    registry.update_device_version(device_type, device_version)
    
    logger.success(f"Device updated: {device_type} v{spec_version}")


@device_commands.command(name="review-message")
@click.option("--device-type", required=True, help="Device type ID")
@click.option("--message", required=True, help="Message ID to review")
@click.option("--action", required=True, type=click.Choice(["approve", "reject", "defer"]))
@click.option("--notes", default="", help="Review notes")
def review_message(device_type: str, message: str, action: str, notes: str):
    """Review and update status of unrecognized message."""
    logger.info(f"Reviewing message: {device_type} - {message}")
    
    custom_msg_path = Path("data/custom_messages.json")
    if not custom_msg_path.exists():
        logger.error("No custom messages found")
        sys.exit(1)
    
    with open(custom_msg_path, 'r') as f:
        custom_msgs = json.load(f)
    
    if device_type not in custom_msgs or message not in custom_msgs[device_type]:
        logger.error(f"Message not found: {device_type} - {message}")
        sys.exit(1)
    
    # Update status
    from datetime import datetime as dt
    custom_msgs[device_type][message]["review_status"] = action
    custom_msgs[device_type][message]["review_notes"] = notes
    custom_msgs[device_type][message]["reviewed_at"] = dt.now().isoformat()
    
    # Save
    with open(custom_msg_path, 'w') as f:
        json.dump(custom_msgs, f, indent=2)
    
    logger.success(f"Message {action}d: {message}")


@device_commands.command(name="list")
def list_devices():
    """List all registered devices."""
    registry = DeviceRegistry()
    devices = registry.list_devices()
    
    if not devices:
        logger.info("No devices registered")
        return
    
    logger.info(f"Registered devices ({len(devices)}):")
    for device_id in devices:
        device = registry.get_device(device_id)
        logger.info(f"  {device_id}: {device.device_name} (v{device.current_version})")
