from pathlib import Path
import tempfile

import pypdfium2 as pdfium
import pytesseract


def ocr_pdf(file_path: str | Path, psm: int = 6) -> list[list[str]]:
    path = Path(file_path)
    pdf = pdfium.PdfDocument(str(path))
    all_lines: list[list[str]] = []

    for page_number in range(len(pdf)):
        page = pdf[page_number]
        bitmap = page.render(scale=2)
        pil_image = bitmap.to_pil()

        ocr_data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT, config=f"--psm {psm}")
        page_lines: dict[int, list[str]] = {}
        for i, text in enumerate(ocr_data["text"]):
            text = text.strip()
            if text:
                line_num = ocr_data["line_num"][i]
                page_lines.setdefault(line_num, []).append(text)

        for line_num in sorted(page_lines):
            all_lines.append(page_lines[line_num])

        page.close()

    pdf.close()
    return all_lines
