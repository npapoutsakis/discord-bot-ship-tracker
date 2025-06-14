import pytesseract
from PIL import Image

# Load the image
image = Image.open('./screenshots/test.png')

# Extract text
text = pytesseract.image_to_string(image)
print(text)