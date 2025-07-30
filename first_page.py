import pdfplumber
import markdown
import os
from openai import OpenAI
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Initialize OpenAI client with API key from environment
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

client = OpenAI(api_key=openai_api_key)

def extract_pdf_first_page(pdf_path):
    """Extract text and image references from the first page of a PDF."""
    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return "", []
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            # Extract image references (assuming placeholders like [Image: filename])
            images = []
            lines = text.split('\n')
            for line in lines:
                if line.startswith('[Image:') and line.endswith(']'):
                    image_name = line.strip('[]').replace('Image:', '').strip()
                    images.append(image_name)
            # If no placeholders found, check for actual images
            if not images and hasattr(first_page, 'images'):
                for i, _ in enumerate(first_page.images):
                    images.append(f"images/{os.path.splitext(os.path.basename(pdf_path))[0]}-0-{i}.png")
            return text, images
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return "", []

def read_markdown(md_path):
    """Read content from a Markdown file."""
    try:
        if not os.path.exists(md_path):
            raise FileNotFoundError(f"Markdown file not found: {md_path}")
        with open(md_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading Markdown: {e}")
        return ""

def read_css(css_path):
    """Read content from a CSS file."""
    try:
        if not os.path.exists(css_path):
            raise FileNotFoundError(f"CSS file not found: {css_path}")
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading CSS: {e}")
        return ""

def extract_image_paths_from_markdown(md_content):
    """Extract all image paths from markdown content."""
    image_pattern = r'!\[.*?\]\((.*?)\)'
    matches = re.findall(image_pattern, md_content)
    return matches

def validate_and_fix_html(html_content, expected_images, original_css):
    """Validate and fix HTML to ensure correct image paths and CSS preservation."""
    
    # Extract image paths from HTML
    html_img_pattern = r'src=["\']([^"\']*)["\']'
    html_images = re.findall(html_img_pattern, html_content)
    
    # Check if images in HTML match expected images
    for expected_img in expected_images:
        found = False
        for html_img in html_images:
            if expected_img in html_img or html_img in expected_img:
                found = True
                break
        
        if not found:
            print(f"Warning: Expected image {expected_img} not found in generated HTML")
    
    # Ensure CSS is preserved - extract CSS from HTML
    css_pattern = r'<style>(.*?)</style>'
    css_match = re.search(css_pattern, html_content, re.DOTALL)
    
    if css_match:
        generated_css = css_match.group(1).strip()
        # Replace the CSS section with original CSS + any additional styles
        if generated_css != original_css.strip():
            print("Warning: CSS was modified by LLM. Preserving original CSS structure.")
            # Keep original CSS and append any new styles that don't conflict
            html_content = re.sub(
                css_pattern,
                f'<style>\n{original_css}\n</style>',
                html_content,
                flags=re.DOTALL
            )
    
    return html_content

def generate_html(pdf_path, md_path, css_path, output_path):
    """Generate HTML using OpenAI API based on PDF, Markdown, and CSS inputs."""
    # Extract content from inputs
    pdf_text, pdf_images = extract_pdf_first_page(pdf_path)
    md_content = read_markdown(md_path)
    css_content = read_css(css_path)
    
    # Extract image paths from markdown
    markdown_images = extract_image_paths_from_markdown(md_content)
    
    # Create a comprehensive list of all expected images
    all_expected_images = list(set(pdf_images + markdown_images))
    
    # Create image reference list for the prompt
    image_reference_text = ""
    if all_expected_images:
        image_reference_text = "CRITICAL IMAGE REQUIREMENTS:\n"
        for i, img_path in enumerate(all_expected_images, 1):
            image_reference_text += f"{i}. Image path MUST be exactly: {img_path}\n"
        image_reference_text += "\nDO NOT change these image paths under any circumstances.\n\n"

    # Prepare prompt for OpenAI
    prompt = f"""
You are tasked with generating an HTML file that replicates the first page of a PDF document, using content from a Markdown file and styling based on a provided CSS file. The PDF follows a consistent format (header with title/subtitle, product description, features list, specs table, compliance/safety lists, and images) but with varying content.

{image_reference_text}

CRITICAL CSS REQUIREMENTS:
- You MUST use the provided CSS exactly as given
- DO NOT modify, remove, or restructure any existing CSS rules
- You may ONLY add new CSS rules if absolutely necessary for layout
- DO NOT change class names, selectors, or existing properties
- Preserve all existing CSS structure and formatting

### Target HTML Structure and Requirements:
- **Header**: A grey background div containing:
  - An `<h1>` with the main title (e.g., product name from PDF/Markdown).
  - An `<h2>` with a subtitle (e.g., product specification from PDF/Markdown).
  - The first image (from PDF images) positioned to the right of the `<h1>`.
  - Keep the name and path of the images exactly as provided in the image reference list above.
- **Main Content**:
  - A section with a title (e.g., "PRODUCT DESCRIPTION") and a paragraph of text from PDF or Markdown.
  - A "SPECIAL FEATURES" section with a `<ul>` of features (bullet points) from PDF or Markdown.
  - An "AT A GLANCE" table summarizing key specs (e.g., Total Power, Input Voltage, # of Outputs) from PDF or Markdown.
  - A "COMPLIANCE" and "SAFETY" section displayed side-by-side using flexbox, with `<ul>` lists from PDF or Markdown.
- **Images**: Use the exact image paths as specified in the image reference list above. DO NOT modify these paths.
- **Footer**: A copyright notice (e.g., "©2025 Company Name") from PDF or Markdown.
- **Styling**:
  - Container: max-width 816px, white background, padding, subtle box-shadow.
  - Use the provided CSS EXACTLY as given - do not modify existing rules.

### Inputs:
**PDF First Page Content:**
Text:
```
{pdf_text}
```

**Expected Image Paths (USE EXACTLY AS LISTED):**
```
{chr(10).join(all_expected_images)}
```

**Markdown Content (first_page.md):**
```
{md_content}
```

**CSS Content (MUST BE USED EXACTLY AS PROVIDED):**
```
{css_content}
```

### STRICT REQUIREMENTS:
1. Image paths MUST match exactly what is provided in the "Expected Image Paths" section
2. CSS MUST be used exactly as provided - only add new rules if absolutely necessary
3. DO NOT change existing CSS class names, selectors, or properties
4. DO NOT rename or modify image file paths
5. Prioritize Markdown for text content but use PDF for image references if conflicting

### Instructions:
- Generate a complete HTML file (`first_page_html.html`) integrating PDF and Markdown content with CSS styling.
- Match the described layout: header (grey background, `<h1>`, `<h2>`, first image on right), content sections, remaining images appropriately placed, footer.
- Use image filenames EXACTLY as provided in the expected image paths list.
- Use the CSS EXACTLY as provided without modifications to existing rules.
- Output only the HTML content with `<style>` tag containing the original CSS.
- Do not include explanations or comments outside the HTML code.

### Output:
Complete HTML content, including `<style>` tag with the original CSS (unmodified), ready for `first_page_html.html`.
"""

    try:
        # Call OpenAI API to generate HTML
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a highly skilled web developer who follows instructions precisely. You NEVER modify provided CSS or image paths unless explicitly instructed. You preserve all original styling and file references exactly as given."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.1  # Lower temperature for more consistent output
        )
        html_content = response.choices[0].message.content.strip()
        
        # Remove any markdown code block markers if present
        if html_content.startswith('```html'):
            html_content = html_content[7:]
        if html_content.startswith('```'):
            html_content = html_content[3:]
        if html_content.endswith('```'):
            html_content = html_content[:-3]
        
        # Validate and fix the generated HTML
        html_content = validate_and_fix_html(html_content, all_expected_images, css_content)

        # Save the generated HTML to output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML file generated successfully at {output_path}")
        
        # Validate the output
        print("\n=== Validation Results ===")
        print(f"Expected images: {len(all_expected_images)}")
        for img in all_expected_images:
            if img in html_content:
                print(f"✅ Image found: {img}")
            else:
                print(f"❌ Image missing: {img}")
        
        # Check if CSS was preserved
        if css_content.strip() in html_content:
            print("✅ Original CSS preserved")
        else:
            print("⚠️ CSS may have been modified")
            
    except Exception as e:
        print(f"Error generating HTML with OpenAI: {e}")

if __name__ == "__main__":
    # Define file paths
    pdf_path = "LCM300.pdf"
    md_path = "first_page.md"
    css_path = "first_page.css"
    output_path = "first_page_html.html"

    # Validate input files
    for path in [pdf_path, md_path, css_path]:
        if not os.path.exists(path):
            print(f"Error: File not found - {path}")
            exit(1)

    # Generate HTML
    generate_html(pdf_path, md_path, css_path, output_path)