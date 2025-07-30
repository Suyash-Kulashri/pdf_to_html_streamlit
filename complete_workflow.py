import os
import subprocess
import sys
import re
from integrated_html_generator import create_integrated_html
from css_validator import run_full_validation

def run_script(script_name, description):
    """Run a Python script and handle errors."""
    print(f"\n{'='*50}")
    print(f"Running {description}...")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, text=True, check=True)
        print(f"✅ {description} completed successfully!")
        if result.stdout:
            print("Output:", result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed!")
        print("Error:", e.stderr if e.stderr else e.stdout)
        return False
    except FileNotFoundError:
        print(f"❌ Script {script_name} not found!")
        return False

def check_file_exists(filepath, description):
    """Check if a file exists and print status."""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ Missing {description}: {filepath}")
        return False

def main():
    """Complete workflow to generate integrated HTML from PDF."""
    print("🚀 Starting Complete PDF to HTML Workflow")
    print("=" * 60)
    
    # Step 1: Check if required input files exist
    print("\n📋 Checking input files...")
    required_files = {
        "LCM300.pdf": "PDF file",
        "first_page.css": "First page CSS",
        "pdf_styles.css": "Main CSS file",
        "advance_energy.png": "Header image"
    }
    
    all_files_exist = True
    for filepath, description in required_files.items():
        if not check_file_exists(filepath, description):
            all_files_exist = False
    
    if not all_files_exist:
        print("\n❌ Some required files are missing. Please ensure all files exist.")
        return False
    
    # Step 2: Run pdf_to_markdown.py
    if not run_script("pdf_to_markdown.py", "PDF to Markdown conversion"):
        return False
    
    # Step 3: Check if markdown files were created
    print("\n📋 Checking markdown files...")
    markdown_files = ["first_page.md", "remaining_pages.md"]
    for md_file in markdown_files:
        if not check_file_exists(md_file, f"Markdown file"):
            print(f"❌ Markdown conversion may have failed. {md_file} not found.")
            return False
    
    # Step 4: Run first_page.py to generate enhanced first page
    if not run_script("first_page.py", "First page HTML generation"):
        return False
    
    # Step 5: Check if first page HTML was created
    if not check_file_exists("first_page_html.html", "First page HTML"):
        print("❌ First page HTML generation may have failed.")
        return False
    
    # Step 5.5: Validate first page HTML
    print(f"\n{'='*50}")
    print("Validating first page HTML...")
    print(f"{'='*50}")
    
    # Extract expected images from markdown
    expected_images = []
    if os.path.exists("first_page.md"):
        with open("first_page.md", 'r', encoding='utf-8') as f:
            md_content = f.read()
        image_pattern = r'!\[.*?\]\((.*?)\)'
        expected_images = re.findall(image_pattern, md_content)
    
    validation_passed = run_full_validation(
        original_css_path="first_page.css",
        expected_images=expected_images,
        generated_html_path="first_page_html.html"
    )
    
    if not validation_passed:
        print("⚠️ Validation issues detected, but continuing with integration...")
    else:
        print("✅ First page HTML validation passed!")
    
    # Step 6: Create integrated HTML
    print(f"\n{'='*50}")
    print("Creating integrated HTML...")
    print(f"{'='*50}")
    
    try:
        create_integrated_html(
            first_page_html_path="first_page_html.html",
            remaining_pages_md_path="remaining_pages.md",
            css_file_path="pdf_styles.css",
            output_html_path="final_integrated_output.html",
            image_file_path="advance_energy.png"
        )
        print("✅ Integrated HTML created successfully!")
    except Exception as e:
        print(f"❌ Integration failed: {str(e)}")
        return False
    
    # Step 7: Final verification
    print(f"\n{'='*50}")
    print("Final verification...")
    print(f"{'='*50}")
    
    output_files = {
        "first_page.md": "First page markdown",
        "remaining_pages.md": "Remaining pages markdown", 
        "first_page_html.html": "Enhanced first page HTML",
        "final_integrated_output.html": "Final integrated HTML"
    }
    
    all_outputs_exist = True
    for filepath, description in output_files.items():
        if not check_file_exists(filepath, description):
            all_outputs_exist = False
    
    if all_outputs_exist:
        print(f"\n🎉 Workflow completed successfully!")
        print(f"📄 Your final HTML file: final_integrated_output.html")
        print(f"📂 Open it in a web browser to view the result.")
        return True
    else:
        print(f"\n❌ Workflow completed with some missing outputs.")
        return False

def cleanup_intermediate_files():
    """Optional: Clean up intermediate files."""
    intermediate_files = [
        "modified.pdf",
        "output_with_css.html",
        "output.html"
    ]
    
    print(f"\n🧹 Cleaning up intermediate files...")
    for file in intermediate_files:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"🗑️  Removed: {file}")
            except Exception as e:
                print(f"⚠️  Could not remove {file}: {e}")

if __name__ == "__main__":
    success = main()
    
    if success:
        # Ask user if they want to clean up intermediate files
        cleanup_choice = input("\n🧹 Do you want to clean up intermediate files? (y/n): ").lower().strip()
        if cleanup_choice in ['y', 'yes']:
            cleanup_intermediate_files()
        
        print(f"\n✨ All done! Your integrated HTML is ready at: final_integrated_output.html")
    else:
        print(f"\n💥 Workflow failed. Please check the errors above and try again.")
        sys.exit(1)