"""
Fixed file processing demonstration for pica-langchain.
This version properly handles file lifecycle and cleanup.
"""

import os
import sys
import asyncio
import tempfile
import shutil
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain.agents import AgentType
from pica_langchain import PicaClient, create_pica_agent
from pica_langchain.models import PicaClientOptions

# Try to import file processing dependencies
try:
    import pandas as pd
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Missing dependencies for file processing: {e}")
    print("Install with: pip install pandas openpyxl Pillow reportlab")
    DEPENDENCIES_AVAILABLE = False


def get_env_var(name: str) -> str:
    """Get environment variable or exit if not set."""
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: {name} environment variable must be set")
        sys.exit(1)
    return value


def create_sample_pdf(file_path: str):
    """Create a sample PDF file for testing."""
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter
    
    # Add content
    c.drawString(100, height - 100, "Sample PDF Document")
    c.drawString(100, height - 130, "This is a test document for file processing demonstration.")
    c.drawString(100, height - 160, "It contains test content and structured data.")
    c.drawString(100, height - 220, "Key Information:")
    c.drawString(120, height - 250, "• Document Type: Test PDF")
    c.drawString(120, height - 280, "• Created by: Pica LangChain Example")
    c.drawString(120, height - 310, "• Purpose: Demonstrate PDF analysis")
    c.drawString(100, height - 380, "This document can be analyzed for text extraction and search.")
    
    c.showPage()
    c.save()
    print(f"✅ Created sample PDF: {os.path.basename(file_path)}")


def create_sample_excel(file_path: str):
    """Create a sample Excel file for testing."""
    data = {
        'Product': ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Speakers'],
        'Category': ['Electronics', 'Accessories', 'Accessories', 'Electronics', 'Electronics'],
        'Price': [999.99, 29.99, 79.99, 299.99, 149.99],
        'Stock': [50, 200, 150, 75, 100],
        'Rating': [4.5, 4.2, 4.7, 4.3, 4.1]
    }
    
    df = pd.DataFrame(data)
    
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Products', index=False)
        
        summary_data = {
            'Metric': ['Total Products', 'Average Price', 'Total Stock', 'Average Rating'],
            'Value': [len(df), df['Price'].mean(), df['Stock'].sum(), df['Rating'].mean()]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    print(f"✅ Created sample Excel: {os.path.basename(file_path)}")


def create_sample_image(file_path: str):
    """Create a sample image file for testing."""
    width, height = 400, 300
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype("Arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    text_lines = [
        "Sample Image for OCR",
        "",
        "This image contains text that can",
        "be extracted using OCR capabilities.",
        "",
        "Text Recognition Test:",
        "• Line 1: Hello World",
        "• Line 2: File Processing",
        "• Line 3: LangChain Tools"
    ]
    
    y_position = 30
    for line in text_lines:
        draw.text((20, y_position), line, fill='black', font=font)
        y_position += 25
    
    draw.rectangle([20, 220, 380, 270], outline='blue', width=2)
    draw.text((30, 235), "This is a bordered text box for testing", fill='blue', font=font)
    
    image.save(file_path)
    print(f"✅ Created sample image: {os.path.basename(file_path)}")


class FileManager:
    """Manages temporary files for the demonstration."""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="pica_file_demo_")
        self.files = {}
        print(f"📁 Created temporary directory: {self.temp_dir}")
    
    def create_sample_files(self):
        """Create all sample files."""
        if not DEPENDENCIES_AVAILABLE:
            return
        
        self.files['pdf'] = os.path.join(self.temp_dir, "sample_document.pdf")
        self.files['excel'] = os.path.join(self.temp_dir, "sample_data.xlsx")
        self.files['image'] = os.path.join(self.temp_dir, "sample_image.png")
        
        create_sample_pdf(self.files['pdf'])
        create_sample_excel(self.files['excel'])
        create_sample_image(self.files['image'])
    
    def get_uploaded_files_info(self):
        """Get file info in the format expected by the agent."""
        return [
            {
                'path': self.files['pdf'],
                'type': 'application/pdf',
                'name': 'sample_document.pdf'
            },
            {
                'path': self.files['excel'],
                'type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'name': 'sample_data.xlsx'
            },
            {
                'path': self.files['image'],
                'type': 'image/png',
                'name': 'sample_image.png'
            }
        ]
    
    def cleanup(self):
        """Clean up all temporary files."""
        try:
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")


async def run_test_scenario(agent, scenario_num, description, query):
    """Run a single test scenario."""
    print(f"\n{'='*60}")
    print(f"TEST {scenario_num}: {description}")
    print("="*60)
    print(f"Query: {query}")
    print("\nAgent Response:")
    print("-" * 40)
    
    try:
        result = await agent.ainvoke({"input": query})
        print(result['output'])
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        print("-" * 40)


async def main():
    """Main function to run the file processing demonstration."""
    print("🎯 Pica LangChain File Processing Demonstration (Fixed)")
    print("=" * 60)
    
    if not DEPENDENCIES_AVAILABLE:
        print("❌ Required dependencies are not installed.")
        print("Install them with:")
        print("pip install pandas openpyxl Pillow reportlab pytesseract PyPDF2 langchain-community")
        return
    
    # Initialize file manager
    file_manager = FileManager()
    
    try:
        # Create sample files
        file_manager.create_sample_files()
        uploaded_files = file_manager.get_uploaded_files_info()
        
        # Verify files exist
        for file_info in uploaded_files:
            if not os.path.exists(file_info['path']):
                print(f"❌ File not found: {file_info['path']}")
                return
            else:
                print(f"✅ File verified: {file_info['name']}")
        
        print("\n" + "="*60)
        print("STARTING FILE PROCESSING DEMONSTRATION")
        print("="*60)
        
        # Create Pica client
        pica_client = await PicaClient.create(
            secret=get_env_var("PICA_SECRET"),
            options=PicaClientOptions(),
        )

        llm = ChatOpenAI(
            temperature=0,
            model="gpt-4o",
        )

        # Create agent with file processing capabilities
        agent = create_pica_agent(
            client=pica_client,
            llm=llm,
            agent_type=AgentType.OPENAI_FUNCTIONS,
            uploaded_files=uploaded_files,
        )
        
        # Test scenarios
        test_scenarios = [
            {
                "description": "📄 PDF Analysis - Extract text content",
                "query": f"Please analyze the PDF file at {file_manager.files['pdf']}. Extract all the text content and tell me what the document is about."
            },
            {
                "description": "📊 Excel Analysis - Get spreadsheet overview", 
                "query": f"Analyze the Excel file at {file_manager.files['excel']}. Tell me about the structure, what sheets are available, and provide a summary of the data."
            },
            {
                "description": "📊 Excel Analysis - Calculate statistics",
                "query": f"From the Excel file at {file_manager.files['excel']}, calculate the total value of all products (price * stock) and find the product with the highest rating."
            },
            {
                "description": "🖼️ Image Analysis - Extract text via OCR",
                "query": f"Analyze the image at {file_manager.files['image']}. Extract any text you can find and tell me what the image contains."
            },
            {
                "description": "🔍 Multi-file Analysis",
                "query": "Give me a comprehensive summary of all the uploaded files. What types of files are they and what information do they contain?"
            }
        ]
        
        # Run tests
        success_count = 0
        for i, scenario in enumerate(test_scenarios, 1):
            success = await run_test_scenario(
                agent, i, scenario['description'], scenario['query']
            )
            if success:
                success_count += 1
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        print(f"\n{'='*60}")
        print(f"DEMONSTRATION COMPLETED: {success_count}/{len(test_scenarios)} tests successful")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n🛑 Demonstration interrupted by user.")
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Always cleanup
        file_manager.cleanup()


if __name__ == "__main__":
    import signal

    def handle_sigterm(*args):
        print("\n🛑 Received shutdown signal. Cleaning up...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    # Check environment variables
    try:
        get_env_var("PICA_SECRET")
        get_env_var("OPENAI_API_KEY")
    except SystemExit:
        print("\n📝 Required environment variables:")
        print("   - PICA_SECRET: Your Pica API secret")
        print("   - OPENAI_API_KEY: Your OpenAI API key")
        sys.exit(1)

    asyncio.run(main())
