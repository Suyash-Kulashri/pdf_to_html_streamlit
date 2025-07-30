import re
import os

def extract_css_selectors(css_content):
    """Extract all CSS selectors from CSS content."""
    # Remove comments
    css_content = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    
    # Find all selectors (text before opening brace)
    selector_pattern = r'([^{}]+)\s*{'
    selectors = re.findall(selector_pattern, css_content)
    
    # Clean up selectors
    cleaned_selectors = []
    for selector in selectors:
        # Split multiple selectors separated by commas
        parts = selector.split(',')
        for part in parts:
            cleaned = part.strip()
            if cleaned and not cleaned.startswith('@'):  # Skip @media, @import etc.
                cleaned_selectors.append(cleaned)
    
    return sorted(list(set(cleaned_selectors)))

def extract_css_from_html(html_content):
    """Extract CSS content from HTML file."""
    css_pattern = r'<style>(.*?)</style>'
    match = re.search(css_pattern, html_content, re.DOTALL)
    return match.group(1).strip() if match else ""

def validate_css_preservation(original_css_path, generated_html_path):
    """Validate that CSS structure is preserved in generated HTML."""
    
    # Read original CSS
    if not os.path.exists(original_css_path):
        print(f"❌ Original CSS file not found: {original_css_path}")
        return False
    
    with open(original_css_path, 'r', encoding='utf-8') as f:
        original_css = f.read()
    
    # Read generated HTML
    if not os.path.exists(generated_html_path):
        print(f"❌ Generated HTML file not found: {generated_html_path}")
        return False
    
    with open(generated_html_path, 'r', encoding='utf-8') as f:
        generated_html = f.read()
    
    # Extract CSS from HTML
    generated_css = extract_css_from_html(generated_html)
    
    if not generated_css:
        print("❌ No CSS found in generated HTML")
        return False
    
    # Extract selectors from both
    original_selectors = extract_css_selectors(original_css)
    generated_selectors = extract_css_selectors(generated_css)
    
    print(f"\n=== CSS Validation Report ===")
    print(f"Original CSS selectors: {len(original_selectors)}")
    print(f"Generated CSS selectors: {len(generated_selectors)}")
    
    # Check for missing selectors
    missing_selectors = set(original_selectors) - set(generated_selectors)
    if missing_selectors:
        print(f"\n❌ Missing selectors ({len(missing_selectors)}):")
        for selector in sorted(missing_selectors):
            print(f"  - {selector}")
    else:
        print(f"\n✅ All original selectors preserved")
    
    # Check for added selectors
    added_selectors = set(generated_selectors) - set(original_selectors)
    if added_selectors:
        print(f"\n➕ Added selectors ({len(added_selectors)}):")
        for selector in sorted(added_selectors):
            print(f"  + {selector}")
    
    # Check if original CSS content is mostly preserved
    original_clean = re.sub(r'\s+', ' ', original_css.strip())
    generated_clean = re.sub(r'\s+', ' ', generated_css.strip())
    
    preservation_ratio = len(set(original_clean.split()) & set(generated_clean.split())) / len(set(original_clean.split()))
    
    print(f"\nCSS Content Preservation: {preservation_ratio:.1%}")
    
    if preservation_ratio > 0.9:
        print("✅ CSS structure well preserved")
        return True
    elif preservation_ratio > 0.7:
        print("⚠️ CSS partially preserved - some modifications detected")
        return True
    else:
        print("❌ CSS significantly modified")
        return False

def validate_image_paths(expected_images, generated_html_path):
    """Validate that image paths are preserved in generated HTML."""
    
    if not os.path.exists(generated_html_path):
        print(f"❌ Generated HTML file not found: {generated_html_path}")
        return False
    
    with open(generated_html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print(f"\n=== Image Path Validation ===")
    print(f"Expected images: {len(expected_images)}")
    
    all_found = True
    for img_path in expected_images:
        if img_path in html_content:
            print(f"✅ {img_path}")
        else:
            print(f"❌ {img_path} - NOT FOUND")
            all_found = False
    
    # Also check for any unexpected image paths
    img_pattern = r'src=["\']([^"\']*\.(png|jpg|jpeg|gif|svg))["\']'
    found_images = re.findall(img_pattern, html_content, re.IGNORECASE)
    found_image_paths = [img[0] for img in found_images]
    
    unexpected_images = set(found_image_paths) - set(expected_images)
    if unexpected_images:
        print(f"\n⚠️ Unexpected images found:")
        for img in unexpected_images:
            print(f"  ? {img}")
    
    return all_found

def run_full_validation(original_css_path, expected_images, generated_html_path):
    """Run complete validation of CSS and image preservation."""
    
    print("🔍 Running Full Validation...")
    print("=" * 50)
    
    css_valid = validate_css_preservation(original_css_path, generated_html_path)
    images_valid = validate_image_paths(expected_images, generated_html_path)
    
    print(f"\n{'=' * 50}")
    if css_valid and images_valid:
        print("🎉 Validation PASSED - All requirements met!")
        return True
    else:
        print("❌ Validation FAILED - Issues detected")
        if not css_valid:
            print("  - CSS structure issues")
        if not images_valid:
            print("  - Image path issues")
        return False

if __name__ == "__main__":
    # Example usage
    original_css_path = "first_page.css"
    generated_html_path = "first_page_html.html"
    expected_images = [
        "images/LCM300-0-0.png",
        "images/LCM300-0-1.png", 
        "images/LCM300-0-2.png"
    ]
    
    run_full_validation(original_css_path, expected_images, generated_html_path)