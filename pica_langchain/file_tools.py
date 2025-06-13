import os
import asyncio
import json
import tempfile
import base64
from typing import Dict, Any, Optional, ClassVar, List
from pathlib import Path

import pandas as pd
from openai import OpenAI
from langchain.tools import BaseTool
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from pydantic import BaseModel, Field
from langchain_community.document_loaders import PyPDFLoader
from .client import PicaClient

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
    client: PicaClient
    
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
        action = f"Starting PDF analysis: {operation} on file {os.path.basename(file_path)}"
        logger.info(action)
        action_human = f"Starting PDF analysis"
        asyncio.create_task(self.client.action_tracking_service.update_action(action_human, "PDF Analysis"))
        
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
    client: PicaClient
    
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
        action = f"Starting Excel analysis: {operation} on file {os.path.basename(file_path)}"
        logger.info(action)
        asyncio.create_task(self.client.action_tracking_service.update_action(action, "Excel Analysis"))
        
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
    """Tool for analyzing images with OCR, basic properties, and AI vision"""
    
    name: ClassVar[str] = "analyze_image"
    description: ClassVar[str] = """Analyze images using AI vision, OCR, or get basic properties. 
    
    IMPORTANT: When the user asks specific questions about an image (like 'Who is this person?', 'What are they doing?', 'Count the objects'), 
    use operation 'analyze_content' and pass the user's exact question as the 'query' parameter.
    
    Operations:
    - get_info: Get basic image properties
    - extract_text: Extract text using OCR  
    - describe_image: General AI description of image content
    - analyze_content: Answer specific questions about the image (USE THIS for user questions)
    - comprehensive_analysis: Combined analysis (OCR + AI vision + properties)
    """    
    openai_client: OpenAI = Field(default=None, exclude=True)
    client: PicaClient
    
    def __init__(self, **kwargs):
        if self.client.openai_api_key:
            kwargs["openai_client"] = OpenAI(api_key=self.client.openai_api_key)
        else:
            kwargs["openai_client"] = OpenAI()
        super().__init__(**kwargs)
    
    def _encode_image_to_base64(self, file_path: str) -> str:
        """Encode image to base64 string"""
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def _analyze_image_with_vision(self, file_path: str, query: Optional[str] = None) -> dict:
        """Analyze image using GPT-4 Vision model"""
        action = f"Starting AI vision analysis for: {os.path.basename(file_path)}"
        logger.info(action)
        action_human = f"Starting AI vision analysis"
        asyncio.create_task(self.client.action_tracking_service.update_action(action_human, "AI Vision Analysis"))
        
        if not self.openai_client:
            error_msg = "OpenAI client not available for vision analysis"
            logger.error(error_msg)
            asyncio.create_task(self.client.action_tracking_service.update_action(error_msg, "AI Vision Analysis"))            
            return {"error": "OpenAI client not available", "success": False}
        
        try:
            # Encode image to base64
            action = "Encoding image for AI vision analysis"
            logger.info(action)
            asyncio.create_task(self.client.action_tracking_service.update_action(action, "AI Vision Analysis"))
            base64_image = self._encode_image_to_base64(file_path)
            
            # Determine image format
            image_format = "jpeg"
            if file_path.lower().endswith('.png'):
                image_format = "png"
            elif file_path.lower().endswith('.gif'):
                image_format = "gif"
            elif file_path.lower().endswith('.webp'):
                image_format = "webp"
                        
            # Default query if none provided
            if not query:
                query = "Describe what you see in this image. Include details about objects, people, text, colors, setting, and any other notable features."
            
            logger.info(f"Analyzing image with vision model: {query}")
            action = f"Sending image to Vision Model with query: {query[:100]}..."
            asyncio.create_task(self.client.action_tracking_service.update_action(action, "AI Vision Analysis"))

            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": query},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{base64_image}",
                                    "detail": "high" 
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1,
            )
            
            description = response.choices[0].message.content
            action = "Successfully received AI vision analysis response"
            logger.info(action)
            asyncio.create_task(self.client.action_tracking_service.update_action(action, "AI Vision Analysis"))            
            
            return {
                "description": description,
                "model_used": "gpt-4.1-mini",
                "query": query,
                "success": True
            }            
            
        except Exception as e:
            logger.error(f"Error analyzing image with vision model: {e}")
            return {"error": f"Vision analysis failed: {str(e)}", "success": False}
    
    def _run(
        self,
        file_path: str,
        operation: str = "get_info",
        query: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """
        Analyze image file
        
        Args:
            file_path: Path to the image file
            operation: Operation to perform (get_info, extract_text, get_base64, describe_image, analyze_content)
            query: Optional custom query for vision analysis
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
                base64_string = self._encode_image_to_base64(file_path)
                result = {
                    "base64": base64_string,
                    "success": True
                }
            
            elif operation in ["describe_image", "analyze_content", "vision_analysis"]:
                # Use AI vision to understand the image content
                result = self._analyze_image_with_vision(file_path, query)
            
            elif operation == "comprehensive_analysis":
                # Combine multiple analysis methods
                comprehensive_result = {"success": True, "analyses": {}}
                
                # Get basic info
                if Image:
                    with Image.open(file_path) as img:
                        comprehensive_result["analyses"]["basic_info"] = {
                            "format": img.format,
                            "size": img.size,
                            "width": img.width,
                            "height": img.height,
                        }
                
                # Extract text via OCR
                if Image and pytesseract:
                    with Image.open(file_path) as img:
                        text = pytesseract.image_to_string(img).strip()
                        comprehensive_result["analyses"]["extracted_text"] = text
                
                # AI vision analysis
                vision_result = self._analyze_image_with_vision(file_path, query)
                if vision_result.get("success"):
                    comprehensive_result["analyses"]["ai_description"] = vision_result["description"]
                else:
                    comprehensive_result["analyses"]["ai_description"] = "Vision analysis not available"
                
                result = comprehensive_result
            
            else:
                result = {
                    "error": f"Unknown operation: {operation}. Available operations: get_info, extract_text, get_base64, describe_image, analyze_content, comprehensive_analysis",
                    "success": False
                }
            
            return json.dumps(result, default=str)
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return json.dumps({"error": str(e), "success": False})
    
    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)


# Updated schema for the enhanced tool
class ImageAnalysisSchema(BaseModel):
    file_path: str = Field(description="Path to the image file")
    operation: str = Field(
        default="get_info", 
        description="Operation: get_info, extract_text, get_base64, describe_image, analyze_content, comprehensive_analysis"
    )
    query: Optional[str] = Field(
        None, 
        description="Custom query for vision analysis (e.g., 'Count the number of people in this image')"
    )

ImageAnalysisTool.args_schema = ImageAnalysisSchema

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


def create_file_processing_tools(
    client: PicaClient,   
    uploaded_files: List[Dict[str, Any]],
) -> List[BaseTool]:
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
            tools.append(PDFAnalysisTool(client=client))
        elif file_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            tools.append(ExcelAnalysisTool(client=client))
        elif file_type.startswith('image/'):
            tools.append(ImageAnalysisTool(openai_api_key=openai_api_key, client=client))
    
    return tools
