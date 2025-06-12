from typing import List, Dict, Any

def generate_file_processing_instructions(uploaded_files: List[Dict[str, Any]]) -> str:
    """
    Generate instructions for the agent on how to use file processing tools.
    
    Args:
        uploaded_files: List of uploaded file information
        
    Returns:
        Instructions string for the agent
    """
    file_types = set()
    file_list = []
    
    for file_info in uploaded_files:
        content_type = file_info.get('type', '').lower()
        filename = file_info.get('name', 'unknown')
        file_path = file_info.get('path', '')
        
        file_list.append(f"- {filename} ({content_type}) at path: {file_path}")
        
        if 'pdf' in content_type:
            file_types.add('PDF')
        elif content_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            file_types.add('Excel')
        elif content_type.startswith('image/'):
            file_types.add('Image')
    
    instructions = f"""

FILE PROCESSING CAPABILITIES:
You have access to LOCAL file processing tools that work DIFFERENTLY from Pica platform tools.
These tools do NOT require platform connections and should be used DIRECTLY when users ask about uploaded files.

UPLOADED FILES:
{chr(10).join(file_list)}

IMPORTANT: File processing tools are LOCAL tools, not Pica platform tools:
- Do NOT use getAvailableActions, getActionKnowledge, or execute for file processing
- Do NOT treat file processing as platform connections
- Use file processing tools DIRECTLY when users ask about files

AVAILABLE FILE PROCESSING TOOLS:
"""
    
    if 'PDF' in file_types:
        instructions += """
- analyze_pdf: Process PDF files directly
  * Operations: extract_text, get_info, search
  * Usage: analyze_pdf(file_path="/path/to/file.pdf", operation="extract_text")
  * No connection required - this is a local tool
"""
    
    if 'Excel' in file_types:
        instructions += """
- analyze_excel: Process Excel files directly  
  * Operations: get_info, extract_data, summary_stats, search
  * Usage: analyze_excel(file_path="/path/to/file.xlsx", operation="get_info")
  * No connection required - this is a local tool
"""
    
    if 'Image' in file_types:
        instructions += """
- Image Analysis: Use analyze_image with operations:
  * get_info: Get image properties (dimensions, format, mode)
  * extract_text: Extract text from images using OCR
  * describe_image: General AI vision analysis to understand image content
  * analyze_content: IMPORTANT - Use this when user asks specific questions about the image
  * comprehensive_analysis: Combined OCR + AI vision + basic info

CRITICAL for Image Analysis:

When user asks specific questions about an image (e.g., "Who is this person?", "What are they doing?", "How many people?"), use analyze_content operation
ALWAYS pass the user's exact question as the query parameter when using analyze_content
Example: If user asks "Who are the people in this image?", call analyze_image with operation="analyze_content" and query="Who are the people in this image?"

Process:

Always specify the correct file_path parameter when calling these tools
For specific image questions, use analyze_content with the user's question as query
Choose appropriate operation based on user's request
Summarize findings in a clear, actionable format
Reference files by their original filename when responding

Example Tool Calls:

User: "Who is in this image?" → analyze_image(file_path="...", operation="analyze_content", query="Who is in this image?")
User: "Count the cars" → analyze_image(file_path="...", operation="analyze_content", query="Count the cars")
User: "What do you see?" → analyze_image(file_path="...", operation="describe_image")
"""
    
    instructions += """
WORKFLOW FOR FILE PROCESSING:
1. When user asks about uploaded files, use file processing tools DIRECTLY
2. Do NOT follow the Pica platform workflow (getAvailableActions -> getActionKnowledge -> execute)
3. File processing tools work independently and immediately
4. Only use Pica platform workflow for actual platform integrations (Gmail, Slack, etc.)

EXAMPLES:
- "Analyze this PDF" → Use analyze_pdf tool directly
- "What's in the Excel file?" → Use analyze_excel tool directly  
- "Extract text from image" → Use analyze_image tool directly
- "Send an email" → Use Pica platform workflow (getAvailableActions for gmail, etc.)
"""
    
    return instructions

