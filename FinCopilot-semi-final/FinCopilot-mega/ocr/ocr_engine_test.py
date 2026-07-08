from ocr.ocr_engine import ocr

print("OCR object loaded successfully")

result = ocr.ocr(r"C:\Users\Pray\Downloads\Bill 2.jpeg")

print("SUCCESS")
print(result[:3] if result else "No result")