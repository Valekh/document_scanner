import io
import base64
import json

import cv2
import pytesseract
from PIL import Image
import requests
import fitz
from googleapiclient.http import MediaIoBaseDownload

from config import CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES, webhook_url, pytesseract_path
from Google import Create_Service

pytesseract.pytesseract.tesseract_cmd = pytesseract_path

service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)


def scan(file):
    file_names = get_the_files(file)

    if file['extension'] != 'pdf':
        file = file_names[0]
        result = {
            'readability': text_recognition(file),
            'borders': check_the_borders(file)
        }
    else:
        result = {
            'readability': True,
            'borders': True,
            'number of pages': len(file_names),
            'page_number': {}
        }
        for page in file_names.items():
            errors = []

            for image in page[1]:
                readability = text_recognition(image)
                borders = check_the_borders(image)

                if result['readability']:
                    print('beep')
                    result['readability'] = readability

                if result['borders']:
                    result['borders'] = borders

                if not readability:
                    errors.append({'readability': False})

                if not borders:
                    errors.append({'borders': False})

            if len(errors) > 0:
                result['page_number'][page[0]] = errors[0]

    send_webhook(result)


def get_the_files(file):
    if file['file_type'] == 'gd':
        file_name = download_file_from_gd(file['file'], file['extension'])
    else:
        file_name = "base64_file." + file['extension']
        with open(file_name, "wb") as fh:
            fh.write(base64.decodebytes(file['file']))

    if file['extension'] == 'pdf':
        files = extract_images_from_pdf(file_name)
    else:
        files = [file_name]

    return files


def download_file_from_gd(file_id, file_extension):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fd=fh, request=request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        print("Download progress: {0}".format(status.progress() * 100))

    fh.seek(0)

    file_name = 'file_from_google.' + file_extension
    with open(file_name, "wb") as f:
        f.write(fh.read())
        f.close()
    return file_name


def extract_images_from_pdf(file):
    pdf_file = fitz.open(file)

    image_names = {}
    for page_index in range(len(pdf_file)):
        image_names[page_index + 1] = []

        page = pdf_file[page_index]
        image_list = page.get_images()

        for image_index, img in enumerate(image_list, start=1):
            xref = img[0]
            pdf_file.extract_image(xref)

            pix = fitz.Pixmap(pdf_file, xref)

            image_name = f"image{page_index + 1}_{image_index}.png"
            pix.save(image_name)

            image_names[page_index + 1].append(image_name)

    return image_names


def text_recognition(image):
    img = cv2.imread(image)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    cv2.imshow('output1', img)
    cv2.waitKey(0)

    result = pytesseract.image_to_string(img)

    result = result.replace(" ", "")
    result = result.replace("\n", "")

    if len(result) > 5:
        return True
    return False


def check_the_borders(image_name):
    image = cv2.imread(image_name)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, threshold = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(threshold, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    max_area = 0
    find_contours = False
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 1000:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.015 * peri, True)
            if area > max_area and len(approx) == 4:
                max_area = area
                find_contours = True

    if not find_contours:
        return False
    return True


def send_webhook(data):
    requests.post(webhook_url, data=json.dumps(data), headers={"Content-Type": 'application/json'})
    return


# file = {
#     'file_type': 'gd OR file': str,
#     'file': 'gd_id: str OR base64': base64,
#     'extension': 'pdf OR jpeg/jpg': str
# }


google_document_ID = 'google_document_ID'
file = {
    'file_type': 'gd',
    'file': google_document_ID,
    'extension': 'pdf'
}
scan(file)
