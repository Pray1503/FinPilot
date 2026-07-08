from pathlib import Path
from paddleocr import PaddleOCR

print("=" * 60)
print("Loading PaddleOCR...")
print("=" * 60)

# Initialize the model only once
ocr = PaddleOCR(
    use_angle_cls='True',
    lang="en"
)

# Path to your benchmark receipt
image_path = Path(r"C:\Users\Pray\Downloads\Bill 3.jpeg")

print(f"\nReading image: {image_path}")

# Check that the image exists
if not image_path.exists():
    raise FileNotFoundError(f"Image not found: {image_path}")

print("\nRunning OCR...\n")


result = ocr.ocr(str(image_path), cls=True)

print("\n" + "=" * 60)
print("FULL OCR TEXT")
print("=" * 60)

all_lines = []

for line in result[0]:
    text = line[1][0]
    all_lines.append(text)
    print(text)

print("\n" + "=" * 60)
print("RAW TEXT BLOCK")
print("=" * 60)
print("\n".join(all_lines))