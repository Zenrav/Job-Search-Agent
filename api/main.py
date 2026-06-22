from fastapi import FastAPI, HTTPException, UploadFile, File
import fitz

app = FastAPI(
    title="Resume Parser API",
    description="An API to parse resumes from PDF files and extract relevant information.",
    version="1.0.0"
)
@app.get("/")
def read_root():
    return {"message": "Welcome to the Resume Parser API!"}

@app.post("/parse_resume/")
async def parse_resume(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
    
    try:
        # Read the uploaded PDF file
        pdf_data = await file.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        # Extract text from the PDF
        text = ""
        for page in doc:
            text += page.get_text()
        
        # Here you can add your resume parsing logic to extract relevant information
        # For demonstration, we will just return the extracted text
        return {"extracted_text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)