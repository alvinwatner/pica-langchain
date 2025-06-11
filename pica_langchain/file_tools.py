import os
import json
import tempfile
import base64
from typing import Dict, Any, Optional, ClassVar, List
from pathlib import Path

import pandas as pd
from langchain.tools import BaseTool
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from pydantic import BaseModel, Field
from langchain_community.document_loaders import PyPDFLoader

import fitz
from PIL import Image
import pytesseract  # for OCR if needed


from .logger import get_logger

logger = get_logger()


class FileProcessor:
    """Base class for file processing"""
    
    @staticmethod
    def create_temp_file(content: bytes, suffix: str) -> str:
        """Create a temporary file and return its path"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    @staticmethod
    def cleanup_temp_file(file_path: str):
        """Clean up temporary file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


class PDFAnalysisTool(BaseTool):
    """Tool for analyzing PDF documents"""
    
    name: ClassVar[str] = "analyze_pdf"
    description: ClassVar[str] = "Analyze PDF documents - extract text, get page count, search content"
    
    def _run(
        self,
        file_path: str,
        operation: str = "extract_text",
        search_query: Optional[str] = None,
        page_range: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Analyze PDF document
        
        Args:
            file_path: Path to the PDF file
            operation: Operation to perform (extract_text, get_info, search, extract_pages)
            search_query: Text to search for (when operation is 'search')
            page_range: Page range like "1-5" or "1,3,5" (when operation is 'extract_pages')
        """
        try:
            if not os.path.exists(file_path):
                return json.dumps({"error": "File not found", "success": False})
            
            result = {}
            
            if operation == "extract_text":
                if PyPDFLoader:
                    loader = PyPDFLoader(file_path)
                    pages = loader.load()
                    result = {
                        "text": "\n\n".join([page.page_content for page in pages]),
                        "page_count": len(pages),
                        "success": True
                    }
                else:
                    result = {"error": "PDF processing not available", "success": False}
            
            elif operation == "get_info":
                if fitz:
                    doc = fitz.open(file_path)
                    result = {
                        "page_count": doc.page_count,
                        "metadata": doc.metadata,
                        "success": True
                    }
                    doc.close()
                else:
                    result = {"error": "PDF info extraction not available", "success": False}
            
            elif operation == "search" and search_query:
                if PyPDFLoader:
                    loader = PyPDFLoader(file_path)
                    pages = loader.load()
                    matches = []
                    for i, page in enumerate(pages):
                        if search_query.lower() in page.page_content.lower():
                            matches.append({
                                "page": i + 1,
                                "content": page.page_content[:500] + "..." if len(page.page_content) > 500 else page.page_content
                            })
                    result = {"matches": matches, "success": True}
                else:
                    result = {"error": "PDF search not available", "success": False}
            
            return json.dumps(result, default=str)
            
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return json.dumps({"error": str(e), "success": False})
    
    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)


class ExcelAnalysisTool(BaseTool):
    """Tool for analyzing Excel files"""
    
    name: ClassVar[str] = "analyze_excel"
    description: ClassVar[str] = "Analyze Excel files - get sheet info, extract data, perform calculations"
    
    def _run(
        self,
        file_path: str,
        operation: str = "get_info",
        sheet_name: Optional[str] = None,
        query: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Analyze Excel file
        
        Args:
            file_path: Path to the Excel file
            operation: Operation to perform (get_info, extract_data, summary_stats, search)
            sheet_name: Name of the sheet to analyze
            query: Search query or pandas query string
        """
        try:
            if not os.path.exists(file_path):
                return json.dumps({"error": "File not found", "success": False})
            
            result = {}
            
            if operation == "get_info":
                # Get basic info about the Excel file
                xl_file = pd.ExcelFile(file_path)
                result = {
                    "sheet_names": xl_file.sheet_names,
                    "success": True
                }
                
                # Get info for each sheet
                sheets_info = {}
                for sheet in xl_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet, nrows=0)  # Just headers
                    sheets_info[sheet] = {
                        "columns": list(df.columns),
                        "column_count": len(df.columns)
                    }
                result["sheets_info"] = sheets_info
            
            elif operation == "extract_data":
                sheet = sheet_name or 0
                df = pd.read_excel(file_path, sheet_name=sheet)
                result = {
                    "data": df.head(20).to_dict('records'),  # First 20 rows
                    "total_rows": len(df),
                    "columns": list(df.columns),
                    "success": True
                }
            
            elif operation == "summary_stats":
                sheet = sheet_name or 0
                df = pd.read_excel(file_path, sheet_name=sheet)
                numeric_cols = df.select_dtypes(include=['number']).columns
                
                if len(numeric_cols) > 0:
                    stats = df[numeric_cols].describe().to_dict()
                    result = {
                        "summary_statistics": stats,
                        "numeric_columns": list(numeric_cols),
                        "success": True
                    }
                else:
                    result = {"message": "No numeric columns found", "success": True}
            
            elif operation == "search" and query:
                sheet = sheet_name or 0
                df = pd.read_excel(file_path, sheet_name=sheet)
                
                # Simple text search across all columns
                mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False, na=False)).any(axis=1)
                matches = df[mask].head(10).to_dict('records')
                
                result = {
                    "matches": matches,
                    "total_matches": mask.sum(),
                    "success": True
                }
            
            return json.dumps(result, default=str, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return json.dumps({"error": str(e), "success": False})
    
    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)


class ImageAnalysisTool(BaseTool):
    """Tool for analyzing images"""
    
    name: ClassVar[str] = "analyze_image"
    description: ClassVar[str] = "Analyze images - get image info, extract text via OCR, get basic properties"
    
    def _run(
        self,
        file_path: str,
        operation: str = "get_info",
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Analyze image file
        
        Args:
            file_path: Path to the image file
            operation: Operation to perform (get_info, extract_text, get_base64)
        """
        try:
            if not os.path.exists(file_path):
                return json.dumps({"error": "File not found", "success": False})
            
            result = {}
            
            if operation == "get_info":
                if Image:
                    with Image.open(file_path) as img:
                        result = {
                            "format": img.format,
                            "mode": img.mode,
                            "size": img.size,
                            "width": img.width,
                            "height": img.height,
                            "success": True
                        }
                else:
                    result = {"error": "Image processing not available", "success": False}
            
            elif operation == "extract_text":
                if Image and pytesseract:
                    with Image.open(file_path) as img:
                        text = pytesseract.image_to_string(img)
                        result = {
                            "extracted_text": text.strip(),
                            "success": True
                        }
                else:
                    result = {"error": "OCR not available", "success": False}
            
            elif operation == "get_base64":
                with open(file_path, "rb") as img_file:
                    base64_string = base64.b64encode(img_file.read()).decode()
                    result = {
                        "base64": base64_string,
                        "success": True
                    }
            
            return json.dumps(result, default=str)
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return json.dumps({"error": str(e), "success": False})
    
    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)


# Pydantic schemas for tool validation
class PDFAnalysisSchema(BaseModel):
    file_path: str = Field(description="Path to the PDF file")
    operation: str = Field(default="extract_text", description="Operation: extract_text, get_info, search, extract_pages")
    search_query: Optional[str] = Field(None, description="Text to search for")
    page_range: Optional[str] = Field(None, description="Page range like '1-5' or '1,3,5'")

class ExcelAnalysisSchema(BaseModel):
    file_path: str = Field(description="Path to the Excel file")
    operation: str = Field(default="get_info", description="Operation: get_info, extract_data, summary_stats, search")
    sheet_name: Optional[str] = Field(None, description="Name of the sheet to analyze")
    query: Optional[str] = Field(None, description="Search query")

class ImageAnalysisSchema(BaseModel):
    file_path: str = Field(description="Path to the image file")
    operation: str = Field(default="get_info", description="Operation: get_info, extract_text, get_base64")

# Assign schemas to tools
PDFAnalysisTool.args_schema = PDFAnalysisSchema
ExcelAnalysisTool.args_schema = ExcelAnalysisSchema
ImageAnalysisTool.args_schema = ImageAnalysisSchema


def create_file_processing_tools(uploaded_files: List[Dict[str, Any]]) -> List[BaseTool]:
    """
    Create file processing tools based on uploaded files
    
    Args:
        uploaded_files: List of file info dicts with 'path', 'type', 'name' keys
    
    Returns:
        List of LangChain tools for file processing
    """
    tools = []
    
    for file_info in uploaded_files:
        file_type = file_info.get('type', '').lower()
        file_path = file_info.get('path')
        
        if not file_path or not os.path.exists(file_path):
            continue
        
        # Add appropriate tools based on file type
        if 'pdf' in file_type:
            tools.append(PDFAnalysisTool())
        elif file_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            tools.append(ExcelAnalysisTool())
        elif file_type.startswith('image/'):
            tools.append(ImageAnalysisTool())
    
    return tools
