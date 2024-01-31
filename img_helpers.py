import base64


def image_to_base64(image_file):
    # Guess the MIME type of the image
    encoded_string = base64.b64encode(image_file).decode('utf-8')

    # Format the result with the appropriate prefix
    image_base64 = f"data:image/png;base64,{encoded_string}"

    return image_base64
