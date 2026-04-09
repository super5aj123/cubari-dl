#Anthony Rowan
#04/08/2026
#Python program to download raw images from Cubari links

#Half written by me, half vibe coded on and off over a few hours
#This is mainly a tool made for my own purposes, I don't really have plans to support other users, but if you find it useful feel free to use it.

#To Use: Just run the Python program, and give it the requested URL (You can get if from the gist source button on cubari)
#Usually it'll be something like python cubari-dl.py or python3 cubari-dl.py

#If you get an error due to missing libraries, run pip install -r requirements.txt
#You may have to run python3 -m pip install -r requirements.txt or python -m pip install requirements.txt depending on your setup

#I only tested this on one title, so I'm not sure how well it works with others.

import os
import re
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image

baseURL = "https://cubari.moe"
requestHeaders = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://cubari.moe/"
}

def createSession():
    httpSession = requests.Session()
    httpSession.headers.update(requestHeaders)
    return httpSession

def normalizeURL(url):
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return baseURL + url

def getJson(url:str, httpSession): #Get the raw JSON from the URL.
    response = httpSession.get(normalizeURL(url), timeout=30)
    response.raise_for_status()

    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as e:
        contentType = response.headers.get("Content-Type", "").split(";")[0].lower()
        raise ValueError(f"Expected JSON from {normalizeURL(url)} but got {contentType or 'unknown content type'}") from e

def sanitizeName(name, fallbackName):
    safeName = "".join(character if character.isalnum() or character in (" ", "-", "_", ".") else "_" for character in str(name))
    safeName = " ".join(safeName.split()).strip(" ._")
    if safeName:
        return safeName
    return fallbackName

def getOutputFolderName(url, title):
    if title:
        return sanitizeName(title, "cubari-images")

    parsedURL = urlparse(url)
    pathParts = [part for part in parsedURL.path.split("/") if part]
    if pathParts:
        return sanitizeName(pathParts[-1], "cubari-images")
    return "cubari-images"

def getPdfOutputPath(url, title):
    outputName = getOutputFolderName(url, title)
    return f"{outputName}.pdf"

def getChapterFolderName(chapterNumber, chapterTitle):
    if chapterTitle:
        return sanitizeName(f"{chapterNumber} - {chapterTitle}", f"{chapterNumber}")
    return sanitizeName(f"{chapterNumber}", "chapter")

def getChapterSortKey(chapterNumber):
    chapterParts = re.split(r"(\d+)", str(chapterNumber))
    sortKey = []

    for chapterPart in chapterParts:
        if not chapterPart:
            continue
        if chapterPart.isdigit():
            sortKey.append((0, int(chapterPart)))
        else:
            sortKey.append((1, chapterPart.lower()))

    return tuple(sortKey)

def isImageURL(url):
    imagePath = urlparse(url).path.lower()
    return imagePath.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"))

def isLikelySourceURL(sourceText):
    if not isinstance(sourceText, str):
        return False

    sourceText = sourceText.strip()
    if not sourceText:
        return False

    if sourceText.startswith("/"):
        return True
    if sourceText.startswith("http://") or sourceText.startswith("https://"):
        return True

    return False

def getOutputMode():
    while True:
        outputChoice = input("Choose output type (1 = PDF, 2 = Images): ").strip()

        if outputChoice == "1":
            return "pdf"
        if outputChoice == "2":
            return "images"

        print("Invalid choice. Enter 1 for PDF or 2 for images.")

def resolveImageURLs(sourceData, httpSession):
    if isinstance(sourceData, list):
        imageURLs = []
        for sourceItem in sourceData:
            imageURLs.extend(resolveImageURLs(sourceItem, httpSession))
        return imageURLs

    if isinstance(sourceData, dict):
        for sourceKey in ("src", "url", "image", "imageUrl", "imageURL", "file", "fileUrl", "fileURL"):
            if sourceKey in sourceData and isLikelySourceURL(sourceData[sourceKey]):
                return resolveImageURLs(sourceData[sourceKey], httpSession)

        imageURLs = []
        for sourceItem in sourceData.values():
            imageURLs.extend(resolveImageURLs(sourceItem, httpSession))
        return imageURLs

    if isinstance(sourceData, str):
        sourceData = sourceData.strip()
        if not isLikelySourceURL(sourceData):
            return []

        sourceURL = normalizeURL(sourceData)

        if isImageURL(sourceURL):
            return [sourceURL]

        resolvedData = getJson(sourceURL, httpSession)
        return resolveImageURLs(resolvedData, httpSession)

    raise ValueError(f"Unsupported source data: {type(sourceData)}")

def getFileExtension(imageURL, contentType):
    parsedURL = urlparse(imageURL)
    fileExtension = os.path.splitext(parsedURL.path)[1].lower()
    if fileExtension:
        return fileExtension

    if "jpeg" in contentType:
        return ".jpg"
    if "png" in contentType:
        return ".png"
    if "webp" in contentType:
        return ".webp"
    if "gif" in contentType:
        return ".gif"
    if "bmp" in contentType:
        return ".bmp"
    if "avif" in contentType:
        return ".avif"
    return ".img"

def getGroupImageURLs(groups, httpSession):
    groupImageURLs = []

    for groupName, groupData in groups.items():
        print(f"Group: {groupName}")

        try:
            imageURLs = resolveImageURLs(groupData, httpSession)
            if imageURLs:
                groupImageURLs.append((groupName, imageURLs))
            else:
                print(f"No images found for group {groupName}")
        except Exception as e:
            print(f"Failed to resolve group {groupName} - {str(e)}")

    return groupImageURLs

def flattenGroupImageURLs(groupImageURLs):
    imageURLs = []

    for groupName, groupImages in groupImageURLs:
        imageURLs.extend(groupImages)

    return imageURLs

def downloadImages(imageURLs, outputFolder, httpSession):
    if not imageURLs:
        print(f"No images found for {outputFolder}")
        return

    os.makedirs(outputFolder, exist_ok=True)
    pagePadding = max(3, len(str(len(imageURLs))))

    for imageNumber, imageURL in enumerate(imageURLs, start=1):
        response = None

        try:
            response = httpSession.get(imageURL, timeout=30, stream=True)
            response.raise_for_status()

            contentType = response.headers.get("Content-Type", "").split(";")[0].lower()
            if not contentType.startswith("image/"):
                raise ValueError(f"Expected image content but got {contentType or 'unknown content type'}")

            fileExtension = getFileExtension(imageURL, contentType)
            fileName = f"{imageNumber:0{pagePadding}d}{fileExtension}"
            outputPath = os.path.join(outputFolder, fileName)

            with open(outputPath, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)

            print(f"Saved {outputPath}")
        except Exception as e:
            print(f"Failed to get image {imageURL} - {str(e)}")
        finally:
            if response is not None:
                response.close()

def prepareImageForPdf(sourceImage):
    if sourceImage.mode in ("RGBA", "LA") or (sourceImage.mode == "P" and "transparency" in sourceImage.info):
        alphaImage = sourceImage.convert("RGBA")
        backgroundImage = Image.new("RGB", alphaImage.size, (255, 255, 255))
        backgroundImage.paste(alphaImage, mask=alphaImage.getchannel("A"))
        return backgroundImage

    if sourceImage.mode != "RGB":
        return sourceImage.convert("RGB")

    return sourceImage.copy()

def getPdfPageData(imageURL, httpSession, imageNumber, imageCount):
    response = None

    try:
        print(f"Adding page {imageNumber}/{imageCount}")
        response = httpSession.get(imageURL, timeout=30)
        response.raise_for_status()

        contentType = response.headers.get("Content-Type", "").split(";")[0].lower()
        if not contentType.startswith("image/"):
            raise ValueError(f"Expected image content but got {contentType or 'unknown content type'}")

        with Image.open(BytesIO(response.content)) as sourceImage:
            pdfImage = prepareImageForPdf(sourceImage)

        imageWidth, imageHeight = pdfImage.size
        imageBuffer = BytesIO()
        pdfImage.save(imageBuffer, format="JPEG", quality=100, subsampling=0)
        pdfImage.close()

        return imageBuffer.getvalue(), imageWidth, imageHeight
    finally:
        if response is not None:
            response.close()

def writePdfObject(pdfFile, objectNumber, objectBody, objectOffsets):
    objectOffsets[objectNumber] = pdfFile.tell()
    pdfFile.write(f"{objectNumber} 0 obj\n".encode("ascii"))
    pdfFile.write(objectBody)
    pdfFile.write(b"\nendobj\n")

def createPdf(imageURLs, outputPath, httpSession):
    if not imageURLs:
        print(f"No images found for {outputPath}")
        return

    totalObjects = 2 + (len(imageURLs) * 3)
    objectOffsets = [0] * (totalObjects + 1)
    pageObjectNumbers = [3 + (imageIndex * 3) for imageIndex in range(len(imageURLs))]

    try:
        with open(outputPath, "wb") as pdfFile:
            pdfFile.write(b"%PDF-1.4\n%\xff\xff\xff\xff\n")

            writePdfObject(pdfFile, 1, b"<< /Type /Catalog /Pages 2 0 R >>", objectOffsets)

            kidsReferences = " ".join(f"{pageObjectNumber} 0 R" for pageObjectNumber in pageObjectNumbers)
            pagesObject = f"<< /Type /Pages /Count {len(imageURLs)} /Kids [{kidsReferences}] >>".encode("ascii")
            writePdfObject(pdfFile, 2, pagesObject, objectOffsets)

            for imageIndex, imageURL in enumerate(imageURLs):
                pageObjectNumber = pageObjectNumbers[imageIndex]
                contentObjectNumber = pageObjectNumber + 1
                imageObjectNumber = pageObjectNumber + 2

                imageBytes, imageWidth, imageHeight = getPdfPageData(imageURL, httpSession, imageIndex + 1, len(imageURLs))

                contentStream = f"q\n{imageWidth} 0 0 {imageHeight} 0 0 cm\n/PageImage Do\nQ\n".encode("ascii")
                pageObject = (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {imageWidth} {imageHeight}] "
                    f"/Resources << /XObject << /PageImage {imageObjectNumber} 0 R >> >> "
                    f"/Contents {contentObjectNumber} 0 R >>"
                ).encode("ascii")
                contentObject = f"<< /Length {len(contentStream)} >>\nstream\n".encode("ascii") + contentStream + b"endstream"
                imageObject = (
                    f"<< /Type /XObject /Subtype /Image /Width {imageWidth} /Height {imageHeight} "
                    f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(imageBytes)} >>\nstream\n"
                ).encode("ascii") + imageBytes + b"\nendstream"

                writePdfObject(pdfFile, pageObjectNumber, pageObject, objectOffsets)
                writePdfObject(pdfFile, contentObjectNumber, contentObject, objectOffsets)
                writePdfObject(pdfFile, imageObjectNumber, imageObject, objectOffsets)

            xrefOffset = pdfFile.tell()
            pdfFile.write(f"xref\n0 {totalObjects + 1}\n".encode("ascii"))
            pdfFile.write(b"0000000000 65535 f \n")

            for objectNumber in range(1, totalObjects + 1):
                pdfFile.write(f"{objectOffsets[objectNumber]:010d} 00000 n \n".encode("ascii"))

            trailer = (
                f"trailer\n<< /Size {totalObjects + 1} /Root 1 0 R >>\n"
                f"startxref\n{xrefOffset}\n%%EOF\n"
            ).encode("ascii")
            pdfFile.write(trailer)

        print(f"Saved {outputPath}")
    except Exception:
        if os.path.exists(outputPath):
            os.remove(outputPath)
        raise

def collectChapterImageURLs(chapterNumber, chapterData, httpSession):
    chapterTitle = chapterData.get("title", "")
    groups = chapterData.get("groups", {})

    if not groups:
        print(f"Chapter {chapterNumber} has no groups.")
        return []

    print(f"Collecting chapter {chapterNumber}: {chapterTitle}")
    groupImageURLs = getGroupImageURLs(groups, httpSession)
    return flattenGroupImageURLs(groupImageURLs)

def downloadChapter(chapterNumber, chapterData, seriesFolder, httpSession):
    chapterTitle = chapterData.get("title", "")
    chapterFolder = os.path.join(seriesFolder, getChapterFolderName(chapterNumber, chapterTitle))
    groups = chapterData.get("groups", {})

    if not groups:
        print(f"Chapter {chapterNumber} has no groups.")
        return

    print(f"Downloading chapter {chapterNumber}: {chapterTitle}")
    groupImageURLs = getGroupImageURLs(groups, httpSession)
    groupItems = list(groupImageURLs)

    if len(groupItems) == 1:
        groupName, imageURLs = groupItems[0]
        downloadImages(imageURLs, chapterFolder, httpSession)
        return

    for groupName, imageURLs in groupItems:
        groupFolder = os.path.join(chapterFolder, sanitizeName(groupName, "group"))
        downloadImages(imageURLs, groupFolder, httpSession)

def downloadSeries(data, sourceURL, httpSession):
    title = data.get("title")
    chapters = data.get("chapters", {})

    if not chapters:
        print("No chapters found.")
        return

    seriesFolder = getOutputFolderName(sourceURL, title)
    os.makedirs(seriesFolder, exist_ok=True)

    sortedChapters = sorted(chapters.items(), key=lambda chapterItem: getChapterSortKey(chapterItem[0]))
    for chapterNumber, chapterData in sortedChapters:
        downloadChapter(chapterNumber, chapterData, seriesFolder, httpSession)

def createSeriesPdf(data, sourceURL, httpSession):
    title = data.get("title")
    chapters = data.get("chapters", {})

    if not chapters:
        print("No chapters found.")
        return

    imageURLs = []
    sortedChapters = sorted(chapters.items(), key=lambda chapterItem: getChapterSortKey(chapterItem[0]))

    for chapterNumber, chapterData in sortedChapters:
        imageURLs.extend(collectChapterImageURLs(chapterNumber, chapterData, httpSession))

    outputPath = getPdfOutputPath(sourceURL, title)
    createPdf(imageURLs, outputPath, httpSession)

def __main__():
    outputMode = getOutputMode()
    url = input("Enter Cubari JSON or chapter API URL: ").strip()
    httpSession = createSession()

    try:
        data = getJson(url, httpSession)

        if isinstance(data, dict) and "chapters" in data:
            if outputMode == "pdf":
                createSeriesPdf(data, url, httpSession)
            else:
                downloadSeries(data, url, httpSession)
        elif isinstance(data, dict) and "groups" in data:
            imageURLs = flattenGroupImageURLs(getGroupImageURLs(data.get("groups", {}), httpSession))

            if outputMode == "pdf":
                outputPath = getPdfOutputPath(url, data.get("title"))
                createPdf(imageURLs, outputPath, httpSession)
            else:
                outputFolder = getOutputFolderName(url, data.get("title"))
                downloadImages(imageURLs, outputFolder, httpSession)
        elif isinstance(data, list):
            imageURLs = resolveImageURLs(data, httpSession)

            if outputMode == "pdf":
                outputPath = getPdfOutputPath(url, None)
                createPdf(imageURLs, outputPath, httpSession)
            else:
                outputFolder = getOutputFolderName(url, None)
                downloadImages(imageURLs, outputFolder, httpSession)
        else:
            print("Unsupported JSON format.")
    except Exception as e:
        print(str(e))
    finally:
        httpSession.close()

    

if __name__ == "__main__":
    __main__()
