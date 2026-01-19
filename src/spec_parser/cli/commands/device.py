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
import pymupdf

from ...config import settings
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


def load_config(config_path: Path) -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Loaded config from: {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        sys.exit(1)


@click.group(name="device")
def device_commands():
    """Device lifecycle management commands."""
    pass


@device_commands.command(name="onboard")
@click.option("--config", type=click.Path(exists=True), help="Path to JSON config file")
@click.option("--vendor", help="Vendor name (e.g., Abbott)")
@click.option("--model", help="Model name (e.g., InfoHQ)")
@click.option("--device-name", help="Human-readable device name")
@click.option("--spec-version", help="Spec version (e.g., 3.3.1)")
@click.option("--spec-pdf", type=click.Path(exists=True), help="Path to spec PDF")
@click.option("--output-dir", default="data/spec_output", help="Output directory")
@click.option("--extract-blueprint", is_flag=True, help="Automatically extract blueprint after indexing")
def onboard_device(config: Optional[str], vendor: Optional[str], model: Optional[str], 
                   device_name: Optional[str], spec_version: Optional[str], 
                   spec_pdf: Optional[str], output_dir: str, extract_blueprint: bool):
    """
    Onboard new device type with initial spec version.
    
    Extracts PDF, parses messages/fields, generates baseline report,
    and registers device in registry.
    
    Use --config to load settings from JSON file, or provide individual options.
    CLI options override config file values.
    """
    # Load from config file if provided
    if config:
        config_data = load_config(Path(config))
        vendor = vendor or config_data.get("vendor")
        model = model or config_data.get("model")
        device_name = device_name or config_data.get("device_name")
        spec_version = spec_version or config_data.get("spec_version")
        spec_pdf = spec_pdf or config_data.get("spec_pdf")
        output_dir = config_data.get("output_dir", output_dir)
    
    # Validate required fields
    if not all([vendor, model, device_name, spec_version, spec_pdf]):
        logger.error("Missing required parameters. Provide --config or all of: --vendor, --model, --device-name, --spec-version, --spec-pdf")
        sys.exit(1)
    
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
    
    # Create images directory within version_dir and update settings
    images_dir = version_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    settings.image_dir = images_dir
    
    logger.info("Extracting PDF with PyMuPDF + OCR...")
    
    # Extract PDF and run OCR
    with PyMuPDFExtractor(spec_pdf_path) as extractor:
        pages = extractor.extract_all_pages()
        
        # Run OCR on images (need to reopen PDF for page access)
        ocr_processor = OCRProcessor()
        pdf_doc = pymupdf.open(spec_pdf_path)
        for page_bundle in pages:
            pdf_page = pdf_doc[page_bundle.page - 1]  # page_bundle.page is 1-indexed
            ocr_processor.process_page(page_bundle, pdf_page)
        pdf_doc.close()
    
    # Write JSON sidecar
    json_path = version_dir / "json" / "document.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_writer = JSONSidecarWriter()
    device_type_name = f"{vendor}_{model}"
    json_writer.write_document(pages, json_path, device_type_name)
    
    # Write markdown
    from ...parsers.markdown_pipeline import MarkdownPipeline
    md_dir = version_dir / "markdown"
    md_dir.mkdir(exist_ok=True)
    md_path = md_dir / "full_document.md"
    pipeline = MarkdownPipeline()
    markdown_content = pipeline.build_simple_markdown(pages)
    md_path.write_text(markdown_content)
    
    logger.info("Building search indices...")
    
    # Build FAISS index
    index_dir = version_dir / "index"
    index_dir.mkdir(exist_ok=True)
    
    from ...embeddings.embedding_model import EmbeddingModel
    embedding_model = EmbeddingModel()
    faiss_indexer = FAISSIndexer(embedding_model, index_dir / "faiss.index")
    
    # Index document texts (simplified - just index text blocks for now)
    logger.info("Indexing document texts...")
    texts = []
    metadatas = []
    for page_bundle in pages:
        for block in page_bundle.blocks:
            # Handle different block types with their specific content fields
            text_content = None
            if block.type == "text" and hasattr(block, 'content') and block.content:
                text_content = block.content
            elif block.type == "table" and hasattr(block, 'markdown_table') and block.markdown_table:
                text_content = block.markdown_table
            
            if text_content:
                texts.append(text_content)
                metadatas.append({
                    "page": page_bundle.page,
                    "bbox": block.bbox,
                    "type": block.type
                })
    
    if texts:
        faiss_indexer.add_texts(texts, metadatas)
        logger.info(f"Indexed {len(texts)} text blocks")
    
    # Extract and index field definitions with metadata
    logger.info("Extracting and indexing field definitions...")
    from ...extractors.field_parser import parse_fields_from_document
    from ...utils.file_handler import read_json
    
    # Load raw JSON document (not PageBundle objects)
    document_json = read_json(json_path)
    fields = parse_fields_from_document(document_json)
    
    if fields:
        field_texts = []
        field_metadatas = []
        
        for field in fields:
            # Create searchable text representation with all field info
            field_text = (
                f"Field: {field.field_name} | "
                f"Type: {field.field_type} | "
                f"Message: {field.message_id} | "
                f"Description: {field.description or 'N/A'}"
            )
            if field.example:
                field_text += f" | Example: {field.example}"
            
            field_texts.append(field_text)
            field_metadatas.append({
                "page": field.page,
                "type": "field",
                "field_name": field.field_name,
                "field_type": field.field_type,
                "message_id": field.message_id,
                "optionality": field.optionality,
                "citation_id": field.citation_id
            })
        
        faiss_indexer.add_texts(field_texts, field_metadatas)
        logger.info(f"Indexed {len(fields)} field definitions")
    
    faiss_indexer.save()
    
    # Build BM25 index with both text blocks and fields
    bm25_searcher = BM25Searcher(index_dir / "bm25.index")
    bm25_searcher.add_texts(texts, metadatas)
    
    if fields:
        bm25_searcher.add_texts(field_texts, field_metadatas)
        logger.info(f"Added {len(fields)} fields to BM25 index")
    
    bm25_searcher.save()
    logger.info("BM25 index built")
    
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
    
    report_path = detector.generate_report(diff, device_id, vendor, model, session_dir=version_dir)
    
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
                "citation_id": citation.citation_id,
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
    
    # Automatically extract blueprint if requested
    if extract_blueprint:
        logger.info("=" * 70)
        logger.info("Extracting blueprint with LLM...")
        logger.info("=" * 70)
        
        try:
            from ...llm.llm_interface import LLMInterface
            from ...llm.nodes import BlueprintFlow
            
            llm = LLMInterface()
            flow = BlueprintFlow(
                device_id=device_id,
                device_name=device_name,
                index_dir=index_dir,
                llm=llm
            )
            
            blueprint = flow.run()
            
            # Save blueprint
            blueprint_path = version_dir / "blueprint.json"
            with open(blueprint_path, 'w') as f:
                json.dump(blueprint, f, indent=2)
            
            logger.success(f"Blueprint saved: {blueprint_path}")
            if 'summary' in blueprint:
                logger.info(f"Summary: {blueprint['summary']}")
            
        except Exception as e:
            logger.error(f"Blueprint extraction failed: {e}")
            logger.warning("Device onboarded successfully, but blueprint extraction encountered an error")
            logger.exception(e)


@device_commands.command(name="update")
@click.option("--config", type=click.Path(exists=True), help="Path to JSON config file")
@click.option("--device-type", help="Device type ID (vendor_model)")
@click.option("--spec-version", help="New spec version")
@click.option("--spec-pdf", type=click.Path(exists=True), help="Path to new spec PDF")
@click.option("--approve", help="Approval reason (required if rebuild needed)")
@click.option("--output-dir", default="data/spec_output", help="Output directory")
def update_device_spec(config: Optional[str], device_type: Optional[str], 
                       spec_version: Optional[str], spec_pdf: Optional[str],
                       approve: Optional[str], output_dir: str):
    """
    Update device spec to new version.
    
    Compares with previous version, generates change report,
    and rebuilds index if HIGH/MEDIUM impact changes detected.
    
    Use --config to load settings from JSON file, or provide individual options.
    CLI options override config file values.
    """
    # Load from config file if provided
    if config:
        config_data = load_config(Path(config))
        device_type = device_type or config_data.get("device_type")
        spec_version = spec_version or config_data.get("spec_version")
        spec_pdf = spec_pdf or config_data.get("spec_pdf")
        approve = approve or config_data.get("approve")
        output_dir = config_data.get("output_dir", output_dir)
    
    # Validate required fields
    if not all([device_type, spec_version, spec_pdf]):
        logger.error("Missing required parameters. Provide --config or all of: --device-type, --spec-version, --spec-pdf")
        sys.exit(1)
    
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
    
    # Create images directory within version_dir and update settings
    images_dir = version_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    settings.image_dir = images_dir
    
    logger.info("Extracting new spec version...")
    
    # Extract PDF
    with PyMuPDFExtractor(spec_pdf_path) as extractor:
        pages = extractor.extract_all_pages()
    
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
    report_path = detector.generate_report(diff, device_type, vendor, model, session_dir=version_dir)
    
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
        from ...parsers.markdown_pipeline import MarkdownPipeline
        md_dir = version_dir / "markdown"
        md_dir.mkdir(exist_ok=True)
        md_path = md_dir / "full_document.md"
        pipeline = MarkdownPipeline()
        markdown_content = pipeline.build_simple_markdown(pages)
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
@click.option("--config", type=click.Path(exists=True), help="Path to JSON config file")
@click.option("--device-type", help="Device type ID")
@click.option("--message", help="Message ID to review")
@click.option("--action", type=click.Choice(["approve", "reject", "defer"]), help="Review action")
@click.option("--notes", default="", help="Review notes")
def review_message(config: Optional[str], device_type: Optional[str], 
                   message: Optional[str], action: Optional[str], notes: str):
    """
    Review and update status of unrecognized message.
    
    Use --config to load settings from JSON file, or provide individual options.
    CLI options override config file values.
    """
    # Load from config file if provided
    if config:
        config_data = load_config(Path(config))
        device_type = device_type or config_data.get("device_type")
        message = message or config_data.get("message")
        action = action or config_data.get("action")
        notes = notes or config_data.get("notes", "")
    
    # Validate required fields
    if not all([device_type, message, action]):
        logger.error("Missing required parameters. Provide --config or all of: --device-type, --message, --action")
        sys.exit(1)
    
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


@device_commands.command(name="extract-blueprint")
@click.option("--device-id", required=True, help="Device identifier (e.g., Roche_CobasLiat)")
@click.option("--device-name", required=True, help="Human-readable device name")
@click.option("--index-dir", required=True, type=click.Path(exists=True), help="Path to FAISS/BM25 index directory")
@click.option("--output", type=click.Path(), help="Output path for blueprint.json (default: index_dir/blueprint.json)")
@click.option("--provider", type=click.Choice(["ollama", "anthropic", "openai"]), help="Override LLM provider from config")
@click.option("--model", help="Override LLM model from config")
def extract_blueprint(device_id: str, device_name: str, index_dir: str, output: Optional[str], provider: Optional[str], model: Optional[str]):
    """
    Extract POCT1-A device blueprint using LLM.
    
    Uses existing FAISS/BM25 index to retrieve context,
    then calls LLM (local or external) to extract message definitions.
    Results are cached in SQLite for deterministic re-runs.
    
    Example:
        spec-parser device extract-blueprint \\
            --device-id Roche_CobasLiat \\
            --device-name "Roche cobas Liat Analyzer" \\
            --index-dir data/spec_output/20260118_180201_rochecobasliat/index
    """
    from ...llm.llm_interface import LLMInterface, create_llm_provider
    from ...llm.nodes import BlueprintFlow
    
    logger.info("=" * 70)
    logger.info(f"Extracting blueprint for: {device_name}")
    logger.info("=" * 70)
    
    # Create LLM provider with optional overrides
    try:
        if provider or model:
            llm_provider = create_llm_provider(provider_name=provider, model=model)
            llm = LLMInterface(provider=llm_provider)
        else:
            llm = LLMInterface()
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {e}")
        logger.info("For Ollama: Ensure 'ollama serve' is running and model is pulled")
        logger.info("For external APIs: Set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    # Run blueprint extraction
    flow = BlueprintFlow(
        device_id=device_id,
        device_name=device_name,
        index_dir=Path(index_dir),
        llm=llm
    )
    
    try:
        blueprint = flow.run()
    except Exception as e:
        logger.error(f"Blueprint extraction failed: {e}")
        logger.exception(e)
        sys.exit(1)
    
    # Save blueprint
    if output:
        output_path = Path(output)
    else:
        output_path = Path(index_dir).parent / "blueprint.json"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(blueprint, f, indent=2)
    
    logger.success(f"Blueprint saved: {output_path}")
    if 'summary' in blueprint:
        logger.info(f"Summary: {blueprint['summary']}")
    if 'cache_stats' in blueprint:
        logger.info(f"Cache stats: {blueprint['cache_stats']}")

