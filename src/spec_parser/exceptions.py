"""
Custom exception hierarchy for spec parser.

All exceptions inherit from SpecParserError base class.
"""


class SpecParserError(Exception):
    """Base exception for all spec parser errors"""
    pass


class PDFExtractionError(SpecParserError):
    """Error during PDF extraction"""
    pass


class OCRError(SpecParserError):
    """Error during OCR processing"""
    pass


class SearchError(SpecParserError):
    """Error during search operations"""
    pass


class ValidationError(SpecParserError):
    """Error during data validation"""
    pass


class EmbeddingError(SpecParserError):
    """Error during embedding generation"""
    pass


class FileHandlerError(SpecParserError):
    """Error during file operations"""
    pass


class RLMError(SpecParserError):
    """Error during RLM operations (search, span extraction, navigation)"""
    pass


class ConfigurationError(SpecParserError):
    """Error in configuration"""
    pass
