# PDF to HTML Converter - Streamlit App

A comprehensive Streamlit application that converts PDF documents to structured HTML with AI-enhanced first page styling.

## 🚀 Features

- **📄 PDF Upload**: Easy drag-and-drop PDF upload
- **🎨 Custom CSS Styling**: Upload your own CSS files for styling
- **🤖 AI-Enhanced First Page**: Uses OpenAI GPT-4 to create a beautifully formatted first page
- **🖼️ Image Extraction**: Automatically extracts and preserves all images
- **📊 Table Extraction**: Extracts tables using Camelot
- **📦 Complete Package**: Download HTML with all assets in a zip file
- **🧹 Auto Cleanup**: Automatically cleans up intermediate files
- **📱 Responsive UI**: User-friendly Streamlit interface

## 📋 Prerequisites

1. **Python 3.8+**
2. **OpenAI API Key** (for enhanced first page generation)
3. **System Dependencies** (see installation section)

## 🛠️ Installation

### 1. Clone or Download Files
```bash
# Create a new directory
mkdir pdf-to-html-converter
cd pdf-to-html-converter

# Save the streamlit_app.py and requirements.txt files
```

### 2. Install System Dependencies

#### On Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y ghostscript
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0
sudo apt-get install -y python3-tk
```

#### On macOS:
```bash
brew install ghostscript
```

#### On Windows:
- Download and install Ghostscript from: https://www.ghostscript.com/download/gsdnld.html
- Add Ghostscript to your PATH

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables (Optional)
Create a `.env` file in your project directory:
```
OPENAI_API_KEY=your_openai_api_key_here
```

## 🚀 Usage

### 1. Start the Streamlit App
```bash
streamlit run streamlit_app.py
```

### 2. Open Your Browser
The app will automatically open at `http://localhost:8501`

### 3. Upload Files
1. **PDF File**: Upload the PDF
