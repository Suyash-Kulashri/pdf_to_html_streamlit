import streamlit as st
import os
import tempfile
import shutil
import zipfile
import io
import re
from pathlib import Path
import subprocess
import sys
from datetime import datetime

# Import your existing modules
import fitz  # PyMuPDF
import pymupdf4llm
import camelot
import pandas as pd
import pdfplumber
import markdown
from openai import OpenAI
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()

class PDFToHTMLConverter:
    def __init__(self, work_dir, pdf_name):
        self.work_dir = work_dir
        self.pdf_name = pdf_name
        self.pdf_basename = os.path.splitext(pdf_name)[0]
        
        # File paths
        self.pdf_path = os.path.join(work_dir, pdf_name)
        self.image_folder = os.path.join(work_dir, "images")
        self.table_folder = os.path.join(work_dir, "tables_output")
        self.first_page_md = os.path.join(work_dir, "first_page.md")
        self.remaining_pages_md = os.path.join(work_dir, "remaining_pages.md")
        self.first_page_html = os.path.join(work_dir, "first_page_html.html")
        self.final_output = os.path.join(work_dir, f"{self.pdf_basename}_final.html")
        
        # Initialize OpenAI client
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=self.openai_api_key)

    def extract_images(self):
        """Extract images from PDF."""
        try:
            os.makedirs(self.image_folder, exist_ok=True)
            pdf_document = fitz.open(self.pdf_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                image_list = page.get_images(full=True)
                
                for image_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        image_filename = f"{self.pdf_basename}-{page_num}-{image_index}.{image_ext}"
                        image_path = os.path.join(self.image_folder, image_filename)
                        
                        with open(image_path, "wb") as image_file:
                            image_file.write(image_bytes)
                    except Exception as e:
                        st.warning(f"Error extracting image {image_index + 1} on page {page_num + 1}: {e}")
            
            pdf_document.close()
            return True
        except Exception as e:
            st.error(f"Error processing PDF {self.pdf_path}: {e}")
            return False

    def extract_tables(self):
        """Extract tables from PDF using Camelot."""
        try:
            os.makedirs(self.table_folder, exist_ok=True)
            tables = camelot.read_pdf(self.pdf_path, flavor='lattice', pages='all')
            table_positions = {}
            
            for table_idx, table in enumerate(tables, start=1):
                page_num = table.page - 1
                table_html = table.df.to_html(index=False, header=True, classes="pdf-table")
                if table._bbox:
                    rect = fitz.Rect(table._bbox)
                else:
                    rect = fitz.Rect(50, 50, 550, 350)
                table_filename = f"table_{table_idx}_page_{table.page}.html"
                table_path = os.path.join(self.table_folder, table_filename)
                
                with open(table_path, "w", encoding="utf-8") as table_file:
                    table_file.write(table_html)
                
                if page_num not in table_positions:
                    table_positions[page_num] = []
                table_positions[page_num].append((rect, table_filename, table_html))
            
            return table_positions
        except Exception as e:
            st.warning(f"Error extracting tables: {e}")
            return {}

    def convert_pdf_to_markdown(self):
        """Convert PDF to markdown files."""
        try:
            pdf_document = fitz.open(self.pdf_path)
            num_pages = len(pdf_document)
            
            # Convert first page
            first_page_content = pymupdf4llm.to_markdown(
                self.pdf_path,
                pages=[0],
                write_images=True,
                image_path=self.image_folder
            )
            
            with open(self.first_page_md, "w", encoding="utf-8") as md_file:
                md_file.write(first_page_content or "# First Page\n\n(No content extracted)")
            
            # Convert remaining pages
            if num_pages > 1:
                remaining_pages_content = pymupdf4llm.to_markdown(
                    self.pdf_path,
                    pages=list(range(1, num_pages)),
                    write_images=True,
                    image_path=self.image_folder
                )
                
                with open(self.remaining_pages_md, "w", encoding="utf-8") as md_file:
                    md_file.write(remaining_pages_content or "# Remaining Pages\n\n(No content extracted)")
            else:
                with open(self.remaining_pages_md, "w", encoding="utf-8") as md_file:
                    md_file.write("# Remaining Pages\n\n(No additional pages)")
            
            pdf_document.close()
            return True
        except Exception as e:
            st.error(f"Error converting PDF to Markdown: {e}")
            return False

    def process_markdown_images(self, markdown_path):
        """Replace image placeholders in markdown with proper syntax."""
        try:
            with open(markdown_path, "r", encoding="utf-8") as md_file:
                lines = md_file.readlines()

            image_pattern = re.compile(r'\[([^\]]+\.(?:png|jpg|jpeg|gif))\]')
            new_lines = []

            for line in lines:
                image_matches = image_pattern.findall(line)
                for image_filename in image_matches:
                    image_path = os.path.join(self.image_folder, image_filename)
                    if os.path.exists(image_path):
                        image_markdown = f"![{image_filename}]({image_path})"
                        line = line.replace(f'[{image_filename}]', image_markdown)
                
                new_lines.append(line)

            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.writelines(new_lines)
            return True
        except Exception as e:
            st.error(f"Error processing markdown file {markdown_path}: {e}")
            return False

    def extract_image_paths_from_markdown(self, md_content):
        """Extract all image paths from markdown content."""
        image_pattern = r'!\[.*?\]\((.*?)\)'
        matches = re.findall(image_pattern, md_content)
        return matches

    def generate_first_page_html(self, css_content):
        """Generate enhanced first page HTML using OpenAI."""
        try:
            # Read markdown content
            with open(self.first_page_md, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # Extract image paths
            markdown_images = self.extract_image_paths_from_markdown(md_content)
            
            # Create image reference text
            image_reference_text = ""
            if markdown_images:
                image_reference_text = "CRITICAL IMAGE REQUIREMENTS:\n"
                for i, img_path in enumerate(markdown_images, 1):
                    image_reference_text += f"{i}. Image path MUST be exactly: {img_path}\n"
                image_reference_text += "\nDO NOT change these image paths under any circumstances.\n\n"

            prompt = f"""
You are tasked with generating an HTML file that replicates the first page of a PDF document, using content from a Markdown file and styling based on a provided CSS file.

{image_reference_text}

CRITICAL CSS REQUIREMENTS:
- You MUST use the provided CSS exactly as given
- DO NOT modify, remove, or restructure any existing CSS rules
- You may ONLY add new CSS rules if absolutely necessary for layout
- DO NOT change class names, selectors, or existing properties
- Preserve all existing CSS structure and formatting

### Target HTML Structure:
- Header with title, subtitle, and first image
- Main content sections (product description, features, specs table, compliance/safety)
- Proper image placement
- Footer with copyright

### Inputs:
**Markdown Content:**
```
{md_content}
```

**CSS Content (MUST BE USED EXACTLY AS PROVIDED):**
```
{css_content}
```

### STRICT REQUIREMENTS:
1. Image paths MUST match exactly what is provided in the markdown
2. CSS MUST be used exactly as provided
3. DO NOT change existing CSS class names, selectors, or properties
4. Generate complete HTML with embedded CSS

### Output:
Complete HTML content ready for use.
"""

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a highly skilled web developer who follows instructions precisely. You NEVER modify provided CSS or image paths unless explicitly instructed."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.1
            )
            
            html_content = response.choices[0].message.content.strip()
            
            # Clean up markdown code blocks if present
            if html_content.startswith('```html'):
                html_content = html_content[7:]
            if html_content.startswith('```'):
                html_content = html_content[3:]
            if html_content.endswith('```'):
                html_content = html_content[:-3]
            
            # Save generated HTML
            with open(self.first_page_html, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return True
        except Exception as e:
            st.error(f"Error generating first page HTML: {e}")
            return False

    def group_images_in_rows(self, md_content):
        """Group images in rows of 3."""
        img_pattern = r'!\[.*?\]\((.*?)\)'
        lines = md_content.split('\n')
        new_lines = []
        buffer = []

        for line in lines:
            match = re.match(img_pattern, line.strip())
            if match:
                img_src = match.group(1)
                buffer.append(f'<img src="{img_src}" alt="" />')
                if len(buffer) == 3:
                    new_lines.append('<div class="image-row">\n' + '\n'.join(buffer) + '\n</div>')
                    buffer = []
            else:
                if buffer:
                    new_lines.append('<div class="image-row">\n' + '\n'.join(buffer) + '\n</div>')
                    buffer = []
                new_lines.append(line)
        if buffer:
            new_lines.append('<div class="image-row">\n' + '\n'.join(buffer) + '\n</div>')
        return '\n'.join(new_lines)

    def create_integrated_html(self, css_content):
        """Create final integrated HTML."""
        try:
            # Extract first page content
            with open(self.first_page_html, 'r', encoding='utf-8') as f:
                first_page_html = f.read()
            
            soup = BeautifulSoup(first_page_html, 'html.parser')
            
            # Extract styles
            style_tag = soup.find('style')
            first_page_styles = style_tag.get_text() if style_tag else ""
            
            # Extract body content
            body_tag = soup.find('body')
            if body_tag:
                first_page_body = str(body_tag)
                first_page_body = re.sub(r'^<body[^>]*>', '', first_page_body)
                first_page_body = re.sub(r'</body>$', '', first_page_body)
            else:
                if style_tag:
                    style_tag.decompose()
                first_page_body = str(soup)
            
            # Read remaining pages
            with open(self.remaining_pages_md, 'r', encoding='utf-8') as f:
                remaining_content = f.read()
            
            # Remove footer text
            text_to_remove = r"""For international contact information,.*?\bAdvanced Energy Industries, Inc\.""".strip()
            remaining_content = re.sub(rf'{text_to_remove}\s*$', '', remaining_content, flags=re.DOTALL | re.MULTILINE).strip()
            
            # Group images and convert to HTML
            remaining_grouped = self.group_images_in_rows(remaining_content)
            remaining_html = markdown.markdown(remaining_grouped, extensions=['extra', 'codehilite'])
            
            # Footer content
            footer_content = """
Advanced Energy (AE) has devoted more than three decades to perfecting power for its global customers. AE designs and manufactures highly engineered, precision power conversion, measurement and control solutions for mission-critical applications and processes.

Our products enable customer innovation in complex applications for a wide range of industries including semiconductor equipment, industrial, manufacturing, telecommunications, data center computing, and medical. With deep applications know-how and responsive service and support across the globe, we build collaborative partnerships to meet rapid technological developments, propel growth for our customers, and innovate the future of power.

For international contact information, visit advancedenergy.com.

powersales@aei.com (Sales Support)  
productsupport.ep@aei.com (Technical Support)  +1 888 412 7832

Specifications are subject to change without notice. Not responsible for errors or omissions. ©2020 Advanced Energy Industries, Inc. All rights reserved. Advanced Energy®, and AE® are U.S. trademarks of Advanced Energy Industries, Inc."""
            
            footer_html = markdown.markdown(footer_content, extensions=['extra', 'codehilite'])
            
            # Extract page title
            h1_tag = soup.find('h1')
            page_title = h1_tag.get_text().strip() if h1_tag else self.pdf_basename
            
            # Combine CSS
            combined_css = css_content
            if first_page_styles:
                combined_css += "\n\n/* First Page Specific Styles */\n" + first_page_styles
            
            # Create final HTML
            final_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <style>
{combined_css}
    </style>
</head>
<body>
<!-- First Page Section -->
<div class="section first-page-section">
    {first_page_body.strip()}
</div>

<!-- Remaining Pages Section -->
<div class="section remaining-pages-section">
    <main>
        {remaining_html}
    </main>
</div>

<!-- Footer Section -->
<div class="section footer-section">
    <h2 align="center">ABOUT ADVANCED ENERGY</h2>
    <footer class="footer">
        {footer_html}
    </footer>
</div>
</body>
</html>"""
            
            with open(self.final_output, 'w', encoding='utf-8') as f:
                f.write(final_html)
            
            return True
        except Exception as e:
            st.error(f"Error creating integrated HTML: {e}")
            return False

    def cleanup_intermediate_files(self):
        """Clean up intermediate files."""
        files_to_remove = [
            self.first_page_md,
            self.remaining_pages_md,
            self.first_page_html
        ]
        
        dirs_to_remove = [
            self.table_folder
        ]
        
        for file_path in files_to_remove:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                st.warning(f"Could not remove {file_path}: {e}")
        
        for dir_path in dirs_to_remove:
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            except Exception as e:
                st.warning(f"Could not remove directory {dir_path}: {e}")

def create_download_zip(work_dir, pdf_basename):
    """Create a zip file with HTML and images for download."""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add HTML file
        html_file = os.path.join(work_dir, f"{pdf_basename}_final.html")
        if os.path.exists(html_file):
            zip_file.write(html_file, f"{pdf_basename}_final.html")
        
        # Add images folder
        images_dir = os.path.join(work_dir, "images")
        if os.path.exists(images_dir):
            for root, dirs, files in os.walk(images_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, work_dir)
                    zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    return zip_buffer

def main():
    st.set_page_config(
        page_title="PDF to HTML Converter",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 PDF to HTML Converter")
    st.markdown("Convert your PDF documents to structured HTML with enhanced first page styling using AI.")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.warning("Please set your OpenAI API Key in the environment variables for security.")
            st.text_input(
                "OpenAI API Key",
                value=api_key,
                type="password",
                help="Enter your OpenAI API key for enhanced first page generation"
            )

        # # OpenAI API Key input
        # api_key = st.text_input(
        #     "OpenAI API Key",
        #     type="password",
        #     help="Enter your OpenAI API key for enhanced first page generation"
        # )
        
        # if api_key:
        #     api_key = os.getenv("OPENAI_API_KEY")

        st.markdown("---")
        st.markdown("### 📋 Requirements")
        st.markdown("""
        - Upload a PDF file
        - Provide CSS files for styling
        - Header image (optional)
        """)
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📁 File Upload")
        
        # PDF Upload
        uploaded_pdf = st.file_uploader(
            "Choose a PDF file",
            type=['pdf'],
            help="Upload the PDF you want to convert to HTML"
        )
        
        # CSS Files Upload
        st.subheader("🎨 CSS Files")
        first_page_css = st.file_uploader(
            "First Page CSS (first_page.css)",
            type=['css'],
            help="CSS file for styling the first page"
        )
        
        main_css = st.file_uploader(
            "Main CSS (pdf_styles.css)",
            type=['css'],
            help="Main CSS file for overall styling"
        )
        
        # Header Image Upload
        header_image = st.file_uploader(
            "Header Image (advance_energy.png)",
            type=['png', 'jpg', 'jpeg'],
            help="Header image for the document (optional)"
        )
    
    with col2:
        st.header("ℹ️ Process Info")
        st.info("""
        **Process Steps:**
        1. Extract images and tables from PDF
        2. Convert PDF to Markdown
        3. Generate enhanced first page with AI
        4. Create integrated HTML
        5. Package for download
        """)
        
        if uploaded_pdf:
            st.success(f"📄 PDF: {uploaded_pdf.name}")
        if first_page_css:
            st.success(f"🎨 First Page CSS: {first_page_css.name}")
        if main_css:
            st.success(f"🎨 Main CSS: {main_css.name}")
        if header_image:
            st.success(f"🖼️ Header Image: {header_image.name}")
    
    # Process button
    st.markdown("---")
    
    if st.button("🚀 Convert PDF to HTML", type="primary", use_container_width=True):
        if not uploaded_pdf:
            st.error("Please upload a PDF file!")
            return
        
        if not first_page_css or not main_css:
            st.error("Please upload both CSS files!")
            return
        
        if not os.getenv("OPENAI_API_KEY"):
            st.error("Please provide OpenAI API Key in the sidebar!")
            return
        
        # Create temporary working directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Save uploaded files
                pdf_name = uploaded_pdf.name
                pdf_path = os.path.join(temp_dir, pdf_name)
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_pdf.getvalue())
                
                first_page_css_path = os.path.join(temp_dir, "first_page.css")
                with open(first_page_css_path, "w") as f:
                    f.write(first_page_css.getvalue().decode("utf-8"))
                
                main_css_path = os.path.join(temp_dir, "pdf_styles.css")
                main_css_content = main_css.getvalue().decode("utf-8")
                with open(main_css_path, "w") as f:
                    f.write(main_css_content)
                
                if header_image:
                    header_path = os.path.join(temp_dir, "advance_energy.png")
                    with open(header_path, "wb") as f:
                        f.write(header_image.getvalue())
                
                # Initialize converter
                converter = PDFToHTMLConverter(temp_dir, pdf_name)
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Step 1: Extract images
                status_text.text("🖼️ Extracting images from PDF...")
                progress_bar.progress(10)
                if not converter.extract_images():
                    st.error("Failed to extract images!")
                    return
                
                # Step 2: Extract tables
                status_text.text("📊 Extracting tables from PDF...")
                progress_bar.progress(20)
                table_positions = converter.extract_tables()
                
                # Step 3: Convert to markdown
                status_text.text("📝 Converting PDF to Markdown...")
                progress_bar.progress(40)
                if not converter.convert_pdf_to_markdown():
                    st.error("Failed to convert PDF to Markdown!")
                    return
                
                # Step 4: Process markdown images
                status_text.text("🔄 Processing markdown images...")
                progress_bar.progress(50)
                converter.process_markdown_images(converter.first_page_md)
                converter.process_markdown_images(converter.remaining_pages_md)
                
                # Step 5: Generate first page HTML
                status_text.text("🤖 Generating enhanced first page with AI...")
                progress_bar.progress(70)
                with open(first_page_css_path, 'r') as f:
                    first_css_content = f.read()
                if not converter.generate_first_page_html(first_css_content):
                    st.error("Failed to generate first page HTML!")
                    return
                
                # Step 6: Create integrated HTML
                status_text.text("🔗 Creating integrated HTML...")
                progress_bar.progress(90)
                if not converter.create_integrated_html(main_css_content):
                    st.error("Failed to create integrated HTML!")
                    return
                
                # Step 7: Finalize
                status_text.text("✅ Finalizing...")
                progress_bar.progress(100)
                
                # Create download package
                pdf_basename = os.path.splitext(pdf_name)[0]
                zip_buffer = create_download_zip(temp_dir, pdf_basename)
                
                # Clean up intermediate files
                converter.cleanup_intermediate_files()
                
                # Success message
                st.success("🎉 Conversion completed successfully!")
                
                # Download buttons
                col1, col2 = st.columns(2)
                
                with col1:
                    with open(converter.final_output, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    st.download_button(
                        label="📄 Download HTML File",
                        data=html_content,
                        file_name=f"{pdf_basename}_final.html",
                        mime="text/html",
                        use_container_width=True
                    )
                
                with col2:
                    st.download_button(
                        label="📦 Download Complete Package",
                        data=zip_buffer.getvalue(),
                        file_name=f"{pdf_basename}_complete.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                
                # Preview section
                st.markdown("---")
                st.header("👀 Preview")
                
                # Show HTML preview in expandable section
                with st.expander("🔍 View HTML Source", expanded=False):
                    st.code(html_content[:2000] + "..." if len(html_content) > 2000 else html_content, language="html")
                
                # Display success metrics
                st.markdown("### 📊 Conversion Statistics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    image_count = len([f for f in os.listdir(converter.image_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))])
                    st.metric("Images Extracted", image_count)
                
                with col2:
                    html_size = len(html_content)
                    st.metric("HTML Size", f"{html_size:,} chars")
                
                with col3:
                    st.metric("Status", "✅ Complete")
                
            except Exception as e:
                st.error(f"An error occurred during conversion: {str(e)}")
                st.exception(e)

if __name__ == "__main__":
    main()