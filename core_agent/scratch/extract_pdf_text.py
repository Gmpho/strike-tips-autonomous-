import httpx
import pypdf
import io
import sys

def extract_pdf_text(url, pages=None):
    print(f"Downloading PDF from {url}...")
    try:
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        pdf_file = io.BytesIO(response.content)
        reader = pypdf.PdfReader(pdf_file)
        
        num_pages = len(reader.pages)
        print(f"Total pages: {num_pages}")
        
        if pages is None:
            pages = range(num_pages)
            
        text = ""
        for i in pages:
            if i < num_pages:
                print(f"Extracting page {i+1}...")
                text += f"\n--- PAGE {i+1} ---\n"
                text += reader.pages[i].extract_text()
        
        return text
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    url = "https://aztabstorage.blob.core.windows.net/tabonline-blob/FieldsPDF/ComputaformSA/HOLLYWOODBETS%20KENILWORTH@2026.05.03.pdf"
    # Extract pages 4 to 8 (index 3 to 7) which usually contain the first few races
    result = extract_pdf_text(url, pages=range(3, 10))
    print(result)
