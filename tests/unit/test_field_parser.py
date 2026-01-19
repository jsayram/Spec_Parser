"""
Tests for field definition parser.
"""

import pytest
from pathlib import Path

from spec_parser.extractors.field_parser import (
    FieldTableParser,
    FieldDefinition,
    parse_fields_from_document
)


class TestFieldTableParser:
    """Tests for FieldTableParser class."""
    
    def test_infer_type_datetime(self):
        """Test datetime type inference."""
        parser = FieldTableParser()
        
        # Test with field name containing 'dttm'
        field_type = parser._infer_type("HDR.creation_dttm", "Creation timestamp", None)
        assert field_type == "datetime"
        
        # Test with ISO datetime example
        field_type = parser._infer_type("timestamp", "", "2017-08-11T10:17:03-00:00")
        assert field_type == "datetime"
        
        # Test with YYYYMMDDHHMMSS format
        field_type = parser._infer_type("date_time", "", "20190414065327")
        assert field_type == "datetime"
    
    def test_infer_type_string(self):
        """Test string type inference (default)."""
        parser = FieldTableParser()
        
        field_type = parser._infer_type("HDR.control_id", "Control ID", "00001")
        assert field_type == "string"
        
        field_type = parser._infer_type("DEV.device_id", "MAC address", "00:20:4a:be:cf:a5")
        assert field_type == "string"
    
    def test_infer_type_int(self):
        """Test integer type inference."""
        parser = FieldTableParser()
        
        field_type = parser._infer_type("count", "Number of items", "100")
        assert field_type == "int"
        
        field_type = parser._infer_type("timeout", "Timeout in seconds", "100")
        assert field_type == "int"
    
    def test_find_column(self):
        """Test column index finding."""
        parser = FieldTableParser()
        
        headers = ["Field", "Description", "Example"]
        
        # Test field column
        idx = parser._find_column(headers, parser.FIELD_HEADERS)
        assert idx == 0
        
        # Test description column
        idx = parser._find_column(headers, parser.DESCRIPTION_HEADERS)
        assert idx == 1
        
        # Test example column
        idx = parser._find_column(headers, parser.EXAMPLE_HEADERS)
        assert idx == 2
        
        # Test not found
        idx = parser._find_column(headers, ["nonexistent"])
        assert idx is None
    
    def test_parse_table_basic(self):
        """Test parsing a basic markdown table."""
        parser = FieldTableParser()
        
        markdown_table = """
|Field|Description|Example|
|---|---|---|
|HDR.control_id|Control identifier|"00001"|
|HDR.version_id|Version ID|"POCT1"|
|HDR.creation_dttm|Creation datetime|"2017-08-11T10:17:03-00:00"|
"""
        
        fields = parser._parse_table(
            markdown_table,
            page=11,
            citation_id="p11_tbl1",
            message_ids=["HEL.R01"]
        )
        
        assert len(fields) == 3
        assert fields[0].field_name == "HDR.control_id"
        assert fields[0].field_type == "string"
        assert fields[0].message_id == "HEL.R01"
        assert fields[0].page == 11
        
        assert fields[2].field_name == "HDR.creation_dttm"
        assert fields[2].field_type == "datetime"
    
    def test_parse_page_with_table_blocks(self):
        """Test parsing a page with table blocks."""
        parser = FieldTableParser()
        
        page_data = {
            "page": 12,
            "markdown": "### 3.1.1. HEL.R01 – Hello Message\n\nField definitions...",
            "blocks": [
                {
                    "type": "table",
                    "markdown_table": """
|Field|Description|Example|
|---|---|---|
|DEV.device_id|Device MAC address|"00:20:4a:be:cf:a5"|
|DEV.serial_id|Serial number|"00010387"|
""",
                    "citation": "p12_tbl1"
                }
            ],
            "citations": {
                "p12_tbl1": {
                    "page": 12,
                    "bbox": [100, 200, 500, 400],
                    "source": "text"
                }
            }
        }
        
        fields = parser.parse_page(page_data)
        
        assert len(fields) == 2
        assert fields[0].field_name == "DEV.device_id"
        assert fields[0].message_id == "HEL.R01"
        assert fields[1].field_name == "DEV.serial_id"


def test_parse_fields_from_document():
    """Test parsing fields from complete document."""
    document = {
        "pages": [
            {
                "page": 11,
                "markdown": "### 3.1.1. HEL.R01 – Hello Message",
                "blocks": [
                    {
                        "type": "table",
                        "markdown_table": """
|Field|Description|Example|
|---|---|---|
|HDR.control_id|Control ID|"00001"|
|HDR.version_id|Version ID|"POCT1"|
""",
                        "citation": "p11_tbl1"
                    }
                ],
                "citations": {}
            },
            {
                "page": 12,
                "markdown": "### 3.1.2. ACK.R01 – Acknowledgement Message",
                "blocks": [
                    {
                        "type": "table",
                        "markdown_table": """
|Field|Description|Example|
|---|---|---|
|ACK.type_id|Ack type|"AA"|
""",
                        "citation": "p12_tbl1"
                    }
                ],
                "citations": {}
            }
        ]
    }
    
    fields = parse_fields_from_document(document)
    
    assert len(fields) == 3
    assert any(f.field_name == "HDR.control_id" for f in fields)
    assert any(f.field_name == "ACK.type_id" for f in fields)
